"""Area of Occupancy (AOO) grid computation for RLE assessments.

Provides the ``AOOGrid`` / ``AOOGridPolygons`` class hierarchies and the
``make_aoo_grid()`` / ``make_aoo_polygons()`` helpers for computing AOO grids
from local data sources (GeoParquet, GeoJSON, COGs).

Earth Engine backends live in the optional ``rle-python-gee`` package
(``rle.gee``); construct them explicitly from there.
"""

import logging
import re
from abc import ABC, abstractmethod

import geopandas as gpd

logger = logging.getLogger(__name__)


def slugify_ecosystem_name(name: str) -> str:
    """Sanitize an ecosystem name for use as a DataFrame column name.

    Replaces any character that is not alphanumeric, underscore, or hyphen
    with an underscore.
    """
    return re.sub(r'[^a-zA-Z0-9_-]', '_', str(name))


from rle.core.ecosystems import (
    Ecosystems,
    EcosystemKind,
    EcosystemsFile,
    EcosystemsGeoParquet,
    EcosystemsCOG,
)


# AOO grid cell size in meters (10 x 10 km)
AOO_CELL_SIZE_M = 10_000

# Number of (grid cell, ecosystem feature) candidate pairs whose intersections
# are materialized at once in AOOGridVectorLocal._compute. Chunking bounds peak
# memory for national-scale datasets (millions of pairs) without changing the
# result. Tunable; larger = fewer Python iterations, more transient memory.
_AOO_INTERSECTION_CHUNK = 100_000


def _remote_file_exists(path: str) -> bool:
    """Check if a file exists, supporting gs:// URIs and local paths."""
    import fsspec
    try:
        fs, fpath = fsspec.core.url_to_fs(path)
        return fs.exists(fpath)
    except Exception:
        return False


class AOOGridNotComputedError(Exception):
    """Raised when accessing grid data before compute() has been called."""

    def __init__(self):
        super().__init__(
            "AOO grid has not been computed yet. "
            "Call .compute() to run the computation."
        )


class AOOGrid(ABC):
    """Base class for Area of Occupancy grid computations.

    Provides derived properties (cell count, AOO) and visualization methods.

    Subclasses implement ``_compute()`` to run the computation and store
    results in the appropriate backend, and ``_load_grid_cells()`` to
    download results on demand.
    """

    def __init__(self, ecosystems: Ecosystems):
        self._ecosystems = ecosystems
        self._computed = False
        self.task = None
        self._grid_cells: gpd.GeoDataFrame | None = None

    # -- classmethods ---------------------------------------------------------

    @classmethod
    def from_parquet(cls, data, *, ecosystem_column: str, **kwargs) -> "AOOGrid":
        """Create an AOO grid from a GeoParquet file."""
        return AOOGridVectorLocal(
            EcosystemsGeoParquet(data, ecosystem_column=ecosystem_column), **kwargs
        )

    @classmethod
    def from_file(cls, data, *, ecosystem_column: str, **kwargs) -> "AOOGrid":
        """Create an AOO grid from a vector file (Shapefile, GeoJSON, etc.)."""
        return AOOGridVectorLocal(
            EcosystemsFile(data, ecosystem_column=ecosystem_column), **kwargs
        )

    @classmethod
    def from_cog(cls, data, **kwargs) -> "AOOGrid":
        """Create an AOO grid from a Cloud Optimized GeoTIFF."""
        return AOOGridCOG(EcosystemsCOG(data), **kwargs)

    # -- computation ---------------------------------------------------------

    @abstractmethod
    def _compute(self) -> None:
        """Run the AOO grid computation and store results in the backend.

        Must not return the result — store it in the backend (EE asset,
        file, or in-memory cache for local backends).
        """
        ...

    @abstractmethod
    def _load_grid_cells(self) -> gpd.GeoDataFrame:
        """Load grid cells from the backend.

        Returns a GeoDataFrame with geometries in EPSG:4326.
        """
        ...

    def compute(self) -> "AOOGrid":
        """Explicitly run the AOO grid computation.

        Results are stored in the backend. Access them via ``grid_cells``.
        Returns self for method chaining.
        """
        self._compute()
        self._computed = True
        self._grid_cells = None  # clear any stale local cache
        return self

    @property
    def grid_cells(self) -> gpd.GeoDataFrame:
        """GeoDataFrame of AOO grid cells. Raises if compute() not called."""
        if not self._computed:
            raise AOOGridNotComputedError()
        if self._grid_cells is None:
            self._grid_cells = self._load_grid_cells().reset_index(drop=True)
        return self._grid_cells

    # -- derived properties --------------------------------------------------

    @property
    def cell_count(self) -> int:
        """Total number of grid cells that intersect the ecosystem."""
        return len(self.grid_cells)

    @property
    def aoo_km2(self) -> float:
        """AOO in km² (cell count × 100 km² per cell)."""
        return self.cell_count * (AOO_CELL_SIZE_M / 1000) ** 2

    # -- export / write -------------------------------------------------------

    def to_ee_feature_collection(self, asset_id: str, *,
                                  gcs_bucket: str | None = None):
        """Export grid cells to an Earth Engine table asset.

        Requires the optional ``rle-python-gee`` package.
        Returns the task/result, or None if asset already exists.
        """
        try:
            from rle.gee.upload import upload_gdf_to_ee_asset
        except ImportError:
            raise ImportError(
                "Earth Engine export requires the 'rle-python-gee' package. "
                "Install it with: pip install rle-python-gee"
            ) from None

        return upload_gdf_to_ee_asset(
            self.grid_cells, asset_id,
            gcs_bucket=gcs_bucket, description="aoo_grid_export"
        )

    def to_parquet(self, path) -> None:
        """Write grid cells as a GeoParquet file."""
        from rle.core.ecosystems import _write_parquet
        _write_parquet(self.grid_cells, path)

    # -- filtering -----------------------------------------------------------

    def filter_by_ecosystem(self, ecosystem_name: str,
                            threshold: float = 0.0) -> "FilteredAOOGrid":
        """Return a filtered AOOGrid with only cells where the ecosystem
        fraction exceeds *threshold*.

        Args:
            ecosystem_name: Ecosystem name as it appears in the source data.
            threshold: Minimum fractional area (0.0–1.0). Default 0.0 means
                any presence.
        """
        col = slugify_ecosystem_name(ecosystem_name)
        if col not in self.grid_cells.columns:
            skip = {"grid_col", "grid_row", "count_geoms", "count_ecosystems", "geometry"}
            available = [c for c in self.grid_cells.columns if c not in skip]
            raise ValueError(
                f"Ecosystem column '{col}' not found. "
                f"Available: {available}"
            )
        mask = self.grid_cells[col] > threshold
        return FilteredAOOGrid(self, mask)

    # -- visualization -------------------------------------------------------

    def to_layer(self, *, get_fill_color=None, get_line_color=None):
        """Return a lonboard PolygonLayer of AOO grid cells."""
        try:
            from lonboard import PolygonLayer
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        if get_fill_color is None:
            get_fill_color = [128, 128, 128, 128]
        if get_line_color is None:
            get_line_color = [0, 0, 0, 255]

        if self.grid_cells.empty:
            return []
        return [PolygonLayer.from_geopandas(
            self.grid_cells,
            get_fill_color=get_fill_color,
            get_line_color=get_line_color,
            line_width_min_pixels=1,
        )]

    def to_gdf_for_viz(self, *, get_fill_color=None, get_line_color=None, **_):
        """Return (gdf, style_dict) for static-image fallback rendering."""
        if get_fill_color is None:
            get_fill_color = [128, 128, 128, 128]
        if get_line_color is None:
            get_line_color = [0, 0, 0, 255]
        return self.grid_cells, {"fill": get_fill_color, "edge": get_line_color}

    def to_map(self, *, get_fill_color=None, get_line_color=None, **kwargs):
        """Return a lonboard Map showing the AOO grid cells."""
        try:
            from lonboard import Map
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        layer_kwargs = {}
        if get_fill_color is not None:
            layer_kwargs["get_fill_color"] = get_fill_color
        if get_line_color is not None:
            layer_kwargs["get_line_color"] = get_line_color
        layers = self.to_layer(**layer_kwargs)
        return Map(layers=layers, **kwargs)

    # -- display -------------------------------------------------------------

    def __repr__(self) -> str:
        if not self._computed:
            return f"{type(self).__name__}(not computed)"
        try:
            return (
                f"{type(self).__name__}("
                f"cell_count={self.cell_count}, "
                f"aoo_km2={self.aoo_km2:.0f})"
            )
        except RuntimeError:
            return f"{type(self).__name__}(computed, results pending)"

    def _repr_html_(self) -> str:
        if not self._computed:
            return (
                f"<b>{type(self).__name__}</b><br>"
                f"<i>Not computed — call .compute() to run</i>"
            )
        try:
            return (
                f"<b>{type(self).__name__}</b><br>"
                f"Grid cells: {self.cell_count}<br>"
                f"AOO: {self.aoo_km2:,.0f} km²"
            )
        except RuntimeError:
            return (
                f"<b>{type(self).__name__}</b><br>"
                f"<i>Export task running — check status at "
                f"<a href='https://code.earthengine.google.com/tasks'>EE Tasks</a></i>"
            )


# ---------------------------------------------------------------------------
# Filtered view
# ---------------------------------------------------------------------------


class FilteredAOOGrid(AOOGrid):
    """A filtered view of an AOOGrid, showing only cells matching a predicate."""

    def __init__(self, source: AOOGrid, mask):
        self._source = source
        self._mask = mask
        self._computed = source._computed
        self._grid_cells = None
        self._ecosystems = source._ecosystems

    def _compute(self):
        raise RuntimeError(
            "Cannot compute a filtered grid — compute the source grid first."
        )

    def _load_grid_cells(self):
        return self._source.grid_cells[self._mask].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Local vector backend (GeoJSON, GeoParquet)
# ---------------------------------------------------------------------------


class AOOGridVectorLocal(AOOGrid):
    """AOO grid from a local vector dataset (GeoJSON or GeoParquet)."""

    def _compute(self) -> None:
        import pandas as pd
        import shapely
        from rle.core.aoo_grid import generate_aoo_grid, AOO_CRS, AOO_CELL_SIZE

        empty_schema = [
            "grid_col", "grid_row", "count_geoms", "count_ecosystems", "geometry"
        ]

        eco = self._ecosystems.load().reset_index(drop=True)
        if eco.crs is not None and not eco.crs.equals("EPSG:4326"):
            eco = eco.to_crs("EPSG:4326")

        eco_col = self._ecosystems.ecosystem_column
        # Keep only the columns we need — bounds peak memory for national datasets.
        eco = eco[(["geometry", eco_col] if eco_col is not None else ["geometry"])]

        grid = generate_aoo_grid(eco.total_bounds)  # EPSG:4326

        # Candidate (grid_cell, ecosystem feature) pairs. Done in EPSG:4326 to
        # match the historical predicate exactly; index values are positional
        # since both frames use a 0..n RangeIndex.
        joined = gpd.sjoin(
            grid[["geometry"]], eco[["geometry"]],
            how="inner", predicate="intersects",
        )
        if joined.empty:
            self._computed_gdf = gpd.GeoDataFrame(columns=empty_schema)
            return
        grid_pos = joined.index.to_numpy()
        eco_pos = joined["index_right"].to_numpy()
        del joined

        # Reproject once to the equal-area CRS for area math, then free the
        # geographic ecosystem copy (the memory-heavy national vector).
        grid_geoms = grid.to_crs(AOO_CRS).geometry.to_numpy()
        eco_geoms = eco.to_crs(AOO_CRS).geometry.to_numpy()
        eco_values = eco[eco_col].to_numpy() if eco_col is not None else None
        del eco
        cell_area = AOO_CELL_SIZE * AOO_CELL_SIZE

        # Vectorized intersection areas, chunked to bound the transient count of
        # materialized intersection geometries. Mirrors the historical rule of
        # keeping every non-empty intersection (boundary touches included).
        frames = []
        for start in range(0, len(grid_pos), _AOO_INTERSECTION_CHUNK):
            gsel = grid_pos[start:start + _AOO_INTERSECTION_CHUNK]
            esel = eco_pos[start:start + _AOO_INTERSECTION_CHUNK]
            inter = shapely.intersection(grid_geoms[gsel], eco_geoms[esel])
            keep = ~shapely.is_empty(inter)
            if not keep.any():
                continue
            chunk = {
                "grid_idx": gsel[keep],
                "fraction": shapely.area(inter[keep]) / cell_area,
            }
            if eco_col is not None:
                chunk["ecosystem"] = eco_values[esel[keep]]
            frames.append(pd.DataFrame(chunk))

        if not frames:
            self._computed_gdf = gpd.GeoDataFrame(columns=empty_schema)
            return
        fractions = pd.concat(frames, ignore_index=True)

        # Summary counts per grid cell
        summary = fractions.groupby("grid_idx").agg(
            count_geoms=("fraction", "count"),
            count_ecosystems=(
                ("ecosystem", "nunique") if eco_col else ("fraction", "count")
            ),
        )

        # Build result with grid geometry
        result = grid.loc[summary.index].copy()
        result["count_geoms"] = summary["count_geoms"].values
        result["count_ecosystems"] = summary["count_ecosystems"].values

        # Wide columns: fractional area per ecosystem
        if eco_col is not None:
            pivot = fractions.pivot_table(
                index="grid_idx", columns="ecosystem",
                values="fraction", aggfunc="sum", fill_value=0.0,
            )
            # Sanitize ecosystem names for use as column names
            pivot.columns = [
                slugify_ecosystem_name(c)
                for c in pivot.columns
            ]
            # Ensure all intersecting grid cells have all ecosystem columns (fill 0)
            result = result.join(pivot)
            result[pivot.columns] = result[pivot.columns].fillna(0.0)

        self._computed_gdf = result.reset_index(drop=True)

    def _load_grid_cells(self) -> gpd.GeoDataFrame:
        return self._computed_gdf

    def to_polygons(self, **kwargs) -> "AOOGridPolygonVectorLocal":
        """Create intersection polygons for this local vector grid."""
        return AOOGridPolygonVectorLocal(self, **kwargs)


# Backward-compatibility aliases
AOOGridGeoParquet = AOOGridVectorLocal
AOOGridGeoJSON = AOOGridVectorLocal


# ---------------------------------------------------------------------------
# COG (Cloud Optimized GeoTIFF) backend
# ---------------------------------------------------------------------------


class AOOGridCOG(AOOGrid):
    """AOO grid from a Cloud Optimized GeoTIFF."""

    def _compute(self) -> None:
        from rasterstats import zonal_stats

        from rle.core.aoo_grid import generate_aoo_grid

        rds = self._ecosystems.load()
        # Get bounds in geographic coords
        bounds = rds.rio.transform_bounds("EPSG:4326")
        grid = generate_aoo_grid(bounds)

        # Reproject raster to equal-area for zonal stats
        rds_ea = rds.rio.reproject("ESRI:54034")
        grid_ea = grid.to_crs("ESRI:54034")

        stats = zonal_stats(
            grid_ea.geometry,
            rds_ea.values[0],
            affine=rds_ea.rio.transform(),
            stats=["mean"],
            nodata=rds_ea.rio.nodata,
        )
        # Keep only cells with non-zero values
        has_data = [bool(s["mean"]) for s in stats]
        result = grid_ea[has_data]

        self._computed_gdf = result[["geometry"]].to_crs("EPSG:4326").reset_index(drop=True)

    def _load_grid_cells(self) -> gpd.GeoDataFrame:
        return self._computed_gdf


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def make_aoo_grid(data, **kwargs) -> AOOGrid:
    """Create an AOO grid from an ``Ecosystems`` instance.

    Call ``.compute()`` to run the computation before accessing results.

    Args:
        data: An ``Ecosystems`` instance. Local vector / raster ecosystems
            return :class:`AOOGridVectorLocal` / :class:`AOOGridCOG`.
            Earth Engine ecosystems require the ``rle-python-gee`` package;
            construct the EE AOO backend explicitly from ``rle.gee``.
        **kwargs: Additional arguments passed to the backend constructor.

    Returns:
        An AOOGrid instance. Call .compute() to run the computation.

    Example:
        >>> from rle.core import Ecosystems
        >>> eco = Ecosystems.from_file("data.geojson", ecosystem_column="ECO_NAME")
        >>> aoo = make_aoo_grid(eco).compute()
        >>> print(aoo.cell_count)
    """
    if isinstance(data, Ecosystems):
        kind = data.kind
        if kind == EcosystemKind.VECTOR_LOCAL:
            return AOOGridVectorLocal(data, **kwargs)
        if kind == EcosystemKind.RASTER_LOCAL:
            return AOOGridCOG(data, **kwargs)
        if kind in (EcosystemKind.EE_IMAGE, EcosystemKind.EE_FEATURE_COLLECTION):
            raise ValueError(
                f"AOO grid for {kind.value} requires the 'rle-python-gee' package. "
                f"Install it and construct the Earth Engine AOO backend from rle.gee."
            )
        raise ValueError(f"AOO grid not yet supported for {kind.value}")

    raise TypeError(
        "make_aoo_grid expects an Ecosystems instance. Construct one first, e.g. "
        "Ecosystems.from_file(path, ecosystem_column=...) or a backend from rle.gee."
    )


def make_aoo_grid_cached(data, *, cache_path, **kwargs) -> AOOGrid:
    """Return an AOOGrid backed by a local GeoParquet cache at ``cache_path``.

    On cache hit, the grid cells are loaded from the parquet file and
    ``compute()`` is skipped. On cache miss, the grid is computed normally
    and the result is written to ``cache_path`` for next time.

    The returned AOOGrid behaves identically to ``make_aoo_grid(...).compute()``
    — ``grid_cells``, ``filter_by_ecosystem``, ``to_layer``, ``aoo_km2`` etc.
    all work the same way.

    Cache invalidation is the caller's responsibility: delete ``cache_path``
    if the source data changes.

    Args:
        data: Same as ``make_aoo_grid`` — an Ecosystems instance.
        cache_path: Local path or ``gs://`` URI for the GeoParquet cache file.
            Parent directories are created on write.
        **kwargs: Forwarded to ``make_aoo_grid``.
    """
    aoo = make_aoo_grid(data, **kwargs)
    cache_path_str = str(cache_path)
    if _remote_file_exists(cache_path_str):
        aoo._grid_cells = gpd.read_parquet(cache_path_str)
        aoo._computed = True
        logger.info("Loaded AOO grid from cache: %s", cache_path_str)
        return aoo
    aoo.compute()
    aoo.to_parquet(cache_path_str)
    logger.info("Wrote AOO grid cache: %s", cache_path_str)
    return aoo


# ---------------------------------------------------------------------------
# AOO Grid Polygons — intersection geometries
# ---------------------------------------------------------------------------


class AOOGridPolygonsNotComputedError(Exception):
    """Raised when accessing polygon data before compute() has been called."""

    def __init__(self):
        super().__init__(
            "AOO grid polygons have not been computed yet. "
            "Call .compute() to run the computation."
        )


class AOOGridPolygons(ABC):
    """Base class for AOO grid × ecosystem intersection polygons.

    Each row represents the geometric intersection of one grid cell with
    one ecosystem polygon.  Subclasses implement ``_compute()`` to produce
    the polygons and ``_load_polygons()`` to retrieve them.
    """

    def __init__(self, aoo_grid: AOOGrid):
        self._aoo_grid = aoo_grid
        self._computed = False
        self._polygons: gpd.GeoDataFrame | None = None
        self.task = None

    # -- abstract interface --------------------------------------------------

    @abstractmethod
    def _compute(self) -> None:
        """Run the intersection computation and store results in backend."""

    @abstractmethod
    def _load_polygons(self) -> gpd.GeoDataFrame:
        """Load the computed intersection polygons as a GeoDataFrame."""

    # -- public API ----------------------------------------------------------

    def compute(self) -> "AOOGridPolygons":
        """Run the intersection computation. Returns *self* for chaining."""
        self._compute()
        self._computed = True
        self._polygons = None  # clear cache
        return self

    @property
    def polygons(self) -> gpd.GeoDataFrame:
        """The intersection polygons as a GeoDataFrame."""
        if not self._computed:
            raise AOOGridPolygonsNotComputedError()
        if self._polygons is None:
            self._polygons = self._load_polygons().reset_index(drop=True)
        return self._polygons

    @property
    def polygon_count(self) -> int:
        """Number of (grid cell × ecosystem) intersection polygons."""
        return len(self.polygons)

    def filter_by_ecosystem(self, ecosystem_name: str) -> "FilteredAOOGridPolygons":
        """Return a filtered view with only polygons for the given ecosystem."""
        eco_col = self._aoo_grid._ecosystems.ecosystem_column
        if eco_col is None:
            raise ValueError("ecosystem_column is not set on the source data")
        mask = self.polygons[eco_col] == ecosystem_name
        return FilteredAOOGridPolygons(self, mask)

    # -- display -------------------------------------------------------------

    def __repr__(self) -> str:
        if not self._computed:
            return f"{type(self).__name__}(not computed)"
        try:
            return f"{type(self).__name__}(polygons={self.polygon_count})"
        except RuntimeError:
            return f"{type(self).__name__}(computed, results pending)"

    def _repr_html_(self) -> str:
        if not self._computed:
            return (
                f"<b>{type(self).__name__}</b><br>"
                f"<i>Not computed — call .compute() to run</i>"
            )
        try:
            count = self.polygon_count
        except Exception:
            return (
                f"<b>{type(self).__name__}</b><br>"
                f"<i>Computed — polygons not yet available (export may be running)</i>"
            )
        return (
            f"<b>{type(self).__name__}</b><br>"
            f"Polygons: {count:,}"
        )

    # -- export / write -------------------------------------------------------

    def to_ee_feature_collection(self, asset_id: str, *,
                                  gcs_bucket: str | None = None):
        """Export intersection polygons to an Earth Engine table asset.

        Requires the optional ``rle-python-gee`` package.
        Returns the task/result, or None if asset already exists.
        """
        try:
            from rle.gee.upload import upload_gdf_to_ee_asset
        except ImportError:
            raise ImportError(
                "Earth Engine export requires the 'rle-python-gee' package. "
                "Install it with: pip install rle-python-gee"
            ) from None

        return upload_gdf_to_ee_asset(
            self.polygons, asset_id,
            gcs_bucket=gcs_bucket, description="aoo_grid_polygons_export"
        )

    def to_parquet(self, path) -> None:
        """Write intersection polygons as a GeoParquet file."""
        from rle.core.ecosystems import _write_parquet
        _write_parquet(self.polygons, path)

    # -- visualization -------------------------------------------------------

    def to_layer(self, *, get_fill_color=None, get_line_color=None):
        """Return lonboard layer(s) for the intersection polygons."""
        if not self._computed:
            raise AOOGridPolygonsNotComputedError()
        try:
            from lonboard import PolygonLayer
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        if get_fill_color is None:
            get_fill_color = [0, 128, 255, 128]
        if get_line_color is None:
            get_line_color = [0, 0, 0, 255]

        gdf = self.polygons
        if gdf.empty:
            return []
        if len(gdf) > 1000:
            raise ValueError(
                f"Dataset has {len(gdf):,} polygons, which is too many to "
                f"display interactively. Export to parquet with "
                f".polygons.to_parquet(path) instead."
            )
        return [PolygonLayer.from_geopandas(
            gdf,
            get_fill_color=get_fill_color,
            get_line_color=get_line_color,
            line_width_min_pixels=1,
        )]

    def to_gdf_for_viz(self, *, get_fill_color=None, get_line_color=None, **_):
        """Return (gdf, style_dict) for static-image fallback rendering."""
        if not self._computed:
            raise AOOGridPolygonsNotComputedError()
        if get_fill_color is None:
            get_fill_color = [0, 128, 255, 128]
        if get_line_color is None:
            get_line_color = [0, 0, 0, 255]
        return self.polygons, {"fill": get_fill_color, "edge": get_line_color}

    def to_map(self, *, get_fill_color=None, get_line_color=None, **kwargs):
        """Return a lonboard Map of the intersection polygons."""
        try:
            from lonboard import Map
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        layer_kwargs = {}
        if get_fill_color is not None:
            layer_kwargs["get_fill_color"] = get_fill_color
        if get_line_color is not None:
            layer_kwargs["get_line_color"] = get_line_color
        try:
            layers = self.to_layer(**layer_kwargs)
        except ValueError as e:
            from IPython.display import HTML, display
            display(HTML(f"<div style='padding:12px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px'>"
                         f"<b>Cannot display map:</b> {e}</div>"))
            return None
        return Map(layers=layers, **kwargs)


class FilteredAOOGridPolygons(AOOGridPolygons):
    """A filtered view of AOOGridPolygons, showing only polygons matching a predicate."""

    def __init__(self, source: AOOGridPolygons, mask):
        self._source = source
        self._mask = mask
        self._computed = source._computed
        self._polygons = None
        self._aoo_grid = source._aoo_grid

    def _compute(self):
        raise RuntimeError(
            "Cannot compute a filtered polygon set — compute the source first."
        )

    def _load_polygons(self):
        return self._source.polygons[self._mask].reset_index(drop=True)


class AOOGridPolygonVectorLocal(AOOGridPolygons):
    """Intersection polygons computed locally via shapely.

    Intersects each grid cell with ecosystem features one at a time
    to keep memory usage bounded.
    """

    def _compute(self) -> None:
        import math
        import pandas as pd
        from shapely.geometry import box
        from rle.core.aoo_grid import AOO_CRS, AOO_CELL_SIZE

        eco = self._aoo_grid._ecosystems.load()
        if eco.crs is None:
            eco = eco.set_crs("EPSG:4326")
        eco_cea = eco.to_crs(AOO_CRS)

        bounds_cea = eco_cea.total_bounds
        sindex = eco_cea.sindex

        col_min = math.floor(bounds_cea[0] / AOO_CELL_SIZE)
        col_max = math.ceil(bounds_cea[2] / AOO_CELL_SIZE)
        row_min = math.floor(bounds_cea[1] / AOO_CELL_SIZE)
        row_max = math.ceil(bounds_cea[3] / AOO_CELL_SIZE)

        chunks = []
        for col in range(col_min, col_max):
            for row in range(row_min, row_max):
                x0 = col * AOO_CELL_SIZE
                y0 = row * AOO_CELL_SIZE
                cell = box(x0, y0, x0 + AOO_CELL_SIZE, y0 + AOO_CELL_SIZE)

                candidates = list(sindex.query(cell))
                if not candidates:
                    continue

                subset = eco_cea.iloc[candidates]
                intersections = subset.intersection(cell)
                mask = ~intersections.is_empty
                if not mask.any():
                    continue

                result = subset.loc[mask].copy()
                result["geometry"] = intersections[mask]
                result["grid_col"] = col
                result["grid_row"] = row
                chunks.append(result)

        if chunks:
            self._computed_gdf = gpd.GeoDataFrame(
                pd.concat(chunks, ignore_index=True), crs=AOO_CRS
            )
        else:
            self._computed_gdf = gpd.GeoDataFrame(
                columns=["geometry", "grid_col", "grid_row"]
            )

    def _load_polygons(self) -> gpd.GeoDataFrame:
        return self._computed_gdf


def make_aoo_polygons(aoo_grid: AOOGrid, **kwargs) -> AOOGridPolygons:
    """Create AOO grid polygons from an AOOGrid instance.

    Args:
        aoo_grid: A computed local AOOGrid instance. For Earth Engine grids,
            use the ``rle.gee`` backend's ``.to_polygons()`` method.
        **kwargs: Additional arguments passed to the backend constructor.

    Returns:
        An AOOGridPolygons instance. Call .compute() to run.
    """
    if isinstance(aoo_grid, AOOGridVectorLocal):
        return AOOGridPolygonVectorLocal(aoo_grid, **kwargs)
    raise ValueError(
        f"AOOGridPolygons not supported for {type(aoo_grid).__name__}. "
        f"For Earth Engine grids, use the rle.gee backend's .to_polygons()."
    )

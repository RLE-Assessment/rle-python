"""Ecosystem distribution data sources for RLE assessments.

Provides the ``Ecosystems`` class hierarchy for loading ecosystem data from
local and cloud-file backends (GeoJSON, GeoParquet — including ``gs://`` and
``s3://`` via fsspec — and COGs).

Earth Engine backends live in the optional ``rle-python-gee`` package
(``rle.gee``). Construct them explicitly, e.g.::

    from rle.gee import GeeEcosystems
    eco = GeeEcosystems("projects/my-project/assets/ecosystems")
"""

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import Any


def _natural_key(s: str) -> list:
    """Sort key that orders numeric parts numerically (e.g. T1.1.2 before T1.1.10)."""
    return [int(part) if part.isdigit() else part.lower()
            for part in re.split(r'(\d+)', s)]


def _write_parquet(gdf, path) -> None:
    """Write a GeoDataFrame to a GeoParquet file (local or gs://)."""
    path_str = str(path)
    if path_str.startswith("gs://"):
        bucket = path_str.split("/")[2]
        try:
            gdf.to_parquet(path_str)
        except FileNotFoundError as exc:
            msg = str(exc)
            if "does not exist" in msg:
                raise FileNotFoundError(
                    f"GCS bucket '{bucket}' not found. "
                    f"Create it with:  gcloud storage buckets create gs://{bucket}"
                ) from None
            raise FileNotFoundError(
                f"Failed to write to {path_str!r}: {msg}"
            ) from None
        except ImportError:
            raise ImportError(
                "The 'gcsfs' package is required to write to GCS. "
                "Install it with:  pip install rle-python[gcs]"
            ) from None
    else:
        from pathlib import Path
        Path(path_str).parent.mkdir(parents=True, exist_ok=True)
        gdf.to_parquet(path_str)


class EcosystemKind(Enum):
    VECTOR_LOCAL = "vector_local"
    RASTER_LOCAL = "raster_local"
    EE_FEATURE_COLLECTION = "ee_fc"
    EE_IMAGE = "ee_image"


class Ecosystems(ABC):
    """Base class for ecosystem distribution datasets."""

    def __init__(self, data, *, ecosystem_column: str | None = None,
                 ecosystem_name_column: str | None = None,
                 functional_group_column: str | None = None):
        self._data = data
        self._cached = None
        self.ecosystem_column = ecosystem_column
        self.ecosystem_name_column = ecosystem_name_column
        self.functional_group_column = functional_group_column

    @property
    @abstractmethod
    def kind(self) -> EcosystemKind: ...

    @abstractmethod
    def _load(self) -> Any: ...

    def load(self) -> Any:
        """Load and cache the ecosystem data. Returns the native object."""
        if self._cached is None:
            self._cached = self._load()
        return self._cached

    def _require_column(self, data, column: str, role: str) -> None:
        """Raise a clear error if a configured column is missing from the data.

        Lists the available column names so the caller can pick a valid one.
        A no-op for backends whose loaded object has no ``columns`` (e.g. rasters).
        """
        columns = getattr(data, "columns", None)
        if columns is not None and column not in columns:
            available = ", ".join(map(str, columns))
            raise ValueError(
                f"{role}={column!r} is not a column in the ecosystem data. "
                f"Available columns: {available}"
            )

    @property
    def geometry(self):
        """Return the geometry column of the loaded data."""
        data = self.load()
        return data.geometry

    def head(self, n: int = 5):
        """Return the first n rows of the loaded data."""
        data = self.load()
        if hasattr(data, 'head'):
            return data.head(n)
        return data

    def size(self) -> int:
        """Return the number of features."""
        data = self.load()
        if hasattr(data, '__len__'):
            return len(data)
        raise NotImplementedError(
            f"size not supported for {self.kind.value}"
        )

    def limit(self, n: int) -> "Ecosystems":
        """Return a new Ecosystems with only the first n features."""
        data = self.load()
        if hasattr(data, 'iloc'):
            return EcosystemsGeoDataFrame(data.iloc[:n], ecosystem_column=self.ecosystem_column,
                                         ecosystem_name_column=self.ecosystem_name_column,
                                         functional_group_column=self.functional_group_column)
        raise NotImplementedError(
            f"limit not supported for {self.kind.value}"
        )

    def unique_ecosystems(self) -> list[str]:
        """Return a naturally sorted list of unique ecosystem values."""
        if self.ecosystem_column is None:
            raise ValueError("ecosystem_column is not set")
        data = self.load()
        if hasattr(data, '__getitem__'):
            self._require_column(data, self.ecosystem_column, "ecosystem_column")
            return sorted(data[self.ecosystem_column].unique(), key=_natural_key)
        raise NotImplementedError(
            f"unique_ecosystems not supported for {self.kind.value}"
        )

    def unique_functional_groups(self) -> list[str]:
        """Return a naturally sorted list of unique functional group values."""
        if self.functional_group_column is None:
            raise ValueError("functional_group_column is not set")
        data = self.load()
        if hasattr(data, '__getitem__'):
            self._require_column(data, self.functional_group_column,
                                 "functional_group_column")
            return sorted(data[self.functional_group_column].unique(), key=_natural_key)
        raise NotImplementedError(
            f"unique_functional_groups not supported for {self.kind.value}"
        )

    def ecosystem_name(self, code: str) -> str:
        """Look up the human-readable name for an ecosystem code.

        Requires ``ecosystem_name_column`` to be set.
        """
        if self.ecosystem_name_column is None:
            raise ValueError("ecosystem_name_column is not set")
        if self.ecosystem_column is None:
            raise ValueError("ecosystem_column is not set")
        data = self.load()
        self._require_column(data, self.ecosystem_column, "ecosystem_column")
        self._require_column(data, self.ecosystem_name_column, "ecosystem_name_column")
        match = data.loc[data[self.ecosystem_column] == code, self.ecosystem_name_column]
        if match.empty:
            raise KeyError(f"Ecosystem code {code!r} not found")
        return match.iloc[0]

    def ecosystem_names(self) -> dict[str, str]:
        """Return a mapping of ecosystem codes to their names, sorted naturally by code.

        Requires ``ecosystem_name_column`` to be set.
        """
        if self.ecosystem_name_column is None:
            raise ValueError("ecosystem_name_column is not set")
        if self.ecosystem_column is None:
            raise ValueError("ecosystem_column is not set")
        data = self.load()
        self._require_column(data, self.ecosystem_column, "ecosystem_column")
        self._require_column(data, self.ecosystem_name_column, "ecosystem_name_column")
        pairs = data.drop_duplicates(subset=self.ecosystem_column)
        mapping = dict(zip(
            pairs[self.ecosystem_column],
            pairs[self.ecosystem_name_column],
        ))
        return {k: mapping[k] for k in sorted(mapping, key=_natural_key)}

    def filter(self, pattern: str, *, regex: bool = False) -> "Ecosystems":
        """Return a new Ecosystems containing only features matching the given value.

        Args:
            pattern: Exact value or regex pattern to match against the ecosystem column.
            regex: If True, treat pattern as a regular expression.

        Returns:
            A new Ecosystems object with only the matching features.
        """
        if self.ecosystem_column is None:
            raise ValueError("ecosystem_column is not set")
        data = self.load()
        if not hasattr(data, '__getitem__'):
            raise NotImplementedError(
                f"filter not supported for {self.kind.value}"
            )
        self._require_column(data, self.ecosystem_column, "ecosystem_column")
        if regex:
            mask = data[self.ecosystem_column].str.match(pattern)
        else:
            mask = data[self.ecosystem_column] == pattern
        return EcosystemsGeoDataFrame(data[mask], ecosystem_column=self.ecosystem_column,
                                     ecosystem_name_column=self.ecosystem_name_column,
                                     functional_group_column=self.functional_group_column)

    @property
    def aoo(self) -> int:
        """AOO cell count for this ecosystem. Cached after first access."""
        if not hasattr(self, '_aoo'):
            from rle.core.aoo import make_aoo_grid, slugify_ecosystem_name

            ecosystems = self.unique_ecosystems()
            if len(ecosystems) != 1:
                raise ValueError(
                    f"aoo requires exactly one ecosystem, "
                    f"but found {len(ecosystems)}. Filter first with "
                    f".filter('ecosystem_name')."
                )
            ecosystem_code = ecosystems[0]
            column = slugify_ecosystem_name(ecosystem_code)

            aoo_grid = make_aoo_grid(self).compute()
            filtered = aoo_grid.filter_by_ecosystem(ecosystem_code)
            gdf = filtered.grid_cells.sort_values(by=column)
            gdf["cumulative_fraction"] = gdf[column].cumsum()
            total = gdf["cumulative_fraction"].iloc[-1]
            gdf["cumulative_proportion"] = gdf["cumulative_fraction"] / total
            self._aoo = int(len(gdf[gdf["cumulative_proportion"] > 0.01]))
        return self._aoo

    @property
    def eoo(self) -> float:
        """EOO area in km². Cached after first access."""
        if not hasattr(self, '_eoo'):
            from rle.core.eoo import make_eoo
            self._eoo = make_eoo(self).compute().area_km2
        return self._eoo

    def to_raster(
        self,
        path,
        *,
        crs,
        scale,
        mode: str = "index",
        oversampling: int = 10,
        nodata=None,
    ) -> dict[int, str]:
        """Rasterize ecosystem polygons to a Cloud Optimized GeoTIFF.

        Two modes are supported:

        * ``mode="index"`` (default): single-band integer raster where each
          pixel holds the 1-based index of the ecosystem covering the
          pixel's center (rasterio's default ``all_touched=False``
          semantics). Indices follow the natural-sort order of
          ``unique_ecosystems()``. Where polygons overlap at a pixel
          center, the naturally-later code wins (rasterio's default
          ``MergeAlg.replace`` combined with our deterministic iteration
          order). Default nodata is the maximum value of the chosen
          output dtype (255 / 65535 / 4294967295).

        * ``mode="fraction"``: multi-band float32 raster with one band per
          ecosystem (also in natural-sort order). Each band stores the
          fraction of the pixel covered by that ecosystem in
          ``[0.0, 1.0]``, computed by rasterizing a binary mask at
          ``oversampling`` × per axis and averaging the resulting
          sub-pixels. Each band's description tag is set to its ecosystem
          code. Default nodata is ``NaN``.

        Args:
            path: Output COG path.
            crs: Target CRS (EPSG code, WKT, or pyproj CRS).
            scale: Pixel size in CRS units (meters for projected CRS).
            mode: ``"index"`` or ``"fraction"``.
            oversampling: Sub-pixel factor per axis for ``"fraction"``
                mode (1..255). Ignored in ``"index"`` mode.
            nodata: Nodata sentinel. Defaults to dtype-max in ``"index"``
                mode and ``NaN`` in ``"fraction"`` mode.

        Returns:
            Mapping of 1-based index (= band number in fraction mode) ->
            ecosystem code.
        """
        if self.kind != EcosystemKind.VECTOR_LOCAL:
            raise NotImplementedError(
                f"to_raster not supported for {self.kind.value}"
            )
        if mode not in ("index", "fraction"):
            raise ValueError(
                f"mode must be 'index' or 'fraction', got {mode!r}"
            )
        if mode == "fraction" and not (1 <= oversampling <= 255):
            raise ValueError("oversampling must be in [1, 255]")

        import json
        import math
        from pathlib import Path
        import numpy as np
        import rasterio
        from rasterio.features import rasterize as _rio_rasterize
        from rasterio.transform import from_origin
        import shapely

        Path(path).parent.mkdir(parents=True, exist_ok=True)

        # ---- Load + validate + reproject ----
        gdf = self.to_geodataframe()
        if gdf.empty:
            raise ValueError("Cannot rasterize empty ecosystem dataset")
        if gdf.crs is None:
            raise ValueError("Input GeoDataFrame has no CRS set")
        gdf = gdf.copy()
        gdf["geometry"] = shapely.make_valid(gdf.geometry)
        gdf = gdf.to_crs(crs)
        gdf = gdf[~(gdf.geometry.is_empty | gdf.geometry.isna())]
        if gdf.empty:
            raise ValueError("All geometries dropped after reprojection")

        codes = self.unique_ecosystems()  # naturally sorted
        n = len(codes)
        if n == 0:
            raise ValueError("No ecosystems to rasterize")
        code_to_index = {c: i for i, c in enumerate(codes, start=1)}
        mapping: dict[int, str] = {i: c for i, c in enumerate(codes, start=1)}
        ecosystem_col = self.ecosystem_column

        # ---- Snap target grid to pixel boundaries ----
        minx, miny, maxx, maxy = gdf.total_bounds
        minx = float(np.floor(minx / scale) * scale)
        miny = float(np.floor(miny / scale) * scale)
        maxx = float(np.ceil(maxx / scale) * scale)
        maxy = float(np.ceil(maxy / scale) * scale)
        W = int(round((maxx - minx) / scale))
        H = int(round((maxy - miny) / scale))
        transform = from_origin(minx, maxy, scale, scale)

        # ---- Mode dispatch ----
        if mode == "index":
            # dtype: indices 1..n + reserved nodata at dtype_max
            if n < 255:
                dtype = np.uint8
            elif n < 65535:
                dtype = np.uint16
            elif n < 4294967295:
                dtype = np.uint32
            else:
                raise ValueError(
                    f"Too many ecosystems ({n}) for to_raster"
                )
            dtype_str = np.dtype(dtype).name
            dtype_max = int(np.iinfo(dtype).max)
            if nodata is None:
                resolved_nodata = dtype_max
            else:
                resolved_nodata = int(nodata)
                if not (0 <= resolved_nodata <= dtype_max):
                    raise ValueError(
                        f"nodata={nodata} out of range for {dtype_str}"
                    )
                if 1 <= resolved_nodata <= n:
                    raise ValueError(
                        f"nodata={nodata} collides with valid ecosystem "
                        f"index 1..{n}"
                    )

            # All shapes in one rasterize call. Natural-sort order combined
            # with the default MergeAlg.replace means later codes win at
            # overlapping pixel centers.
            shapes = []
            for code in codes:
                idx = code_to_index[code]
                for geom in gdf.loc[gdf[ecosystem_col] == code, "geometry"]:
                    if geom is None or geom.is_empty:
                        continue
                    shapes.append((geom, idx))
            arr = _rio_rasterize(
                shapes=shapes,
                out_shape=(H, W),
                transform=transform,
                fill=resolved_nodata,
                dtype=dtype_str,
                all_touched=False,
            )
            count = 1
        else:  # mode == "fraction"
            if nodata is None:
                resolved_nodata = float("nan")
            else:
                resolved_nodata = float(nodata)
                if not (math.isnan(resolved_nodata)
                        or math.isfinite(resolved_nodata)):
                    raise ValueError(
                        f"nodata={nodata} must be finite or NaN"
                    )
            dtype_str = "float32"

            N = oversampling
            over_transform = from_origin(minx, maxy, scale / N, scale / N)
            over_shape = (H * N, W * N)
            inv_n2 = 1.0 / (N * N)

            arr = np.zeros((n, H, W), dtype=np.float32)
            for i, code in enumerate(codes, start=1):
                subset = gdf.loc[gdf[ecosystem_col] == code, "geometry"]
                if subset.empty:
                    continue
                mask = _rio_rasterize(
                    shapes=(
                        (geom, 1) for geom in subset if not geom.is_empty
                    ),
                    out_shape=over_shape,
                    transform=over_transform,
                    fill=0,
                    dtype="uint8",
                    all_touched=False,
                )
                cov = mask.reshape(H, N, W, N).sum(axis=(1, 3))
                arr[i - 1, :, :] = cov.astype(np.float32) * inv_n2
            count = n

        profile = {
            "driver": "COG",
            "dtype": dtype_str,
            "count": count,
            "height": H,
            "width": W,
            "crs": crs,
            "transform": transform,
            "nodata": resolved_nodata,
            "compress": "deflate",
            "predictor": 2 if mode == "index" else 3,
            "blocksize": 512,
            "overview_resampling": "nearest" if mode == "index" else "average",
            "BIGTIFF": "IF_SAFER",
        }
        with rasterio.open(path, "w", **profile) as dst:
            if mode == "index":
                dst.write(arr, 1)
            else:
                dst.write(arr)
                for i, code in mapping.items():
                    dst.set_band_description(i, code)
            dst.update_tags(
                ECOSYSTEM_COLUMN=ecosystem_col,
                ECOSYSTEM_INDEX_JSON=json.dumps(mapping),
                RASTERIZE_MODE=mode,
            )
            dst.update_tags(1, **{f"ECO_{i}": c for i, c in mapping.items()})

        return mapping

    def _feature_count(self) -> int | None:
        """Return the number of features, or None if not applicable."""
        if hasattr(self._cached, '__len__'):
            return len(self._cached)
        return None

    # -- export / write -------------------------------------------------------

    def to_geodataframe(self) -> "gpd.GeoDataFrame":
        """Convert to a GeoDataFrame.

        For vector local backends, returns the loaded GeoDataFrame directly.
        """
        import geopandas as gpd  # noqa: F401

        if self.kind == EcosystemKind.VECTOR_LOCAL:
            return self.load()
        raise NotImplementedError(
            f"to_geodataframe not supported for {self.kind.value}"
        )

    def to_parquet(self, path) -> None:
        """Write ecosystem data as a GeoParquet file."""
        _write_parquet(self.to_geodataframe(), path)

    def to_geojson(self, path) -> None:
        """Write ecosystem data as a GeoJSON file."""
        from pathlib import Path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        gdf = self.to_geodataframe()
        gdf.to_file(path, driver="GeoJSON")

    def to_ee_feature_collection(self, asset_id: str, *,
                                  gcs_bucket: str | None = None):
        """Upload ecosystem data as an Earth Engine asset.

        Requires the optional ``rle-python-gee`` package. Small datasets are
        uploaded inline; large datasets (> 1000 features) are written as a
        shapefile to GCS and ingested (requires ``gcs_bucket``).

        Returns the task/result, or None if asset already exists.
        """
        try:
            from rle.gee.upload import upload_gdf_to_ee_asset
        except ImportError:
            raise ImportError(
                "Earth Engine export requires the 'rle-python-gee' package. "
                "Install it with: pip install rle-python-gee"
            ) from None
        gdf = self.to_geodataframe()
        return upload_gdf_to_ee_asset(
            gdf, asset_id, gcs_bucket=gcs_bucket, description="ecosystem_export"
        )

    # -- visualization -------------------------------------------------------

    def to_layer(self, *, get_fill_color=None, get_line_color=None, max_features: int = 1000):
        """Return lonboard layer(s) for this ecosystem dataset.

        Args:
            get_fill_color: Fill color for polygons.
            get_line_color: Line color for polygons.
            max_features: Maximum number of features to display. Default 1000.
        """
        if self.kind != EcosystemKind.VECTOR_LOCAL:
            raise NotImplementedError(
                f"Visualization not yet supported for {self.kind.value}"
            )
        try:
            from lonboard import PolygonLayer
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        if get_fill_color is None:
            get_fill_color = [0, 255, 0, 128]
        if get_line_color is None:
            get_line_color = [0, 0, 0, 255]

        gdf = self.load()
        if gdf.empty:
            return []
        if len(gdf) > max_features:
            raise ValueError(
                f"Dataset has {len(gdf):,} features, exceeding max_features={max_features:,}. "
                f"Use .limit() or .filter() to reduce, increase max_features, "
                f"or upload to Earth Engine for tile-based visualization."
            )
        return [PolygonLayer.from_geopandas(
            gdf,
            get_fill_color=get_fill_color,
            get_line_color=get_line_color,
            line_width_min_pixels=1,
        )]

    def to_gdf_for_viz(self, *, get_fill_color=None, get_line_color=None, **_):
        """Return (gdf, style_dict) for static-image fallback rendering."""
        if self.kind != EcosystemKind.VECTOR_LOCAL:
            raise NotImplementedError(
                f"Static rendering not supported for {self.kind.value}"
            )
        if get_fill_color is None:
            get_fill_color = [0, 255, 0, 128]
        if get_line_color is None:
            get_line_color = [0, 0, 0, 255]
        return self.load(), {"fill": get_fill_color, "edge": get_line_color}

    def to_map(self, *, max_features: int = 1000, **kwargs):
        """Return a lonboard Map showing the ecosystem polygons.

        Args:
            max_features: Maximum number of features to display. Default 1000.
            **kwargs: Additional arguments passed to lonboard.Map.
        """
        try:
            from lonboard import Map
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        try:
            layers = self.to_layer(max_features=max_features)
        except ValueError as e:
            from IPython.display import HTML, display
            display(HTML(f"<div style='padding:12px;background:#fff3cd;border:1px solid #ffc107;border-radius:4px'>"
                         f"<b>Cannot display map:</b> {e}</div>"))
            return None
        return Map(layers=layers, **kwargs)

    # -- display -------------------------------------------------------------

    def __repr__(self) -> str:
        return f"{type(self).__name__}(data={self._data!r})"

    def _repr_html_(self) -> str:
        parts = [
            f"<b>{type(self).__name__}</b>",
            f"Kind: {self.kind.value}",
            f"Source: {self._data!r}",
        ]
        if self._cached is not None:
            count = self._feature_count()
            if count is not None:
                parts.append(f"Features: {count:,}")
        return "<br>".join(parts)

    # -- factory classmethods -------------------------------------------------

    @classmethod
    def from_file(cls, path, *, ecosystem_column: str, **kwargs) -> "Ecosystems":
        """Create from a vector file (Shapefile, GeoJSON, GeoParquet, etc.)."""
        if str(path).endswith(".parquet"):
            return EcosystemsGeoParquet(path, ecosystem_column=ecosystem_column, **kwargs)
        return EcosystemsFile(path, ecosystem_column=ecosystem_column, **kwargs)

    @classmethod
    def from_parquet(cls, path, *, ecosystem_column: str, **kwargs) -> "Ecosystems":
        """Create from a GeoParquet file."""
        return EcosystemsGeoParquet(path, ecosystem_column=ecosystem_column, **kwargs)

    @classmethod
    def from_cog(cls, data, **kwargs) -> "Ecosystems":
        """Create from a Cloud Optimized GeoTIFF."""
        return EcosystemsCOG(data, **kwargs)


# ---------------------------------------------------------------------------
# Vector local backends
# ---------------------------------------------------------------------------


class EcosystemsFile(Ecosystems):
    """Ecosystem polygons from a vector file (Shapefile, GeoJSON, etc.)."""

    kind = EcosystemKind.VECTOR_LOCAL

    def __init__(self, data, *, ecosystem_column: str, ecosystem_name_column: str | None = None,
                 functional_group_column: str | None = None):
        super().__init__(data, ecosystem_column=ecosystem_column,
                         ecosystem_name_column=ecosystem_name_column,
                         functional_group_column=functional_group_column)

    def _load(self):
        import geopandas as gpd

        return gpd.read_file(self._data)


class EcosystemsGeoParquet(Ecosystems):
    """Ecosystem polygons from a GeoParquet file (local, gs://, s3://, …)."""

    kind = EcosystemKind.VECTOR_LOCAL

    def __init__(self, data, *, ecosystem_column: str, ecosystem_name_column: str | None = None,
                 functional_group_column: str | None = None):
        super().__init__(data, ecosystem_column=ecosystem_column,
                         ecosystem_name_column=ecosystem_name_column,
                         functional_group_column=functional_group_column)

    def _load(self):
        import geopandas as gpd

        if isinstance(self._data, str) and self._data.startswith(
            ("http://", "https://", "gs://", "s3://", "az://")
        ):
            import fsspec

            with fsspec.open(self._data, "rb") as f:
                return gpd.read_parquet(f)
        return gpd.read_parquet(self._data)


class EcosystemsGeoDataFrame(Ecosystems):
    """Ecosystem polygons from an in-memory GeoDataFrame."""

    kind = EcosystemKind.VECTOR_LOCAL

    def __init__(self, data, *, ecosystem_column: str, ecosystem_name_column: str | None = None,
                 functional_group_column: str | None = None):
        super().__init__(data, ecosystem_column=ecosystem_column,
                         ecosystem_name_column=ecosystem_name_column,
                         functional_group_column=functional_group_column)
        self._cached = data

    def _load(self):
        return self._data


# ---------------------------------------------------------------------------
# Raster local backend
# ---------------------------------------------------------------------------


class EcosystemsCOG(Ecosystems):
    """Ecosystem coverage from a Cloud Optimized GeoTIFF."""

    kind = EcosystemKind.RASTER_LOCAL

    def _load(self):
        import rioxarray  # noqa: F401

        return rioxarray.open_rasterio(self._data)

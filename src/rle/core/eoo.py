"""Extent of Occurrence (EOO) computation for RLE assessments.

Provides the ``EOO`` class hierarchy and the ``make_eoo()`` helper for
computing EOO from a local ``Ecosystems`` instance. Earth Engine EOO support
lives in the optional ``rle-python-gee`` package.
"""

from abc import ABC, abstractmethod

from rle.core.ecosystems import (
    Ecosystems,
    EcosystemKind,
)


class EOONotComputedError(Exception):
    """Raised when accessing EOO results before compute() has been called."""

    def __init__(self):
        super().__init__(
            "EOO has not been computed yet. "
            "Call .compute() to run the computation."
        )


class EOO(ABC):
    """Base class for Extent of Occurrence computations.

    Subclasses implement ``_compute()`` to calculate the convex hull
    geometry and area.
    """

    def __init__(self, ecosystems: Ecosystems):
        self._ecosystems = ecosystems
        self._computed = False
        self._geometry = None
        self._area_km2: float | None = None
        self._crs = None

    @abstractmethod
    def _compute(self) -> None:
        """Run the EOO computation.

        Must store results so that ``_load_geometry()`` and
        ``_load_area_km2()`` can retrieve them.
        """
        ...

    @abstractmethod
    def _load_geometry(self):
        """Return the computed convex hull geometry."""
        ...

    @abstractmethod
    def _load_area_km2(self) -> float:
        """Return the EOO area in km²."""
        ...

    def compute(self) -> "EOO":
        """Run the EOO computation. Returns self for method chaining."""
        self._compute()
        self._computed = True
        self._geometry = None
        self._area_km2 = None
        return self

    @property
    def geometry(self):
        """The convex hull geometry. Raises EOONotComputedError if not computed."""
        if not self._computed:
            raise EOONotComputedError()
        if self._geometry is None:
            self._geometry = self._load_geometry()
        return self._geometry

    @property
    def area_km2(self) -> float:
        """EOO area in km²."""
        if not self._computed:
            raise EOONotComputedError()
        if self._area_km2 is None:
            self._area_km2 = self._load_area_km2()
        return self._area_km2

    # -- export / visualization ----------------------------------------------

    def to_geodataframe(self):
        """Return the convex hull as a single-row GeoDataFrame."""
        import geopandas as gpd

        return gpd.GeoDataFrame(
            {"area_km2": [self.area_km2]},
            geometry=[self.geometry],
            crs=self._crs,
        )

    def to_gdf_for_viz(self, *, get_fill_color=None, get_line_color=None, **_):
        """Return (gdf, style_dict) for static-image fallback rendering."""
        if get_fill_color is None:
            get_fill_color = [255, 0, 0, 40]
        if get_line_color is None:
            get_line_color = [255, 0, 0, 255]
        return self.to_geodataframe(), {"fill": get_fill_color, "edge": get_line_color}

    def to_layer(self, *, get_fill_color=None, get_line_color=None):
        """Return a lonboard PolygonLayer of the EOO convex hull."""
        gdf = self.to_geodataframe()
        if gdf.geometry.is_empty.all():
            return []

        try:
            from lonboard import PolygonLayer
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        if get_fill_color is None:
            get_fill_color = [255, 0, 0, 40]
        if get_line_color is None:
            get_line_color = [255, 0, 0, 255]

        return [PolygonLayer.from_geopandas(
            gdf,
            get_fill_color=get_fill_color,
            get_line_color=get_line_color,
            line_width_min_pixels=2,
        )]

    def to_map(self, **kwargs):
        """Return a lonboard Map showing the EOO convex hull."""
        try:
            from lonboard import Map
        except ImportError:
            raise ImportError(
                "lonboard is required for visualization. "
                "Install it with: pip install rle-python[viz]"
            ) from None

        return Map(layers=self.to_layer(), **kwargs)

    # -- display -------------------------------------------------------------

    def __repr__(self) -> str:
        if not self._computed:
            return f"{type(self).__name__}(not computed)"
        return (
            f"{type(self).__name__}("
            f"area_km2={self.area_km2:,.0f})"
        )

    def _repr_html_(self) -> str:
        if not self._computed:
            return (
                f"<b>{type(self).__name__}</b><br>"
                f"<i>Not computed — call .compute() to run</i>"
            )
        return (
            f"<b>{type(self).__name__}</b><br>"
            f"EOO: {self.area_km2:,.0f} km²"
        )


class EOOVectorLocal(EOO):
    """EOO from a local vector dataset (GeoDataFrame, GeoJSON, GeoParquet)."""

    def _compute(self) -> None:
        import geopandas as gpd

        gdf = self._ecosystems.to_geodataframe()

        self._crs = gdf.crs or "EPSG:4326"

        # Union all geometries, then compute convex hull
        union = gdf.geometry.union_all()
        hull = union.convex_hull

        # Degenerate inputs (single point, collinear points, empty) produce
        # Point/LineString/GeometryCollection which lonboard cannot render.
        geom_type = hull.geom_type if hull is not None and not hull.is_empty else None
        if geom_type not in ("Polygon", "MultiPolygon"):
            from shapely import Polygon
            if hull is None or hull.is_empty:
                hull = Polygon()
            else:
                hull = hull.buffer(0.0001)

        self._computed_geometry = hull

        # Compute area in km² using equal-area projection (ESRI:54034)
        hull_gdf = gpd.GeoDataFrame(geometry=[hull], crs=self._crs)
        hull_ea = hull_gdf.to_crs("ESRI:54034")
        self._computed_area = hull_ea.geometry.iloc[0].area / 1e6

    def _load_geometry(self):
        return self._computed_geometry

    def _load_area_km2(self) -> float:
        return self._computed_area


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def make_eoo(data, **kwargs) -> EOO:
    """Create an EOO from an ``Ecosystems`` instance.

    Call ``.compute()`` to run the computation before accessing results.

    Args:
        data: An ``Ecosystems`` instance. For local vector data this returns
            an :class:`EOOVectorLocal`. Earth Engine ecosystems require the
            ``rle-python-gee`` package; construct the EE EOO backend
            explicitly from ``rle.gee``.
        **kwargs: Additional arguments passed to the backend constructor.

    Returns:
        An EOO instance. Call .compute() to run the computation.

    Example:
        >>> from rle.core import Ecosystems
        >>> eco = Ecosystems.from_file("ecosystems.geojson", ecosystem_column="ECO_NAME")
        >>> eoo = make_eoo(eco).compute()
        >>> print(eoo.area_km2)
    """
    if isinstance(data, Ecosystems):
        kind = data.kind
        if kind == EcosystemKind.VECTOR_LOCAL:
            return EOOVectorLocal(data, **kwargs)
        if kind in (EcosystemKind.EE_FEATURE_COLLECTION, EcosystemKind.EE_IMAGE):
            raise ValueError(
                f"EOO for {kind.value} requires the 'rle-python-gee' package. "
                f"Install it and construct the Earth Engine EOO backend from rle.gee."
            )
        raise ValueError(f"EOO not yet supported for {kind.value}")

    raise TypeError(
        "make_eoo expects an Ecosystems instance. Construct one first, e.g. "
        "Ecosystems.from_file(path, ecosystem_column=...) or a backend from rle.gee."
    )

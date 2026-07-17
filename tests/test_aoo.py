"""Tests for the AOO grid module (local backends)."""

from pathlib import Path

import pytest
import geopandas as gpd
from shapely.geometry import box
from unittest.mock import patch, MagicMock

from rle.core.aoo import (
    AOOGrid,
    AOOGridCOG,
    AOOGridNotComputedError,
    AOOGridPolygons,
    AOOGridPolygonsNotComputedError,
    AOOGridVectorLocal,
    make_aoo_grid,
    make_aoo_grid_cached,
    make_aoo_polygons,
)
from rle.core.ecosystems import (
    Ecosystems,
    EcosystemKind,
    EcosystemsFile,
    EcosystemsGeoDataFrame,
)
from rle.core.aoo_grid import AOO_CRS, AOO_CELL_SIZE


# ---------------------------------------------------------------------------
# Concrete subclass for testing base class logic
# ---------------------------------------------------------------------------


class FakeEcosystems(Ecosystems):
    """Minimal concrete Ecosystems subclass for testing."""
    kind = EcosystemKind.VECTOR_LOCAL

    def _load(self):
        return self._data


class FakeAOOGrid(AOOGrid):
    """Minimal concrete subclass for testing AOOGrid base class."""

    def __init__(self, grid_cells_gdf, **kwargs):
        super().__init__(ecosystems=FakeEcosystems(None), **kwargs)
        self._fake_gdf = grid_cells_gdf

    def _compute(self) -> None:
        self._computed_gdf = self._fake_gdf

    def _load_grid_cells(self) -> gpd.GeoDataFrame:
        return self._computed_gdf


def _make_test_gdf(n: int = 3) -> gpd.GeoDataFrame:
    """Create a test GeoDataFrame with grid cell geometries."""
    cells = [box(i, 0, i + 0.1, 0.1) for i in range(n)]
    return gpd.GeoDataFrame(
        {"geometry": cells},
        crs="EPSG:4326",
    )


# ---------------------------------------------------------------------------
# Base class tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAOOGridBase:
    """Tests for AOOGrid base class properties and methods."""

    def test_cell_count(self):
        gdf = _make_test_gdf(3)
        aoo = FakeAOOGrid(gdf).compute()
        assert aoo.cell_count == 3

    def test_aoo_km2(self):
        """AOO should be cell_count * 100 km²."""
        gdf = _make_test_gdf(1)
        aoo = FakeAOOGrid(gdf).compute()
        assert aoo.aoo_km2 == aoo.cell_count * 100

    def test_repr(self):
        gdf = _make_test_gdf(1)
        aoo = FakeAOOGrid(gdf).compute()
        r = repr(aoo)
        assert "FakeAOOGrid" in r
        assert "cell_count=" in r

    def test_repr_html(self):
        gdf = _make_test_gdf(1)
        aoo = FakeAOOGrid(gdf).compute()
        html = aoo._repr_html_()
        assert "FakeAOOGrid" in html
        assert "km²" in html

    def test_not_computed_raises(self):
        """Accessing grid_cells before compute() should raise."""
        gdf = _make_test_gdf(1)
        aoo = FakeAOOGrid(gdf)
        with pytest.raises(AOOGridNotComputedError, match="Call .compute()"):
            _ = aoo.grid_cells

    def test_cell_count_raises_before_compute(self):
        aoo = FakeAOOGrid(_make_test_gdf(1))
        with pytest.raises(AOOGridNotComputedError):
            _ = aoo.cell_count

    def test_aoo_km2_raises_before_compute(self):
        aoo = FakeAOOGrid(_make_test_gdf(1))
        with pytest.raises(AOOGridNotComputedError):
            _ = aoo.aoo_km2

    def test_repr_before_compute(self):
        aoo = FakeAOOGrid(_make_test_gdf(1))
        r = repr(aoo)
        assert "not computed" in r

    def test_repr_html_before_compute(self):
        aoo = FakeAOOGrid(_make_test_gdf(1))
        html = aoo._repr_html_()
        assert "Not computed" in html

    def test_compute_returns_self(self):
        gdf = _make_test_gdf(1)
        aoo = FakeAOOGrid(gdf)
        result = aoo.compute()
        assert result is aoo


# ---------------------------------------------------------------------------
# Factory function tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMakeAooFactory:
    """Tests for the make_aoo_grid factory function."""

    def test_ecosystems_instance(self):
        """make_aoo_grid should accept an Ecosystems instance directly."""
        eco = EcosystemsFile("/fake/path.geojson", ecosystem_column='ECO_NAME')
        aoo = make_aoo_grid(eco)
        assert isinstance(aoo, AOOGridVectorLocal)

    def test_raw_path_raises_typeerror(self):
        """make_aoo_grid no longer accepts raw paths."""
        with pytest.raises(TypeError, match="Ecosystems instance"):
            make_aoo_grid("/fake/path.parquet", ecosystem_column='ECO_NAME')

    def test_ee_kind_raises_pointing_to_gee(self):
        """EE-kind ecosystems require the rle-python-gee package."""

        class FakeEEEcosystems(Ecosystems):
            kind = EcosystemKind.EE_IMAGE
            def _load(self):
                return None

        eco = FakeEEEcosystems("fake", ecosystem_column='eco')
        with pytest.raises(ValueError, match="rle-python-gee"):
            make_aoo_grid(eco)


# ---------------------------------------------------------------------------
# Classmethod tests (local backends only)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestAOOGridClassmethods:
    """Tests for AOOGrid.from_*() classmethods."""

    def test_from_parquet(self):
        aoo = AOOGrid.from_parquet("/fake/path.parquet", ecosystem_column='ECO_NAME')
        assert isinstance(aoo, AOOGridVectorLocal)

    def test_from_file(self):
        aoo = AOOGrid.from_file("/fake/path.geojson", ecosystem_column='ECO_NAME')
        assert isinstance(aoo, AOOGridVectorLocal)

    def test_from_cog(self):
        aoo = AOOGrid.from_cog("/fake/path.tif")
        assert isinstance(aoo, AOOGridCOG)


# ---------------------------------------------------------------------------
# GeoJSON backend tests
# ---------------------------------------------------------------------------

GEOJSON_PATH = Path(__file__).parent / "test_data" / "null_island.geojson"


@pytest.mark.unit
class TestAOOGridGeoJSON:
    def test_grid_cells_non_empty(self):
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME').compute()
        assert len(aoo.grid_cells) > 0

    def test_cell_count(self):
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME').compute()
        assert aoo.cell_count > 0

    def test_aoo_km2(self):
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME').compute()
        assert aoo.aoo_km2 > 0

    def test_via_ecosystems(self):
        """Constructing via Ecosystems should produce the same result."""
        eco = Ecosystems.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        aoo = make_aoo_grid(eco).compute()
        assert isinstance(aoo, AOOGridVectorLocal)
        assert aoo.cell_count > 0

    def test_ecosystem_fraction_columns(self):
        """Grid cells should have fraction columns for each ecosystem."""
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME').compute()
        assert 'Null_Island_Tropical_Forest' in aoo.grid_cells.columns
        assert 'Null_Island_Alpine_Grassland' in aoo.grid_cells.columns
        assert 'Null_Island_Marine_Shelf' in aoo.grid_cells.columns

    def test_to_polygons(self):
        """to_polygons().compute() should produce intersection polygons."""
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME').compute()
        polygons = aoo.to_polygons().compute()
        assert polygons.polygon_count > 0
        gdf = polygons.polygons
        assert "grid_col" in gdf.columns
        assert "grid_row" in gdf.columns
        assert "ECO_NAME" in gdf.columns

    def test_to_polygons_via_make_aoo_polygons(self):
        """make_aoo_polygons should work for local vector grids."""
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME').compute()
        polygons = make_aoo_polygons(aoo).compute()
        assert polygons.polygon_count > 0


# ---------------------------------------------------------------------------
# Characterization tests for AOOGridVectorLocal._compute
#
# These lock the exact output contract so the vectorized/low-memory refactor
# of _compute cannot silently change any assessment number.
# ---------------------------------------------------------------------------

GOLDEN_PATH = (
    Path(__file__).parent / "test_data" / "aoo_grid_null_island_golden.parquet"
)


def _area_ea(geom) -> float:
    """Area of a single EPSG:4326 geometry in the AOO equal-area CRS (m²)."""
    return (
        gpd.GeoDataFrame(geometry=[geom], crs="EPSG:4326")
        .to_crs(AOO_CRS)
        .geometry.area.iloc[0]
    )


@pytest.mark.unit
class TestAOOGridVectorLocalCompute:
    """Byte-level and semantic characterization of _compute output."""

    def test_matches_golden_snapshot(self):
        """Output must equal the committed golden snapshot exactly."""
        from geopandas.testing import assert_geodataframe_equal

        golden = gpd.read_parquet(GOLDEN_PATH)
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column="ECO_NAME").compute()
        result = aoo.grid_cells

        assert list(result.columns) == list(golden.columns)
        assert result.crs == golden.crs
        assert_geodataframe_equal(result, golden, check_dtype=False)

    def test_single_feature_counts_one_per_cell(self):
        """A single ecosystem feature spanning many cells: every cell counts 1."""
        from shapely.geometry import box

        # ~55 km box near (0.5, 0.5) — spans several 10 km cells, away from origin.
        feature = box(0.30, 0.30, 0.80, 0.80)
        gdf = gpd.GeoDataFrame(
            {"ECO_NAME": ["eco_solo"], "geometry": [feature]}, crs="EPSG:4326"
        )
        eco = EcosystemsGeoDataFrame(gdf, ecosystem_column="ECO_NAME")
        cells = AOOGridVectorLocal(eco).compute().grid_cells

        assert (cells["count_geoms"] == 1).all()
        assert (cells["count_ecosystems"] == 1).all()
        assert "eco_solo" in cells.columns
        # Fractional area is conserved: sum over cells == feature_area / cell_area.
        expected = _area_ea(feature) / (AOO_CELL_SIZE * AOO_CELL_SIZE)
        assert cells["eco_solo"].sum() == pytest.approx(expected, rel=1e-6)

    def test_same_ecosystem_fractions_sum_in_one_cell(self):
        """Two overlapping features of one ecosystem in a cell: fractions add."""
        from shapely.geometry import box

        # Two overlapping small boxes near (0.5, 0.5): both land in the SAME
        # 10 km cell (well inside cell [50000, 60000] in the equal-area CRS).
        a = box(0.500, 0.500, 0.502, 0.502)
        b = box(0.501, 0.501, 0.503, 0.503)
        # A different ecosystem placed in a DIFFERENT cell (~0.4°).
        c = box(0.400, 0.400, 0.402, 0.402)
        gdf = gpd.GeoDataFrame(
            {"ECO_NAME": ["eco_x", "eco_x", "eco_y"], "geometry": [a, b, c]},
            crs="EPSG:4326",
        )
        eco = EcosystemsGeoDataFrame(gdf, ecosystem_column="ECO_NAME")
        cells = AOOGridVectorLocal(eco).compute().grid_cells

        # eco_x occupies exactly one cell, hit by both features.
        eco_x_cells = cells[cells["eco_x"] > 0]
        assert len(eco_x_cells) == 1
        row = eco_x_cells.iloc[0]
        assert row["count_geoms"] == 2  # both features counted
        assert row["count_ecosystems"] == 1  # both are eco_x
        # Fractions summed (overlap counted twice, matching per-feature summation).
        expected = (_area_ea(a) + _area_ea(b)) / (AOO_CELL_SIZE * AOO_CELL_SIZE)
        assert row["eco_x"] == pytest.approx(expected, rel=1e-6)

    def test_chunked_intersection_matches_golden(self, monkeypatch):
        """Chunking the intersection must not change the result (chunk size 1)."""
        from geopandas.testing import assert_geodataframe_equal
        import rle.core.aoo as aoo_module

        # raising=True: fails until the chunk constant exists (drives the refactor).
        monkeypatch.setattr(aoo_module, "_AOO_INTERSECTION_CHUNK", 1)

        golden = gpd.read_parquet(GOLDEN_PATH)
        aoo = AOOGrid.from_file(GEOJSON_PATH, ecosystem_column="ECO_NAME").compute()
        assert_geodataframe_equal(aoo.grid_cells, golden, check_dtype=False)


# ---------------------------------------------------------------------------
# Backward-compatibility alias tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestBackwardCompatAliases:
    def test_geojson_alias(self):
        from rle.core.aoo import AOOGridGeoJSON
        assert AOOGridGeoJSON is AOOGridVectorLocal

    def test_geoparquet_alias(self):
        from rle.core.aoo import AOOGridGeoParquet
        assert AOOGridGeoParquet is AOOGridVectorLocal


# ---------------------------------------------------------------------------
# make_aoo_grid_cached tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMakeAOOGridCached:
    def test_cache_miss_writes_file(self, tmp_path):
        cache_path = tmp_path / "aoo.parquet"
        eco = Ecosystems.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        aoo = make_aoo_grid_cached(eco, cache_path=cache_path)
        assert cache_path.exists()
        assert len(aoo.grid_cells) > 0

    def test_cache_hit_skips_compute(self, tmp_path):
        cache_path = tmp_path / "aoo.parquet"
        eco = Ecosystems.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        first = make_aoo_grid_cached(eco, cache_path=cache_path)

        with patch.object(
            AOOGridVectorLocal, "_compute",
            side_effect=AssertionError("compute must not run on cache hit"),
        ):
            second = make_aoo_grid_cached(eco, cache_path=cache_path)

        assert len(second.grid_cells) == len(first.grid_cells)
        assert second.grid_cells.crs is not None

    def test_filter_works_after_cache_hit(self, tmp_path):
        cache_path = tmp_path / "aoo.parquet"
        eco = Ecosystems.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        make_aoo_grid_cached(eco, cache_path=cache_path)

        reloaded = make_aoo_grid_cached(eco, cache_path=cache_path)
        filtered = reloaded.filter_by_ecosystem('Null Island Tropical Forest')
        assert len(filtered.grid_cells) > 0

    def test_parent_dir_autocreated(self, tmp_path):
        cache_path = tmp_path / "nested" / "dirs" / "aoo.parquet"
        eco = Ecosystems.from_file(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        aoo = make_aoo_grid_cached(eco, cache_path=cache_path)
        assert cache_path.exists()
        assert len(aoo.grid_cells) > 0


# ---------------------------------------------------------------------------
# _remote_file_exists — cache existence checks
#
# gs:// caches are read/written via pyarrow's native GCS backend
# (gpd.read_parquet / to_parquet). The existence check must use the SAME
# backend, not fsspec — otherwise it silently returns False when gcsfs is not
# installed, the cache is never detected, and the grid is recomputed (OOM).
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRemoteFileExists:
    def test_gs_uri_uses_pyarrow_not_fsspec(self, monkeypatch):
        """gs:// existence works via pyarrow, with no gcsfs/fsspec dependency."""
        import pyarrow.fs as pafs
        import fsspec.core
        from rle.core.aoo import _remote_file_exists

        seen = {}

        class _Info:
            type = pafs.FileType.File

        class _FakeGCS:
            def get_file_info(self, path):
                seen["path"] = path
                return _Info()

        monkeypatch.setattr(pafs, "GcsFileSystem", lambda *a, **k: _FakeGCS())
        # Routing gs:// through fsspec would require gcsfs — forbid it.
        def _no_fsspec(*a, **k):
            raise AssertionError("gs:// must not go through fsspec")
        monkeypatch.setattr(fsspec.core, "url_to_fs", _no_fsspec)

        assert _remote_file_exists("gs://bucket/key.parquet") is True
        assert seen["path"] == "bucket/key.parquet"  # gs:// prefix stripped

    def test_gs_uri_missing_returns_false(self, monkeypatch):
        import pyarrow.fs as pafs
        from rle.core.aoo import _remote_file_exists

        class _Info:
            type = pafs.FileType.NotFound

        class _FakeGCS:
            def get_file_info(self, path):
                return _Info()

        monkeypatch.setattr(pafs, "GcsFileSystem", lambda *a, **k: _FakeGCS())
        assert _remote_file_exists("gs://bucket/missing.parquet") is False

    def test_local_path_still_works(self, tmp_path):
        from rle.core.aoo import _remote_file_exists
        p = tmp_path / "x.parquet"
        assert _remote_file_exists(str(p)) is False
        p.write_text("data")
        assert _remote_file_exists(str(p)) is True


# ---------------------------------------------------------------------------
# AOOGridPolygons base class tests
# ---------------------------------------------------------------------------


class FakeAOOGridPolygons(AOOGridPolygons):
    """Minimal concrete subclass for testing AOOGridPolygons base class."""

    def __init__(self, aoo_grid, polygons_gdf):
        super().__init__(aoo_grid)
        self._fake_polygons = polygons_gdf

    def _compute(self) -> None:
        self._computed_polygons = self._fake_polygons

    def _load_polygons(self) -> gpd.GeoDataFrame:
        return self._computed_polygons


def _make_test_polygons_gdf(n: int = 4) -> gpd.GeoDataFrame:
    """Create a test GeoDataFrame with intersection polygon geometries."""
    polys = [box(i * 0.05, 0, i * 0.05 + 0.03, 0.03) for i in range(n)]
    return gpd.GeoDataFrame(
        {
            "geometry": polys,
            "grid_col": [0, 0, 1, 1][:n],
            "grid_row": [0, 0, 0, 0][:n],
            "ecosystem": ["eco_a", "eco_b", "eco_a", "eco_c"][:n],
        },
        crs="EPSG:4326",
    )


@pytest.mark.unit
class TestAOOGridPolygonsBase:
    """Tests for AOOGridPolygons base class."""

    def _make(self, n=4):
        grid_gdf = _make_test_gdf(2)
        aoo = FakeAOOGrid(grid_gdf).compute()
        poly_gdf = _make_test_polygons_gdf(n)
        return FakeAOOGridPolygons(aoo, poly_gdf)

    def test_polygon_count(self):
        obj = self._make(4).compute()
        assert obj.polygon_count == 4

    def test_compute_returns_self(self):
        obj = self._make()
        result = obj.compute()
        assert result is obj

    def test_not_computed_raises(self):
        obj = self._make()
        with pytest.raises(AOOGridPolygonsNotComputedError, match="Call .compute()"):
            _ = obj.polygons

    def test_polygon_count_raises_before_compute(self):
        obj = self._make()
        with pytest.raises(AOOGridPolygonsNotComputedError):
            _ = obj.polygon_count

    def test_repr(self):
        obj = self._make().compute()
        r = repr(obj)
        assert "FakeAOOGridPolygons" in r
        assert "polygons=" in r

    def test_repr_runtime_error_fallback(self):
        obj = self._make().compute()
        obj._polygons = None
        obj._load_polygons = MagicMock(side_effect=RuntimeError("pending"))
        r = repr(obj)
        assert "results pending" in r

    def test_repr_before_compute(self):
        obj = self._make()
        r = repr(obj)
        assert "not computed" in r

    def test_repr_html(self):
        obj = self._make().compute()
        html = obj._repr_html_()
        assert "FakeAOOGridPolygons" in html
        assert "Polygons:" in html

    def test_repr_html_before_compute(self):
        obj = self._make()
        html = obj._repr_html_()
        assert "Not computed" in html


# ---------------------------------------------------------------------------
# make_aoo_polygons factory tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestMakeAooPolygonsFactory:
    def test_unsupported_type_raises(self):
        grid_gdf = _make_test_gdf(2)
        aoo = FakeAOOGrid(grid_gdf).compute()
        with pytest.raises(ValueError, match="not supported"):
            make_aoo_polygons(aoo)

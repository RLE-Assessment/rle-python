"""Tests for the Ecosystems class hierarchy (local backends)."""

from pathlib import Path

import pytest
import geopandas as gpd

from rle.core.ecosystems import (
    Ecosystems,
    EcosystemKind,
    EcosystemsFile,
    EcosystemsGeoParquet,
    EcosystemsCOG,
)

GEOJSON_PATH = Path(__file__).parent / "test_data" / "null_island.geojson"


# ---------------------------------------------------------------------------
# Subclass unit tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEcosystemsFile:
    def test_kind(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        assert eco.kind == EcosystemKind.VECTOR_LOCAL

    def test_load_returns_geodataframe(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        gdf = eco.load()
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0

    def test_load_caches(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        first = eco.load()
        second = eco.load()
        assert first is second


@pytest.mark.unit
class TestEcosystemsGeoParquet:
    def test_kind(self):
        eco = EcosystemsGeoParquet("/fake/path.parquet", ecosystem_column='ECO_NAME')
        assert eco.kind == EcosystemKind.VECTOR_LOCAL

    @staticmethod
    def _fixture(tmp_path):
        from shapely.geometry import box
        gdf = gpd.GeoDataFrame(
            {
                "ECO_NAME": ["a", "a", "b", "c"],
                "geometry": [box(i, i, i + 1, i + 1) for i in range(4)],
            },
            crs="EPSG:4326",
        )
        p = tmp_path / "eco.parquet"
        gdf.to_parquet(p)
        return p

    def test_filter_pushdown_avoids_full_load(self, tmp_path):
        """Exact-match filter reads only matching rows — never full-loads."""
        p = self._fixture(tmp_path)
        eco = EcosystemsGeoParquet(str(p), ecosystem_column="ECO_NAME")
        filtered = eco.filter("a")
        assert filtered.size() == 2
        assert set(filtered.load()["ECO_NAME"]) == {"a"}
        # The source parquet must not have been fully materialized/cached.
        assert eco._cached is None

    def test_filter_pushdown_matches_in_memory(self, tmp_path):
        """Pushdown filter returns the same rows as a full-load + mask."""
        from geopandas.testing import assert_geodataframe_equal
        p = self._fixture(tmp_path)
        ref = gpd.read_parquet(p)
        ref = ref[ref["ECO_NAME"] == "a"].reset_index(drop=True)
        eco = EcosystemsGeoParquet(str(p), ecosystem_column="ECO_NAME")
        got = eco.filter("a").load().reset_index(drop=True)
        assert_geodataframe_equal(got, ref, check_dtype=False)

    def test_filter_regex_falls_back_to_in_memory(self, tmp_path):
        """Regex filtering can't be pushed down — falls back to a full load."""
        p = self._fixture(tmp_path)
        eco = EcosystemsGeoParquet(str(p), ecosystem_column="ECO_NAME")
        filtered = eco.filter("a", regex=True)
        assert filtered.size() == 2
        assert eco._cached is not None  # full load happened


@pytest.mark.unit
class TestEcosystemsCOG:
    def test_kind(self):
        eco = EcosystemsCOG("/fake/path.tif")
        assert eco.kind == EcosystemKind.RASTER_LOCAL


# ---------------------------------------------------------------------------
# Factory classmethod tests (local backends only)
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEcosystemsClassmethods:
    def test_from_file(self):
        eco = Ecosystems.from_file("/path.geojson", ecosystem_column='ECO_NAME')
        assert isinstance(eco, EcosystemsFile)

    def test_from_parquet(self):
        eco = Ecosystems.from_parquet("/path.parquet", ecosystem_column='ECO_NAME')
        assert isinstance(eco, EcosystemsGeoParquet)

    def test_from_file_parquet_str(self):
        eco = Ecosystems.from_file("/path.parquet", ecosystem_column='ECO_NAME')
        assert isinstance(eco, EcosystemsGeoParquet)

    def test_from_file_parquet_path(self):
        # A pathlib.Path ending in .parquet must route to the GeoParquet
        # backend, not the OGR-based EcosystemsFile.
        eco = Ecosystems.from_file(Path("/path.parquet"), ecosystem_column='ECO_NAME')
        assert isinstance(eco, EcosystemsGeoParquet)

    def test_from_cog(self):
        eco = Ecosystems.from_cog("/path.tif")
        assert isinstance(eco, EcosystemsCOG)


# ---------------------------------------------------------------------------
# Removed-API guard
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestRemovedApis:
    def test_make_ecosystems_not_exported(self):
        """make_ecosystems is EE-only and must not be exposed by core."""
        import rle.core as core
        assert not hasattr(core, "make_ecosystems")


# ---------------------------------------------------------------------------
# Display and visualization tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEcosystemsDisplay:
    def test_repr(self):
        eco = EcosystemsFile("/path/to/file.geojson", ecosystem_column='ECO_NAME')
        r = repr(eco)
        assert "EcosystemsFile" in r
        assert "file.geojson" in r

    def test_repr_html(self):
        eco = EcosystemsFile("/path/to/file.geojson", ecosystem_column='ECO_NAME')
        html = eco._repr_html_()
        assert "EcosystemsFile" in html
        assert "vector_local" in html

    def test_to_layer_geojson(self):
        from lonboard import PolygonLayer

        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        layers = eco.to_layer()
        assert len(layers) == 1
        assert isinstance(layers[0], PolygonLayer)

    def test_to_map_geojson(self):
        from lonboard import Map

        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        m = eco.to_map()
        assert isinstance(m, Map)


# ---------------------------------------------------------------------------
# Export / write tests
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestEcosystemsExport:
    def test_to_geodataframe_geojson(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        gdf = eco.to_geodataframe()
        assert isinstance(gdf, gpd.GeoDataFrame)
        assert len(gdf) > 0

    def test_to_parquet(self, tmp_path):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        out = tmp_path / "output.parquet"
        eco.to_parquet(out)
        result = gpd.read_parquet(out)
        assert len(result) > 0
        assert result.geometry.is_valid.all()

    def test_to_geojson(self, tmp_path):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        out = tmp_path / "output.geojson"
        eco.to_geojson(out)
        result = gpd.read_file(out)
        assert len(result) > 0
        assert result.geometry.is_valid.all()

    def test_to_ee_feature_collection_requires_gee(self):
        """Core has no Earth Engine; export should point to rle-python-gee."""
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_NAME')
        with pytest.raises(ImportError, match="rle-python-gee"):
            eco.to_ee_feature_collection("projects/test/assets/output")


@pytest.mark.unit
class TestEcosystemsToRaster:
    # ---- index mode ----

    def test_index_mode_creates_cog(self, tmp_path):
        import json
        import numpy as np
        import rasterio

        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        out = tmp_path / "eco_index.tif"
        mapping = eco.to_raster(out, crs="ESRI:54034", scale=1000)

        assert out.exists()
        with rasterio.open(out) as src:
            # Rasterio reports driver as GTiff for any TIFF on read; the
            # COG layout shows up in IMAGE_STRUCTURE namespace tags.
            assert src.driver == "GTiff"
            assert src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
            assert src.count == 1
            assert src.dtypes[0] in ("uint8", "uint16", "uint32")
            assert src.nodata == np.iinfo(src.dtypes[0]).max
            arr = src.read(1)
            unique_vals = set(np.unique(arr).tolist())
            assert unique_vals - {src.nodata} <= set(mapping.keys())
            assert len(unique_vals - {src.nodata}) >= 1
            tags = src.tags()
            recovered = {
                int(k): v
                for k, v in json.loads(tags["ECOSYSTEM_INDEX_JSON"]).items()
            }
            assert recovered == mapping
            assert tags["RASTERIZE_MODE"] == "index"

    def test_index_value_at_known_location(self, tmp_path):
        import rasterio

        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        out = tmp_path / "eco_index.tif"
        mapping = eco.to_raster(out, crs="ESRI:54034", scale=1000)

        gdf = eco.to_geodataframe().to_crs("ESRI:54034")
        largest = gdf.geometry.iloc[gdf.geometry.area.argmax()]
        cx, cy = largest.centroid.x, largest.centroid.y
        with rasterio.open(out) as src:
            row, col = src.index(cx, cy)
            val = int(src.read(1)[row, col])
            assert val != src.nodata
        assert mapping[val] in eco.unique_ecosystems()

    def test_index_nodata_collision_rejected(self, tmp_path):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        with pytest.raises(ValueError, match="collides"):
            eco.to_raster(tmp_path / "x.tif", crs="ESRI:54034",
                          scale=1000, nodata=1)

    # ---- fraction mode ----

    def test_fraction_mode_creates_multiband_cog(self, tmp_path):
        import math
        import rasterio

        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        codes = eco.unique_ecosystems()
        out = tmp_path / "eco_frac.tif"
        mapping = eco.to_raster(out, crs="ESRI:54034", scale=1000,
                                mode="fraction", oversampling=10)

        assert out.exists()
        assert mapping == {i: c for i, c in enumerate(codes, start=1)}
        with rasterio.open(out) as src:
            assert src.driver == "GTiff"
            assert src.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
            assert src.count == len(codes)
            assert src.dtypes[0] == "float32"
            assert math.isnan(src.nodata)
            assert list(src.descriptions) == codes
            arr = src.read()
            assert arr.shape[0] == len(codes)
            assert float(arr.min()) >= 0.0
            assert float(arr.max()) <= 1.0
            assert any(b.sum() > 0 for b in arr)

    def test_fraction_band_sum_in_range(self, tmp_path):
        """For non-overlapping ecosystems, the sum across bands at each
        pixel must be in [0, 1]."""
        import rasterio

        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        out = tmp_path / "eco_frac.tif"
        eco.to_raster(out, crs="ESRI:54034", scale=1000,
                      mode="fraction", oversampling=10)
        with rasterio.open(out) as src:
            arr = src.read()
            band_sum = arr.sum(axis=0)
            assert float(band_sum.max()) <= 1.0 + 1e-6
            assert float(band_sum.max()) > 0.0

    def test_fraction_invalid_oversampling(self, tmp_path):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        with pytest.raises(ValueError, match="oversampling"):
            eco.to_raster(tmp_path / "x.tif", crs="ESRI:54034", scale=1000,
                          mode="fraction", oversampling=0)

    # ---- shared ----

    def test_invalid_mode(self, tmp_path):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        with pytest.raises(ValueError, match="mode must be"):
            eco.to_raster(tmp_path / "x.tif", crs="ESRI:54034",
                          scale=1000, mode="largest")


@pytest.mark.unit
class TestEcosystemsFunctionalGroupColumn:
    def test_functional_group_column_stored(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE',
                             functional_group_column='EFG1')
        assert eco.functional_group_column == 'EFG1'

    def test_functional_group_column_default_none(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        assert eco.functional_group_column is None

    def test_unique_functional_groups(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE',
                             functional_group_column='EFG1')
        groups = eco.unique_functional_groups()
        assert isinstance(groups, list)
        assert len(groups) == 3
        # Should be naturally sorted
        assert groups == ['M1.1', 'T1.1', 'T6.5']

    def test_unique_functional_groups_raises_without_column(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE')
        with pytest.raises(ValueError, match="functional_group_column is not set"):
            eco.unique_functional_groups()

    def test_threaded_through_filter(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE',
                             functional_group_column='EFG1')
        filtered = eco.filter('T1.1.1')
        assert filtered.functional_group_column == 'EFG1'

    def test_threaded_through_limit(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE',
                             functional_group_column='EFG1')
        limited = eco.limit(1)
        assert limited.functional_group_column == 'EFG1'


@pytest.mark.unit
class TestEcosystemsColumnValidation:
    """A missing configured column should raise a clear error that lists the
    available column names, instead of a bare pandas KeyError."""

    def test_unique_ecosystems_missing_column_lists_available(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='NOPE')
        with pytest.raises(ValueError) as excinfo:
            eco.unique_ecosystems()
        msg = str(excinfo.value)
        assert 'NOPE' in msg                 # names the bad column
        assert 'Available columns' in msg
        assert 'ECO_CODE' in msg             # lists a real column

    def test_unique_functional_groups_missing_column_lists_available(self):
        eco = EcosystemsFile(GEOJSON_PATH, ecosystem_column='ECO_CODE',
                             functional_group_column='NOPE')
        with pytest.raises(ValueError) as excinfo:
            eco.unique_functional_groups()
        msg = str(excinfo.value)
        assert 'NOPE' in msg
        assert 'Available columns' in msg
        assert 'EFG1' in msg

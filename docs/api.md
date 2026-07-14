---
title: API reference
---

# API reference

Everything below is importable from the top-level `rle.core` namespace unless
noted otherwise:

```python
from rle.core import Ecosystems, make_aoo_grid, make_eoo
```

The module version is available as `rle.core.__version__`.

---

## Data model

### `Ecosystems`

Abstract base class for ecosystem distribution datasets. Data is loaded lazily
and cached on first access.

Constructor arguments (shared by concrete subclasses): `data` (path, URI, or
GeoDataFrame), and keyword-only `ecosystem_column`, `ecosystem_name_column`,
`functional_group_column`.

Factory classmethods:

- `Ecosystems.from_file(path, *, ecosystem_column, **kwargs)` — vector file;
  `.parquet` routes to the GeoParquet backend, otherwise a generic vector file.
- `Ecosystems.from_parquet(path, *, ecosystem_column, **kwargs)` — GeoParquet
  (local, `gs://`, `s3://`, `http(s)://` via fsspec).
- `Ecosystems.from_cog(data, **kwargs)` — Cloud Optimized GeoTIFF.

Inspection and subsetting:

- `load()` — load and cache the native object (a GeoDataFrame for vector data).
- `head(n=5)` — first *n* rows.
- `size()` — number of features.
- `limit(n)` — new `Ecosystems` with only the first *n* features.
- `filter(pattern, *, regex=False)` — new `Ecosystems` matching the ecosystem
  column (exact value, or a regex when `regex=True`).
- `unique_ecosystems()` — naturally-sorted unique ecosystem values.
- `unique_functional_groups()` — naturally-sorted unique functional group values.
- `ecosystem_name(code)` — human-readable name for a code (needs
  `ecosystem_name_column`).
- `ecosystem_names()` — mapping of code → name, naturally sorted by code.
- `geometry` — the geometry column of the loaded data.

Derived metrics (single ecosystem; cached):

- `aoo` — AOO cell count after a 1%-cumulative-proportion trim. Requires exactly
  one ecosystem; `filter()` first.
- `eoo` — EOO area in km².

Export:

- `to_geodataframe()` — the loaded GeoDataFrame (vector backends).
- `to_parquet(path)` — write GeoParquet (local or `gs://`).
- `to_geojson(path)` — write GeoJSON.
- `to_raster(path, *, crs, scale, mode="index", oversampling=10, nodata=None)` —
  rasterize polygons to a COG. Returns a mapping of 1-based index → ecosystem
  code. See [](ecosystems.md#rasterization) for the `index` vs `fraction` modes.
- `to_ee_feature_collection(asset_id, *, gcs_bucket=None)` — upload as an Earth
  Engine asset (requires `rle-python-gee`).

Visualization (require the `viz` extra):

- `to_layer(*, get_fill_color=None, get_line_color=None, max_features=1000)`
- `to_map(*, max_features=1000, **kwargs)`

### `EcosystemKind`

Enum of backend kinds: `VECTOR_LOCAL`, `RASTER_LOCAL`, `EE_FEATURE_COLLECTION`,
`EE_IMAGE`.

### Concrete `Ecosystems` backends

- `EcosystemsFile(data, *, ecosystem_column, ...)` — Shapefile, GeoJSON, etc.
- `EcosystemsGeoParquet(data, *, ecosystem_column, ...)` — GeoParquet (local,
  `gs://`, `s3://`, `http(s)://`).
- `EcosystemsGeoDataFrame(data, *, ecosystem_column, ...)` — in-memory
  GeoDataFrame.
- `EcosystemsCOG(data, ...)` — Cloud Optimized GeoTIFF (`RASTER_LOCAL`).

---

## Extent of Occurrence (EOO)

### `make_eoo(data, **kwargs)`

Create an `EOO` from an `Ecosystems` instance. Local vector data returns an
`EOOVectorLocal`; Earth Engine kinds require `rle-python-gee`. Call `.compute()`
before reading results.

### `EOO`

Abstract base class for Extent of Occurrence computations.

- `compute()` → `EOO` — run the computation; returns self.
- `geometry` — the convex hull geometry (raises `EOONotComputedError` if not
  computed).
- `area_km2` — hull area in km² (equal-area `ESRI:54034`).
- `to_geodataframe()` — single-row GeoDataFrame with an `area_km2` column.
- `to_layer(...)` / `to_map(...)` — lonboard visualization of the hull.

### `EOOVectorLocal`

EOO from a local vector dataset (GeoDataFrame, GeoJSON, GeoParquet).

### `EOONotComputedError`

Raised when accessing EOO results before `compute()`.

---

## Area of Occupancy (AOO)

### `make_aoo_grid(data, **kwargs)`

Create an `AOOGrid` from an `Ecosystems` instance. `VECTOR_LOCAL` →
`AOOGridVectorLocal`; `RASTER_LOCAL` → `AOOGridCOG`; Earth Engine kinds require
`rle-python-gee`. Call `.compute()` before reading results.

### `make_aoo_grid_cached(data, *, cache_path, **kwargs)`

An `AOOGrid` backed by a GeoParquet cache at `cache_path` (local or `gs://`). On
a cache hit, loads the parquet and skips `compute()`; on a miss, computes and
writes the cache. Cache invalidation is the caller's responsibility.

### `make_aoo_polygons(aoo_grid, **kwargs)`

Create `AOOGridPolygons` (grid cell × ecosystem intersections) from a computed
local `AOOGrid`. For Earth Engine grids, use the `rle.gee` backend's
`.to_polygons()`.

### `slugify_ecosystem_name(name)`

Sanitize an ecosystem name into a valid DataFrame column name (non-alphanumeric
characters become `_`). Used to name the per-ecosystem fraction columns.

### `AOOGrid`

Abstract base class for AOO grid computations. Grid cells are 10×10 km
(`AOO_CELL_SIZE_M = 10_000`), 100 km² each.

Classmethods: `AOOGrid.from_file(...)`, `from_parquet(...)`, `from_cog(...)`.

- `compute()` → `AOOGrid` — run and store results; returns self.
- `grid_cells` — GeoDataFrame of occupied cells (raises
  `AOOGridNotComputedError` if not computed).
- `cell_count` — number of occupied cells.
- `aoo_km2` — `cell_count × 100` km².
- `filter_by_ecosystem(ecosystem_name, threshold=0.0)` — filtered view keeping
  cells where the ecosystem's fractional coverage exceeds `threshold`.
- `to_parquet(path)` — write grid cells as GeoParquet.
- `to_ee_feature_collection(asset_id, *, gcs_bucket=None)` — export to Earth
  Engine (requires `rle-python-gee`).
- `to_layer(...)` / `to_map(...)` — lonboard visualization.

### `AOOGridVectorLocal` / `AOOGridCOG`

Concrete AOO grids for local vector data (GeoJSON/GeoParquet) and Cloud
Optimized GeoTIFFs respectively.

### `AOOGridPolygons`

Abstract base for grid × ecosystem intersection polygons.

- `compute()` → `AOOGridPolygons`
- `polygons` — GeoDataFrame of intersections (raises
  `AOOGridPolygonsNotComputedError` if not computed).
- `polygon_count` — number of intersection polygons.
- `filter_by_ecosystem(ecosystem_name)` — filtered view.
- `to_parquet(path)`, `to_ee_feature_collection(...)`, `to_layer(...)`,
  `to_map(...)`.

### `AOOGridPolygonVectorLocal`

Intersection polygons computed locally via shapely.

### Errors

- `AOOGridNotComputedError`
- `AOOGridPolygonsNotComputedError`

---

## Ecosystem codes

Importable from `rle.core.ecosystem_codes` (not the top-level namespace).

### `assign_ecosystem_codes(gdf, *, fg_code_col, eco_name_col, eco_code_col)`

Return a copy of `gdf` with a new hierarchical ecosystem-code column. Within each
functional group, distinct ecosystem names are sorted alphabetically before
numbering (`T1.1` → `T1.1.1`, `T1.1.2`). Null functional group or name → null
code.

Raises `ValueError` if a source column is missing or the target column already
exists. Warns (`UserWarning`) when a generated code exceeds `SHAPEFILE_VALUE_LIMIT`
(10 characters). See [](ecosystem-codes.md).

---

## Backend registry

### `BackendInfo`

Frozen dataclass describing a backend: `name`, `cls`, `capability` (`"ecosystems"`
/ `"aoo"` / `"eoo"`), `distribution`, `can_handle`.

### `iter_backends()`

Return every `BackendInfo` advertised by installed `rle.backends` entry points.

### `list_backends()`

Return the sorted names of all installed backends.

---

## Command-line interface

The `rle` console script (`rle.core.cli:app`):

- `rle --version` / `rle -v` — print the version.
- `rle backends` — list installed data-access backends.

See [](cli-and-backends.md).

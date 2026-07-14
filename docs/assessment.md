---
title: Assessment metrics
kernelspec:
  name: python3
  display_name: 'Python 3'
---

# Assessment metrics — EOO & AOO

`rle-python` computes the two spatial metrics behind RLE **Criterion B**:
**Extent of Occurrence (EOO)** and **Area of Occupancy (AOO)**. Both are derived
from an [`Ecosystems`](ecosystems.md) object and both follow the same
`compute()` → read-results lifecycle.

```{code-cell} python
:tags: remove-cell

from rle.core import Ecosystems
eco = Ecosystems.from_file("data/null_island.geojson", ecosystem_column="ECO_NAME")
```

## Extent of Occurrence (EOO)

`make_eoo` builds the convex hull of the unioned ecosystem geometry and measures
its area in the IUCN equal-area projection `ESRI:54034` (World Cylindrical Equal
Area). It feeds **Criterion B1**.

```{code-cell} python
from rle.core import make_eoo

eoo = make_eoo(eco).compute()
print("EOO:", round(eoo.area_km2, 2), "km²")
```

The convex hull is available as geometry or as a single-row GeoDataFrame:

```{code-cell} python
hull_gdf = eoo.to_geodataframe()
hull_gdf[["area_km2"]]
```

Accessing `eoo.area_km2` or `eoo.geometry` before `compute()` raises
`EOONotComputedError`.

## Area of Occupancy (AOO)

`make_aoo_grid` overlays the standard RLE grid — 10×10 km cells
(`AOO_CELL_SIZE_M = 10_000`), each covering 100 km² — and keeps the cells that
intersect the ecosystem. It feeds **Criterion B2**.

```{code-cell} python
from rle.core import make_aoo_grid

aoo = make_aoo_grid(eco).compute()
print("occupied cells:", aoo.cell_count)
print("AOO:", aoo.aoo_km2, "km²")   # cell_count × 100 km²
```

### Grid cell attributes

`grid_cells` is a GeoDataFrame. Alongside `count_geoms` / `count_ecosystems`, it
carries one **fractional-area column per ecosystem**, named by sanitizing the
ecosystem value with `slugify_ecosystem_name` (non-alphanumeric characters → `_`):

```{code-cell} python
from rle.core import slugify_ecosystem_name

print([c for c in aoo.grid_cells.columns if c not in
       {"grid_col", "grid_row", "count_geoms", "count_ecosystems", "geometry"}])
print(slugify_ecosystem_name("Null Island Tropical Forest"))
```

### Filtering by ecosystem

`filter_by_ecosystem` returns a view containing only cells where an ecosystem's
fractional coverage exceeds a threshold (default `0.0`, i.e. any presence):

```{code-cell} python
forest_cells = aoo.filter_by_ecosystem("Null Island Tropical Forest")
print("forest cells:", forest_cells.cell_count)
```

### Rasters instead of vectors

When the source is a Cloud Optimized GeoTIFF, `make_aoo_grid` returns an
`AOOGridCOG`, which keeps cells whose zonal mean is non-zero. The derived
properties (`cell_count`, `aoo_km2`) and visualization methods are identical.

## Caching an AOO grid

Grid computation can be expensive on large datasets. `make_aoo_grid_cached`
backs the grid with a GeoParquet file: on a cache hit it loads the parquet and
skips `compute()`; on a miss it computes and writes the cache. Cache
invalidation is the caller's responsibility — delete the file when the source
changes.

```python
from rle.core import make_aoo_grid_cached

aoo = make_aoo_grid_cached(eco, cache_path="cache/aoo_grid.parquet")  # local or gs://
aoo.aoo_km2   # behaves exactly like make_aoo_grid(eco).compute()
```

## Intersection polygons

`make_aoo_polygons` cuts each grid cell against the ecosystem polygons, yielding
one row per (grid cell × ecosystem) intersection — useful for area-weighted
reporting or high-resolution display.

```{code-cell} python
from rle.core import make_aoo_polygons

polys = make_aoo_polygons(aoo).compute()
print("intersection polygons:", polys.polygon_count)
```

`filter_by_ecosystem(name)` narrows the polygon set, and `to_parquet(path)`
writes the result. (Interactive display via `to_map()` is capped at 1000
polygons — export to parquet for larger sets.)

## The compute lifecycle

Every metric class raises a dedicated error if results are read too early:

| Class                | Read too early raises              |
| -------------------- | ---------------------------------- |
| `EOO`                | `EOONotComputedError`              |
| `AOOGrid`            | `AOOGridNotComputedError`          |
| `AOOGridPolygons`    | `AOOGridPolygonsNotComputedError`  |

`compute()` returns `self`, so the common pattern is `make_*(eco).compute()`.

See [](concepts.md) for how EOO and AOO map onto the RLE criteria and threat
categories.

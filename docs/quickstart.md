---
title: Quickstart
kernelspec:
  name: python3
  display_name: 'Python 3'
---

# Quickstart

This page runs a full assessment end to end on a small bundled dataset,
`data/null_island.geojson` — three toy ecosystems centered on 0°N, 0°E (a
tropical forest, an alpine grassland, and a marine shelf).

## Load an ecosystem dataset

Every workflow starts with an `Ecosystems` object. The `ecosystem_column`
argument names the attribute that identifies each ecosystem type.

```{code-cell} python
from rle.core import Ecosystems

eco = Ecosystems.from_file(
    "data/null_island.geojson",
    ecosystem_column="ECO_NAME",
)
eco
```

Inspect what was loaded:

```{code-cell} python
print("features:", eco.size())
eco.unique_ecosystems()
```

`from_file` picks a backend from the file extension (GeoParquet routes to the
GeoParquet backend; everything else is read as a vector file). See
[](ecosystems.md) for the full data model.

## Area of Occupancy (AOO)

`make_aoo_grid` overlays the standard 10×10 km RLE grid on the ecosystem. Call
`.compute()` to run it, then read the derived properties.

```{code-cell} python
from rle.core import make_aoo_grid

aoo = make_aoo_grid(eco).compute()
print("occupied cells:", aoo.cell_count)
print("AOO:", aoo.aoo_km2, "km²")
```

Each occupied grid cell covers 100 km², so `aoo_km2` is simply
`cell_count × 100`. AOO feeds RLE **Criterion B2**.

## Extent of Occurrence (EOO)

`make_eoo` computes the convex hull of all occurrences and reports its area in an
equal-area projection.

```{code-cell} python
from rle.core import make_eoo

eoo = make_eoo(eco).compute()
print("EOO:", round(eoo.area_km2, 2), "km²")
```

EOO feeds RLE **Criterion B1**.

:::{tip}
`EOO`, `AOOGrid`, and `AOOGridPolygons` all follow the same lifecycle: construct
with a factory (`make_eoo` / `make_aoo_grid`), call `.compute()` to run the
computation, then read results (`area_km2`, `cell_count`, `grid_cells`, …).
Accessing results before `.compute()` raises a `NotComputed` error.
:::

## Next steps

- Explore the data model — filtering, export, rasterization → [](ecosystems.md)
- Go deeper on the metrics — grid fractions, caching, intersection polygons → [](assessment.md)
- See every public function → [](api.md)

---
title: Ecosystems
kernelspec:
  name: python3
  display_name: 'Python 3'
---

# The `Ecosystems` data model

`Ecosystems` is the entry point for every workflow. It wraps an ecosystem
distribution dataset behind a uniform, lazily-loaded interface, regardless of
where the data lives.

```{code-cell} python
:tags: remove-cell

GEOJSON = "data/null_island.geojson"
```

## Backends

Each concrete subclass reads a different source, but all expose the same API.
Pick one via a factory classmethod or construct it directly:

| Class                    | Source                                   | `kind`         |
| ------------------------ | ---------------------------------------- | -------------- |
| `EcosystemsFile`         | Vector file (Shapefile, GeoJSON, …)      | `VECTOR_LOCAL` |
| `EcosystemsGeoParquet`   | GeoParquet — local, `gs://`, `s3://`, …  | `VECTOR_LOCAL` |
| `EcosystemsGeoDataFrame` | In-memory GeoDataFrame                   | `VECTOR_LOCAL` |
| `EcosystemsCOG`          | Cloud Optimized GeoTIFF (raster)         | `RASTER_LOCAL` |

The `EcosystemKind` enum also defines `EE_FEATURE_COLLECTION` and `EE_IMAGE`,
which are handled by the optional `rle-python-gee` package.

```{code-cell} python
from rle.core import Ecosystems, EcosystemKind

eco = Ecosystems.from_file(GEOJSON, ecosystem_column="ECO_NAME")
print(type(eco).__name__, "->", eco.kind)
```

### Factory classmethods

```{code-cell} python
# from_file dispatches on extension; .parquet routes to the GeoParquet backend
Ecosystems.from_file(GEOJSON, ecosystem_column="ECO_NAME")          # EcosystemsFile
# Ecosystems.from_parquet("s3://bucket/eco.parquet", ecosystem_column="ECO_NAME")
# Ecosystems.from_cog("coverage.tif")
```

Cloud GeoParquet is read through `fsspec`, so `gs://` and `s3://` URIs work the
same way once the matching extra is installed (see [](installation.md)):

```python
eco = Ecosystems.from_parquet(
    "gs://my-bucket/ecosystems.parquet",
    ecosystem_column="ECO_NAME",
)
```

## Inspecting and subsetting

Data is loaded once and cached on first access. The identifying columns can be
declared up front and are carried through `filter()` and `limit()`.

```{code-cell} python
eco = Ecosystems.from_file(
    GEOJSON,
    ecosystem_column="ECO_NAME",
    functional_group_column="EFG1",
)
print("features:", eco.size())
print("ecosystems:", eco.unique_ecosystems())
print("functional groups:", eco.unique_functional_groups())
```

Values are returned in natural sort order (so `T1.1.2` precedes `T1.1.10`).

```{code-cell} python
# Keep only one ecosystem — returns a new Ecosystems
forest = eco.filter("Null Island Tropical Forest")
print(forest.size(), "feature(s):", forest.unique_ecosystems())
```

`filter(pattern, regex=True)` matches with a regular expression; `limit(n)`
keeps the first *n* features; `head(n)` returns a preview GeoDataFrame.

### Per-ecosystem AOO and EOO shortcuts

For a single filtered ecosystem, the `.aoo` and `.eoo` properties compute the
metrics directly (both cached after first access):

```{code-cell} python
print("EOO km²:", round(forest.eoo, 2))
print("AOO cells:", forest.aoo)
```

:::{note}
`.aoo` is not the raw grid cell count. It sorts occupied cells by ecosystem
fraction, takes the cumulative distribution, and drops the smallest cells below
1% cumulative proportion — a trimming rule that differs from
`make_aoo_grid(eco).compute().cell_count` in [](assessment.md).
:::

## Export

Vector datasets convert to a GeoDataFrame and write to GeoParquet or GeoJSON.
`to_parquet` accepts `gs://` targets when `gcsfs` is installed.

```python
gdf = eco.to_geodataframe()
eco.to_parquet("out/ecosystems.parquet")     # local or gs://
eco.to_geojson("out/ecosystems.geojson")
```

Uploading to Earth Engine (`to_ee_feature_collection`) requires `rle-python-gee`.

## Rasterization

`to_raster()` burns ecosystem polygons into a Cloud Optimized GeoTIFF. It has two
modes:

- **`mode="index"`** (default) — a single-band integer raster where each pixel
  holds the 1-based index of the ecosystem covering the pixel center. Indices
  follow the natural-sort order of `unique_ecosystems()`; where polygons overlap
  at a pixel center, the naturally-later code wins. Nodata defaults to the
  dtype maximum (255 / 65535 / 4294967295).
- **`mode="fraction"`** — a multi-band `float32` raster with one band per
  ecosystem, each storing the fraction of the pixel `[0.0, 1.0]` covered by that
  ecosystem, computed by rasterizing at `oversampling`× per axis and averaging.
  Each band's description is set to its ecosystem code. Nodata defaults to `NaN`.

`to_raster` returns a mapping of 1-based index → ecosystem code, and writes the
mapping into the COG tags (`ECOSYSTEM_INDEX_JSON`, `RASTERIZE_MODE`). It requires
a projected, equal-area CRS and pixel `scale` in CRS units:

```python
mapping = eco.to_raster(
    "out/ecosystems_index.tif",
    crs="ESRI:54034",      # World Cylindrical Equal Area
    scale=1000,            # 1 km pixels
    mode="index",
)

eco.to_raster(
    "out/ecosystems_fraction.tif",
    crs="ESRI:54034",
    scale=1000,
    mode="fraction",
    oversampling=10,
)
```

Rasterization is only supported for `VECTOR_LOCAL` datasets.

## Visualization

With the `viz` extra, any vector dataset renders as an interactive map:

```python
eco.to_map()                 # lonboard Map
eco.to_layer()               # lonboard PolygonLayer(s)
```

`to_map` caps interactive display at `max_features` (default 1000); reduce with
`.limit()`/`.filter()` or export to Earth Engine for tile-based display.

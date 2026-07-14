---
title: rle-python
description: Core tools for IUCN Red List of Ecosystems (RLE) analysis with local and cloud data access.
---

# rle-python

`rle-python` is the backend-agnostic **core** for
[IUCN Red List of Ecosystems (RLE)](https://iucnrle.org/) analysis. It provides the
RLE data model (`Ecosystems`, `AOOGrid`, `EOO`), the assessment business logic, and
local + cloud-file (`gs://`, `s3://` via fsspec) data access. It has **no Earth Engine
dependency** — Earth Engine support lives in the optional
[`rle-python-gee`](https://github.com/RLE-Assessment/rle-python-gee) distribution
(import `rle.gee`).

Check your installed version with `rle --version`, and list the data-access
backends registered in your environment with `rle backends` (see
[](cli-and-backends.md)).

Everything imports under the shared `rle` namespace:

```python
from rle.core import Ecosystems, make_aoo_grid, make_eoo

eco = Ecosystems.from_file("ecosystems.geojson", ecosystem_column="ECO_NAME")
print(make_aoo_grid(eco).compute().aoo_km2)   # Area of Occupancy (km²)
print(make_eoo(eco).compute().area_km2)       # Extent of Occurrence (km²)
```

## What's inside

::::{grid} 1 1 2 2

:::{card} Installation
:link: installation.md

Install from PyPI, with optional `gcs` / `aws` / `viz` extras.
:::

:::{card} Quickstart
:link: quickstart.md

Load ecosystems and compute AOO and EOO end to end.
:::

:::{card} Ecosystems guide
:link: ecosystems.md

Load, filter, export, and rasterize ecosystem distributions.
:::

:::{card} Assessment guide
:link: assessment.md

Extent of Occurrence, Area of Occupancy grids, and intersection polygons.
:::

:::{card} CLI & backends
:link: cli-and-backends.md

The `rle` command line tool and the plugin backend registry.
:::

:::{card} API reference
:link: api.md

Every public class and function.
:::

::::

## Glossary

```{glossary}
Red List of Ecosystems
: The IUCN global standard (RLE) for assessing the risk of ecosystem collapse,
  organised around five criteria (A–E) and a set of threat categories. Often
  abbreviated RLE.

Ecosystem
: A distribution dataset for one or more ecosystem types, loaded through the
  `Ecosystems` class from vector files, GeoParquet (local or cloud), in-memory
  GeoDataFrames, or Cloud Optimized GeoTIFFs.

EOO
: Extent of Occurrence — the area of the convex hull enclosing all occurrences of
  an ecosystem, reported in km². Feeds RLE Criterion B1.

AOO
: Area of Occupancy — the number of occupied cells on a standard 10×10 km grid
  (each cell covers 100 km²). Feeds RLE Criterion B2.

Functional Group
: A level of the IUCN Global Ecosystem Typology (e.g. `T1.1`) that an ecosystem
  belongs to. Ecosystem codes such as `T1.1.1` extend the functional group code.

Backend
: A data-access implementation (e.g. local vector, GeoParquet, COG) advertised
  through the `rle.backends` entry-point group and discoverable via the registry.
```

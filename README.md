# rle-python

Core tools for **IUCN Red List of Ecosystems (RLE)** analysis.

`rle-python` provides the RLE data model and assessment business logic
(Extent of Occurrence, Area of Occupancy grids, ecosystem code assignment,
criteria/categories) together with **local and cloud-file data access** — it
has no Earth Engine dependency.

Everything imports under the shared `rle` namespace:

```python
from rle.core import Ecosystems, make_aoo_grid, make_eoo

eco = Ecosystems.from_file("ecosystems.geojson", ecosystem_column="ECO_NAME")
aoo = make_aoo_grid(eco).compute()
print(aoo.cell_count, aoo.aoo_km2)

eoo = make_eoo(eco).compute()
print(eoo.area_km2)
```

## Installation

```bash
pip install rle-python            # local files
pip install rle-python[gcs]       # + gs:// GeoParquet (gcsfs)
pip install rle-python[aws]       # + s3:// GeoParquet (s3fs)
pip install rle-python[viz]       # + interactive maps (lonboard) / static fallback
```

## Optional backends

Additional data sources are provided by separate distributions that install
into the same `rle` namespace and register themselves for discovery:

```bash
pip install rle-python-gee        # Google Earth Engine backends -> rle.gee
```

```python
from rle.gee import GeeEcosystems
eco = GeeEcosystems("projects/my-project/assets/ecosystems")
```

List the backends available in your environment:

```bash
rle backends
```

## Layout

`rle-python` ships the `rle.core` package under a PEP 420 namespace (`rle/`),
so multiple `rle-*` distributions can coexist without conflict.

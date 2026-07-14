---
title: Installation
---

# Installation

`rle-python` requires Python **3.11 or 3.12** (`>=3.11,<3.13`).

## From PyPI

```bash
pip install rle-python            # local files
pip install rle-python[gcs]       # + gs:// GeoParquet (gcsfs)
pip install rle-python[aws]       # + s3:// GeoParquet (s3fs)
pip install rle-python[viz]       # + interactive maps (lonboard) / static fallback (matplotlib)
```

The extras are additive — combine them as needed, e.g.
`pip install rle-python[gcs,viz]`.

| Extra   | Adds                    | Enables                                            |
| ------- | ----------------------- | -------------------------------------------------- |
| `gcs`   | `gcsfs`                 | Reading/writing GeoParquet on `gs://`              |
| `aws`   | `s3fs`                  | Reading GeoParquet on `s3://`                      |
| `viz`   | `lonboard`, `matplotlib`| `to_map()` / `to_layer()` interactive maps and the static-image fallback |

The core install already pulls in the geospatial stack (`geopandas`, `shapely`,
`rasterio`, `rioxarray`, `rasterstats`, `pyproj`, `pyarrow`, `fsspec`) so local
vector, GeoParquet, and COG workflows work out of the box.

## From GitHub

To install an unreleased version straight from the repository:

```bash
pip install "rle-python @ git+https://github.com/RLE-Assessment/rle-python"
```

Extras work the same way, e.g.
`pip install "rle-python[viz] @ git+https://github.com/RLE-Assessment/rle-python"`.

## With uv

[uv](https://docs.astral.sh/uv/) is a fast Python package manager. Add
`rle-python` to a project (writes it to your `pyproject.toml`):

```bash
uv add rle-python
uv add "rle-python[gcs,viz]"        # with extras
```

To install into the current environment without touching project files:

```bash
uv pip install rle-python
```

Install from GitHub via uv:

```bash
uv add "rle-python @ git+https://github.com/RLE-Assessment/rle-python"
```

## As a script dependency

`rle-python` can be declared as an inline dependency of a single-file script
using [PEP 723](https://peps.python.org/pep-0723/) metadata. A runner such as
`uv run` reads the `# /// script` block, provisions an isolated environment, and
executes the file — no separate install step:

```python
# /// script
# requires-python = ">=3.11"
# dependencies = ["rle-python @ git+https://github.com/RLE-Assessment/rle-python"]
# ///

from rle.core import list_backends

print("rle backends:", list_backends())
```

Run it with:

```bash
uv run script.py
```

## Earth Engine support

Earth Engine backends are **not** part of `rle-python`. They ship in the optional
companion distribution [`rle-python-gee`](https://github.com/RLE-Assessment/rle-python-gee),
which installs into the same `rle` namespace under `rle.gee`:

```bash
pip install rle-python-gee        # Google Earth Engine backends -> rle.gee
```

```python
from rle.gee import GeeEcosystems
eco = GeeEcosystems("projects/my-project/assets/ecosystems")
```

List the backends available in your environment with the CLI:

```bash
rle backends
```

See [](cli-and-backends.md) for details on the backend registry.

## Verify the install

```bash
rle --version
```

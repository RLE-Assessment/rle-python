---
title: Ecosystem codes
kernelspec:
  name: python3
  display_name: 'Python 3'
---

# Assigning ecosystem codes

Ecosystem codes extend a functional group code with a per-ecosystem counter —
for example, two ecosystems in functional group `T1.1` become `T1.1.1` and
`T1.1.2`. `rle-python` can generate these deterministically from a functional
group column and an ecosystem name column.

## As a function

`assign_ecosystem_codes` lives in `rle.core.ecosystem_codes` and returns a copy
of the input GeoDataFrame with a new code column. Within each functional group,
distinct ecosystem names are sorted alphabetically before numbering, so the
result is independent of input row order.

```{code-cell} python
import geopandas as gpd
from rle.core.ecosystem_codes import assign_ecosystem_codes

gdf = gpd.read_file("data/null_island.geojson")

coded = assign_ecosystem_codes(
    gdf,
    fg_code_col="EFG1",        # existing functional group code, e.g. "T1.1"
    eco_name_col="ECO_NAME",   # existing ecosystem name
    eco_code_col="NEW_CODE",   # new column to create
)
coded[["EFG1", "ECO_NAME", "NEW_CODE"]]
```

Behaviour worth knowing:

- Rows whose functional group code or ecosystem name is null get a **null** code.
- It raises `ValueError` if a source column is missing or if the target column
  already exists (it refuses to overwrite).
- It emits a `UserWarning` when any generated code exceeds **10 characters** —
  shapefile DBF fields silently truncate at 10, which can collapse distinct
  ecosystems into the same reported code.

## As a command-line script

`scripts/assign_ecosystem_codes.py` wraps the same function for file-to-file use.
Input and output formats are auto-detected by extension (`.shp`, `.geojson`,
`.gpkg`, `.fgb`).

```bash
python scripts/assign_ecosystem_codes.py \
    input.geojson output.geojson \
    --fg-code-col EFG1 \
    --eco-name-col ECO_NAME \
    --eco-code-col ECO_CODE
```

| Argument          | Required | Meaning                                           |
| ----------------- | -------- | ------------------------------------------------- |
| `input`           | yes      | Path to the input vector file                     |
| `output`          | yes      | Path to the output vector file                    |
| `--fg-code-col`   | yes      | Existing functional group code column             |
| `--eco-name-col`  | yes      | Existing ecosystem name column                    |
| `--eco-code-col`  | yes      | Name of the new code column to create             |

The script prints a summary (functional groups, distinct ecosystems, rows with a
null code) and creates output parent directories automatically. If the output is
a `.shp` and `--eco-code-col` is longer than 10 characters, it exits with an
error before writing — choose a shorter name or a non-shapefile format.

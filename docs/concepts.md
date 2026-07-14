---
title: RLE concepts
kernelspec:
  name: python3
  display_name: 'Python 3'
---

# RLE concepts

The [IUCN Red List of Ecosystems](https://iucnrle.org/rle-categ-and-criteria)
(RLE) is a global standard for assessing the risk of ecosystem collapse. This
page summarizes the criteria and categories that `rle-python`'s metrics feed
into. The reference constants below live in `rle.core.rle`.

## Criteria

An ecosystem is assessed against five criteria; the overall status is the
highest risk category obtained under any single criterion.

| Criterion | Description                                                                 |
| --------- | --------------------------------------------------------------------------- |
| **A**     | Reduction in geographic distribution                                        |
| **B**     | Restricted geographic distribution                                          |
| **C**     | Environmental degradation                                                   |
| **D**     | Disruption of biotic processes and interactions                             |
| **E**     | Quantitative analysis estimating the probability of ecosystem collapse      |

`rle-python` computes the two spatial sub-measures of **Criterion B**:

- **EOO** (Extent of Occurrence) → Criterion **B1** — see [](assessment.md#extent-of-occurrence-eoo).
- **AOO** (Area of Occupancy) → Criterion **B2** — see [](assessment.md#area-of-occupancy-aoo).

## Threat categories

```{code-cell} python
import pandas as pd
from rle.core.rle import rle_categories

pd.DataFrame(rle_categories)[["name", "abbreviation", "threatened"]]
```

The categories, from highest to lowest risk, are Collapsed (CO), Critically
Endangered (CR), Endangered (EN), Vulnerable (VU), Near Threatened (NT), Least
Concern (LC), plus Data Deficient (DD) and Not Evaluated (NE). CO, CR, EN, and VU
are the *threatened* categories.

## The equal-area projection

Both EOO area and AOO grids are computed in **`ESRI:54034`** (World Cylindrical
Equal Area) — the equal-area projection used for RLE spatial measures, so that
areas and 10×10 km grid cells are consistent across datasets and latitudes.

For the full criteria thresholds and sub-criteria, see the IUCN RLE
[categories and criteria](https://iucnrle.org/rle-categ-and-criteria) reference.

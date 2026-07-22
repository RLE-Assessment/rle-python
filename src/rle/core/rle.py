# https://iucnrle.org/rle-categ-and-criteria
rle_criteria = {
    "A": {
        "description": "Reduction in geographic distribution",
        "threshold": 0.5
    },
    "B": {
        "description": "Restricted geographic distribution",
        "threshold": 0.5
    },
    "C": {
        "description": "Environmental degradation",
        "threshold": 0.5
    },
    "D": {
        "description": "Disruption of biotic processes and interactions",
        "threshold": 0.5
    },
    "E": {
        "description": "Quantitative analysis that estimates the probability of ecosystem collapse",
        "threshold": 0.5
    }
}

# Source: https://iucnrle.org/rle-categ-and-criteria
rle_categories = [
    {
        "name": "Collapsed",
        "abbreviation": "CO",
        "threatened": True,
        "background_color": "black",
    },
    {
        "name": "Critically Endangered",
        "abbreviation": "CR",
        "threatened": True,
        "background_color": "red",
    },
    {
        "name": "Endangered",
        "abbreviation": "EN",
        "threatened": True,
        "background_color": "orange",
    },
    {
        "name": "Vulnerable",
        "abbreviation": "VU",
        "threatened": True,
        "background_color": "yellow",
    },
    {
        "name": "Near Threatened",
        "abbreviation": "NT",
        "background_color": "green",
    },
    {
        "name": "Least Concern",
        "abbreviation": "LC",
        "background_color": "darkgreen",
    },
    {
        "name": "Data Deficient",
        "abbreviation": "DD",
        "background_color": "lightgray",    
    },
    {
        "name": "Not Evaluated",
        "abbreviation": "NE",
        "background_color": "white",
    }
]


def rle_category(abbreviation):
    """Return the ``rle_categories`` entry for a category abbreviation.

    Args:
        abbreviation: A category code such as ``"VU"``, ``"EN"``, ``"CR"``, ``"LC"``.

    Returns:
        The matching dict (``name``/``abbreviation``/``background_color`` and, for
        threatened categories, ``threatened``), or ``None`` if unknown.
    """
    return next(
        (c for c in rle_categories if c["abbreviation"] == abbreviation), None
    )


# Criterion B (restricted geographic distribution) thresholds, from the IUCN Red
# List of Ecosystems Guidelines v2.0 (2024), Section 6.2, p.66. Each entry is an
# inclusive upper bound ("<=") mapping to the category met at that bound.
#   B1 uses EOO (extent of occurrence) in km².
#   B2 uses AOO (area of occupancy) as the number of occupied 10 x 10 km cells.
CRITERION_B1_EOO_KM2 = [(2_000, "CR"), (20_000, "EN"), (50_000, "VU")]
CRITERION_B2_AOO_CELLS = [(2, "CR"), (20, "EN"), (50, "VU")]

# Ordering from most to least threatened, used to pick the overall category as the
# most-threatened of the sub-criteria. (NT/DD/NE are never assigned by the spatial
# thresholds here, but are ranked so the helper composes with manual inputs.)
_CATEGORY_RANK = {"CO": 0, "CR": 1, "EN": 2, "VU": 3, "NT": 4, "LC": 5, "DD": 6, "NE": 7}


def _category_for(value, thresholds):
    """Map a metric value to a category via inclusive upper-bound thresholds.

    Returns ``None`` if ``value`` is ``None`` (metric unavailable), or ``"LC"`` if
    the value exceeds every threshold (does not meet Criterion B on this metric).
    """
    if value is None:
        return None
    for upper, category in thresholds:
        if value <= upper:
            return category
    return "LC"


def criterion_b_status(eoo_km2=None, aoo_cells=None):
    """Classify IUCN RLE Criterion B status from the spatial metrics.

    Applies the B1 (EOO) and B2 (AOO) thresholds and returns the category met by
    each, plus the overall Criterion B category (the most-threatened of the two).

    IMPORTANT: these are the *spatial* thresholds only. A final listing under B1 or
    B2 additionally requires at least one of sub-conditions (a) continuing decline,
    (b) threatening processes, or (c) few threat-defined locations — which cannot be
    derived from EOO/AOO alone. Callers should present the result as provisional on
    those sub-conditions. A value above the VU threshold yields ``"LC"`` (does not
    meet Criterion B); ``NT`` is a judgement call with no numeric breakpoint and is
    never assigned here.

    Args:
        eoo_km2: Extent of occurrence in km² (B1), or ``None`` if unavailable.
        aoo_cells: Number of occupied 10 x 10 km cells (B2), or ``None``.

    Returns:
        dict with keys ``"B1"``, ``"B2"``, ``"overall"`` holding category
        abbreviations (or ``None`` when the corresponding metric is ``None``).
    """
    b1 = _category_for(eoo_km2, CRITERION_B1_EOO_KM2)
    b2 = _category_for(aoo_cells, CRITERION_B2_AOO_CELLS)
    categories = [c for c in (b1, b2) if c is not None]
    overall = min(categories, key=lambda c: _CATEGORY_RANK[c]) if categories else None
    return {"B1": b1, "B2": b2, "overall": overall}
"""RLE core — IUCN Red List of Ecosystems analysis with local/cloud data access.

This is the backend-agnostic core. It provides the RLE data model
(``Ecosystems``, ``AOOGrid``, ``EOO``), the assessment business logic, and
local + cloud-file (``gs://``, ``s3://`` via fsspec) data access.

Earth Engine support lives in the optional ``rle-python-gee`` distribution
(import ``rle.gee``).
"""

from importlib.metadata import version, PackageNotFoundError

try:
    __version__ = version("rle-python")
except PackageNotFoundError:
    __version__ = "0.0.0.dev"

from rle.core.ecosystems import (
    Ecosystems,
    EcosystemKind,
    EcosystemsFile,
    EcosystemsGeoParquet,
    EcosystemsGeoDataFrame,
    EcosystemsCOG,
)
from rle.core.eoo import (
    EOO,
    EOOVectorLocal,
    EOONotComputedError,
    make_eoo,
)
from rle.core.aoo import (
    AOOGrid,
    AOOGridVectorLocal,
    AOOGridCOG,
    AOOGridNotComputedError,
    AOOGridPolygons,
    AOOGridPolygonVectorLocal,
    AOOGridPolygonsNotComputedError,
    make_aoo_grid,
    make_aoo_grid_cached,
    make_aoo_polygons,
    slugify_ecosystem_name,
)
from rle.core.registry import BackendInfo, iter_backends, list_backends
from rle.core.rle import (
    rle_categories,
    rle_criteria,
    rle_category,
    criterion_b_status,
    CRITERION_B1_EOO_KM2,
    CRITERION_B2_AOO_CELLS,
)

__all__ = [
    "__version__",
    # data model
    "Ecosystems",
    "EcosystemKind",
    "EcosystemsFile",
    "EcosystemsGeoParquet",
    "EcosystemsGeoDataFrame",
    "EcosystemsCOG",
    # EOO
    "EOO",
    "EOOVectorLocal",
    "EOONotComputedError",
    "make_eoo",
    # AOO
    "AOOGrid",
    "AOOGridVectorLocal",
    "AOOGridCOG",
    "AOOGridNotComputedError",
    "AOOGridPolygons",
    "AOOGridPolygonVectorLocal",
    "AOOGridPolygonsNotComputedError",
    "make_aoo_grid",
    "make_aoo_grid_cached",
    "make_aoo_polygons",
    "slugify_ecosystem_name",
    # discovery
    "BackendInfo",
    "iter_backends",
    "list_backends",
    # Red List categories & Criterion B assessment
    "rle_categories",
    "rle_criteria",
    "rle_category",
    "criterion_b_status",
    "CRITERION_B1_EOO_KM2",
    "CRITERION_B2_AOO_CELLS",
]

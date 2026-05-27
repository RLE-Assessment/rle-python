"""Entry-point registration for the core (local/cloud-file) backends."""

from __future__ import annotations

from rle.core.registry import BackendInfo


def _is_geojson(data) -> bool:
    return isinstance(data, str) and data.endswith((".geojson", ".json"))


def _is_geoparquet(data) -> bool:
    return isinstance(data, str) and data.endswith(".parquet")


def _is_cog(data) -> bool:
    return isinstance(data, str) and data.endswith((".tif", ".tiff"))


def register() -> list[BackendInfo]:
    """Advertise the local/cloud-file ecosystem backends provided by rle-python."""
    from rle.core.ecosystems import (
        EcosystemsFile,
        EcosystemsGeoParquet,
        EcosystemsCOG,
    )

    dist = "rle-python"
    return [
        BackendInfo(
            name="file",
            cls=EcosystemsFile,
            capability="ecosystems",
            distribution=dist,
            can_handle=_is_geojson,
        ),
        BackendInfo(
            name="geoparquet",
            cls=EcosystemsGeoParquet,
            capability="ecosystems",
            distribution=dist,
            can_handle=_is_geoparquet,
        ),
        BackendInfo(
            name="cog",
            cls=EcosystemsCOG,
            capability="ecosystems",
            distribution=dist,
            can_handle=_is_cog,
        ),
    ]

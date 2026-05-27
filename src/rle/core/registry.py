"""Backend discovery for the ``rle`` namespace.

Backend distributions (e.g. ``rle-python-gee``) advertise their data-access
backends through an ``rle.backends`` entry point. Each entry point is a
callable returning one or more :class:`BackendInfo` records.

This registry is for *discovery and introspection* only (e.g. the ``rle
backends`` CLI command). Backends are constructed explicitly by importing
their classes — there is no auto-dispatch here.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import entry_points
from typing import Callable, Optional

_GROUP = "rle.backends"


@dataclass(frozen=True)
class BackendInfo:
    """Describes a single data-access backend.

    Attributes:
        name: Stable identifier, e.g. ``"gee-feature-collection"``.
        cls: The backend class (an ``Ecosystems``/``AOOGrid``/``EOO`` subclass).
        capability: One of ``"ecosystems"``, ``"aoo"``, ``"eoo"``.
        distribution: The distribution that provides it, e.g. ``"rle-python-gee"``.
        can_handle: Optional predicate for a future URI/data dispatcher.
    """

    name: str
    cls: type
    capability: str
    distribution: str = ""
    can_handle: Optional[Callable[[object], bool]] = None


def iter_backends() -> list[BackendInfo]:
    """Return every backend advertised by installed ``rle.backends`` entry points.

    Entry points whose callable fails to load or run are skipped silently so a
    broken optional backend never breaks discovery of the others.
    """
    infos: list[BackendInfo] = []
    for ep in entry_points(group=_GROUP):
        try:
            factory = ep.load()
            result = factory()
        except Exception:
            continue
        if isinstance(result, (list, tuple)):
            infos.extend(r for r in result if isinstance(r, BackendInfo))
        elif isinstance(result, BackendInfo):
            infos.append(result)
    return infos


def list_backends() -> list[str]:
    """Return the names of all installed backends, sorted."""
    return sorted(b.name for b in iter_backends())

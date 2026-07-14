---
title: CLI & backends
kernelspec:
  name: python3
  display_name: 'Python 3'
---

# Command line & backend registry

## The `rle` CLI

Installing `rle-python` provides an `rle` command (a small Typer app):

```bash
rle --version        # print the installed version
rle backends         # list installed data-access backends
rle --help
```

`rle backends` prints one row per registered backend — its name, capability, and
the distribution that provides it — sorted by capability then name.

## The backend registry

Backends are advertised through the `rle.backends` **entry-point group**. Each
entry point is a callable that returns one or more `BackendInfo` records.
`rle-python` registers its own core backends, and optional distributions such as
`rle-python-gee` register theirs into the same namespace.

The registry is for **discovery and introspection only** — it is how the CLI and
your own code can enumerate what is installed. There is no auto-dispatch: you
still construct backend classes explicitly (e.g. `Ecosystems.from_file(...)` or
`from rle.gee import GeeEcosystems`).

```{code-cell} python
from rle.core import iter_backends, list_backends

print(list_backends())
for b in iter_backends():
    print(f"{b.name:<12} {b.capability:<11} {b.distribution}")
```

`BackendInfo` is a frozen dataclass with these fields:

| Field          | Meaning                                                       |
| -------------- | ------------------------------------------------------------ |
| `name`         | Stable identifier, e.g. `"geoparquet"`                        |
| `cls`          | The backend class (an `Ecosystems` / `AOOGrid` / `EOO` type) |
| `capability`   | One of `"ecosystems"`, `"aoo"`, `"eoo"`                      |
| `distribution` | Providing distribution, e.g. `"rle-python"`                  |
| `can_handle`   | Optional predicate reserved for a future URI dispatcher      |

Entry points that fail to load or run are skipped silently, so a broken optional
backend never breaks discovery of the others.

## Registering your own backend

A distribution advertises backends by pointing an `rle.backends` entry point at a
callable that returns `BackendInfo` records. For example, in `pyproject.toml`:

```toml
[project.entry-points."rle.backends"]
mypackage = "mypackage._entrypoints:register"
```

```python
# mypackage/_entrypoints.py
from rle.core import BackendInfo
from mypackage import MyEcosystems

def register():
    return [
        BackendInfo(
            name="my-backend",
            cls=MyEcosystems,
            capability="ecosystems",
            distribution="mypackage",
        ),
    ]
```

Once installed, it appears in `rle backends` and `list_backends()`.

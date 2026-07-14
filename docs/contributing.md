---
title: Contributing
---

# Contributing

## Dev setup

```bash
git clone https://github.com/RLE-Assessment/rle-python
cd rle-python
pip install -e .            # editable install with core dependencies
```

Add extras as needed for map/visualization work, e.g. `pip install -e ".[viz]"`.

## Running tests

The test suite (marked `unit`) is fast and needs no Earth Engine credentials.
`pytest` is provided by the `dev` dependency group:

```bash
pip install --group dev     # or: pip install pytest
pytest
```

## Building these docs

The documentation in `docs/` is written for [MyST](https://mystmd.org/) and
contains executable `{code-cell}` blocks that run against the package and the
bundled `docs/data/null_island.geojson` sample. Install the CLI and a Jupyter
kernel, then preview locally:

```bash
npm install -g mystmd
pip install jupyter-server ipykernel
python -m ipykernel install --user --name python3

cd docs
myst start                    # live preview at http://localhost:3000
myst build --html --execute   # execute cells + build static HTML in _build/html/
```

`myst build --html --execute` is what CI runs (see
`.github/workflows/deploy-docs.yml`); it fails the build if any code cell errors,
which keeps the examples honest.

## Layout

```
docs/
├── myst.yml             # MyST project config + TOC
├── index.md             # landing page
├── installation.md
├── quickstart.md
├── ecosystems.md
├── assessment.md
├── ecosystem-codes.md
├── cli-and-backends.md
├── api.md
├── concepts.md
├── contributing.md
└── data/
    └── null_island.geojson   # sample dataset used by the executable examples
```

## Style

- Keep code samples runnable against the current `main` branch. Prefer executable
  `{code-cell}` blocks for light, local operations; use static ```python``` blocks
  for anything that needs the cloud, Earth Engine, `viz` widgets, or writes files.
- Use MyST cross-references (`[](page.md#anchor)`) rather than raw URLs for in-repo
  links — they are checked at build time.

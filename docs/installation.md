# Installation

## PyPI

Once published:

```sh
pip install pytimeslice
```

## Local Development

For local work on the repository:

```sh
make setup
```

This creates `.venv`, installs the package in editable mode, and installs the
development toolchain.

## Docs Tooling

The docs site is built with MkDocs and `mkdocstrings`.

```sh
make docs-build
make docs-serve
```

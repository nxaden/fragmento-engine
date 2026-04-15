# Releasing

This repository is set up for source and wheel builds through `python -m build`
and distribution validation through `twine check`.

## Before You Start

- Confirm the package name and repository URLs in `pyproject.toml`.
- Bump the version in `pyproject.toml`.
- Make sure `README.md` still renders correctly as package metadata.

## Local Release Checklist

1. Run the full verification stack:

   ```sh
   make check
   ```

2. Build source and wheel distributions:

   ```sh
   make build
   ```

3. Validate the generated metadata and README rendering:

   ```sh
   make check-dist
   ```

The generated artifacts land in `dist/`.

## TestPyPI

Use TestPyPI first if you want to validate installability and rendered package
metadata before the real release:

```sh
.venv/bin/python -m twine upload --repository testpypi dist/*
```

Then verify installation from TestPyPI in a clean environment.

## PyPI

When the package is ready for a real release:

```sh
.venv/bin/python -m twine upload dist/*
```

If you later adopt trusted publishing in CI, keep `make build` and
`make check-dist` as the local preflight steps so local and CI packaging
behavior stay aligned.

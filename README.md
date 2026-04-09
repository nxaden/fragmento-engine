# Fragmento Core

Fragmento Core is the image processing engine behind Fragmento. It takes an ordered image sequence and a time-slice specification, then produces a composite time-slice image.

## Status

This project is under active development.

## Goals

- deterministic rendering
- testable core logic
- clean separation between domain logic and infrastructure
- reusable core for multiple interfaces

## Project Structure

```text
src/
└── fragmento_core/
    ├── app.py
    ├── application/
    ├── domain/
    ├── infra/
    └── interface/
```

## Development

Install dependencies:

```bash
make setup
```

Run tests:

```bash
make test
```

## Documentation

- See: `docs/architecture.md`
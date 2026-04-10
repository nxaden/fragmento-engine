# Fragmento Engine

Fragmento Engine is the core image-processing library behind Fragmento. It takes an ordered image sequence and a time-slice specification, then produces a composite time-slice image.

The project is designed as a reusable Python engine first, with thin interfaces such as a CLI layered on top.

## Status

This project is under active development.

## Goals

- deterministic rendering
- testable core logic
- clean separation between domain, application, infrastructure, and interface layers
- reusable engine for multiple interfaces
- library friendly API with CLI support

## Features

Current focus includes:

- loading ordered image sequences
- resizing or cropping source images to a consistent frame size
- vertical or horizontal time-slice rendering
- configurable slice count
- optional reverse-time rendering
- application-layer render workflows
- infrastructure adapters for PIL-based loading and saving

## Architecture

Fragmento Engine is organized into layers:

- **Domain**: core models and time-slice logic
- **Application**: render workflows and service orchestration
- **Infrastructure**: image loading and writing adapters
- **Interface**: CLI and future user-facing entry points

## Project Structure

```text
src/
└── fragmento_engine/
    ├── __init__.py
    ├── app.py
    ├── application/
    │   └── services.py
    ├── domain/
    │   ├── compositor.py
    │   ├── models.py
    │   └── planner.py
    ├── infrastructure/
    │   ├── image_loader.py
    │   └── image_writer.py
    ├── interfaces/
    │   └── cli.py
    └── shared/
        └── types.py
```

## Installation

Clone the repository and install the project in your environment.

```sh
make setup
```

## Development

Run tests with:

```sh
make test
```

## Library Usage

Fragmento Engine is intended to be usable as a Python library.

Example:

```sh
from pathlib import Path

from fragmento_engine import render_folder, TimesliceSpec

spec = TimesliceSpec(
    orientation="vertical",
    num_slices=20,
    reverse_time=False,
)

response = render_folder(
    input_folder=Path("./frames"),
    output_file=Path("./out/timeslice.jpg"),
    spec=spec,
    resize_mode="crop",
)

print(response.result.image.shape)
```

## CLI Usage

A CLI interface can be provided on top of the engine so a folder of source frames can be rendered directly from the command line.

```sh
fragmento ./frames ./out.jpg --orientation vertical --slices 20
```

## Roadmap

Planned improvements include:

preview workflows
metadata export
batch rendering
additional frame selection strategies
richer public API
PyPI packaging and publishing
web interface support

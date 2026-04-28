# pytimeslice

![Timeslice](assets/timeslice.gif)

`pytimeslice` is a Python image-processing library for building composite
timeslice images from ordered frame sequences.

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
- optional slice boundary effects such as borders, auto or gradient dividers,
  shadows, highlights, feathering, and curve shaping
- application-layer render workflows
- infrastructure adapters for PIL-based loading and saving

## Architecture

`pytimeslice` is organized into layers:

- **Domain**: core models and time-slice logic
- **Application**: render workflows and service orchestration
- **Infrastructure**: image loading and writing adapters
- **Interface**: CLI and future user-facing entry points

See [the hosted documentation](https://nxaden.github.io/pytimeslice/) for the
user guides and generated API reference.

## Project Structure

```text
src/
└── pytimeslice/
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
    ├── interface/
    │   └── cli.py
    └── shared/
        └── types.py
```

## Installation

For local development:

```sh
make setup
```

Once the package is published, the install command will be:

```sh
pip install pytimeslice
```

## Development

Run tests with:

```sh
make test
```

Committed sample inputs for experimentation and future fixtures live under:

- `examples/media/placeholder-sequence/`
- `tests/fixtures/placeholder-sequence/`

## Library Usage

`pytimeslice` is intended to be usable as a Python library.

Example:

```python
from pathlib import Path

from pytimeslice import SliceEffects, TimesliceSpec, render_folder

spec = TimesliceSpec(
    orientation="vertical",
    num_slices=20,
    reverse_time=False,
    effects=SliceEffects(
        border_width=2,
        border_color=(255, 255, 255),
        border_opacity=0.8,
        border_color_mode="gradient",
        shadow_width=8,
        shadow_opacity=0.35,
        highlight_width=4,
        highlight_opacity=0.2,
        feather_width=6,
        curve="smoothstep",
    ),
)

response = render_folder(
    input_folder=Path("./frames"),
    spec=spec,
    resize_mode="crop",
)

print(response.result.image.shape)
```

To render and save explicitly:

```python
from pytimeslice import render_folder_to_file

saved = render_folder_to_file(
    input_folder=Path("./frames"),
    spec=spec,
    resize_mode="crop",
)

print(saved.output_file)
```

## CLI Usage

A CLI interface can be provided on top of the engine so a folder of source
frames can be rendered directly from the command line.

```sh
pytimeslice ./frames --orientation vertical --slices 20
```

If no output path is provided, `pytimeslice` writes a timestamped file into an
`out/` folder next to the input folder.

Example with slice effects:

```sh
pytimeslice ./frames \
  --orientation vertical \
  --slices 20 \
  --border 2 \
  --border-opacity 0.8 \
  --border-color-mode gradient \
  --shadow 8 \
  --shadow-opacity 0.35 \
  --highlight 4 \
  --highlight-opacity 0.2 \
  --feather 6 \
  --curve smoothstep
```

Progression GIF example:

```sh
pytimeslice ./frames \
  --progression-gif \
  --gif-smooth-loop \
  --gif-frame-duration-ms 180 \
  --orientation vertical \
  --border 4 \
  --border-color-mode gradient \
  --shadow 8 \
  --highlight 4 \
  --feather 6 \
  --curve smoothstep
```

More CLI recipes, including overlay practice commands, live in
[the hosted docs](https://nxaden.github.io/pytimeslice/USAGE_EXAMPLES/).

## Packaging

Release-oriented commands:

```sh
make release-check
make build
make check-dist
```

The release checklist lives in
[RELEASING.md](https://github.com/nxaden/pytimeslice/blob/main/RELEASING.md).
Release notes live in
[CHANGELOG.md](https://github.com/nxaden/pytimeslice/blob/main/CHANGELOG.md).

## Docs

The human-facing docs site is built with MkDocs and generated API reference
pages from the package docstrings.

Hosted docs are intended to live at
[nxaden.github.io/pytimeslice](https://nxaden.github.io/pytimeslice/).

```sh
make docs-build
make docs-serve
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

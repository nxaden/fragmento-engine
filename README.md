# pytimeslice

| ![Timeslice](assets/timeslice.gif) |
|:--:| 
| *An animated Timeslice of the 401 Highway in Toronto created from `pytimeslice`* |

`pytimeslice` is a Python image processing library for building composite
[timeslice](http://medium.com/@blech/a-slice-of-time-1c70f1b06665) images from ordered frame sequences.

## Features

- Render composite timeslice images from ordered image sequences
- Choose vertical or horizontal slicing, slice count, and time direction
- Use mask-based layouts such as diagonal, spiral, circular, random block grids, or user-defined pixel-order masks
- Normalize source frames by resizing, cropping, or fitting them to a common size
- Add slice-boundary effects including borders, dividers, shadows, highlights, feathering, and curve shaping
- Export still images or animated progression GIFs
- Use as either a Python library or a command-line tool

## Architecture

`pytimeslice` is organized into layers:

- **Domain**: core models and time-slice logic
- **Application**: render workflows and service orchestration
- **Infrastructure**: image loading and writing adapters
- **Interface**: CLI and future user-facing entry points

See [the hosted documentation](https://nxaden.github.io/pytimeslice/) for the
user guides and generated API reference.

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

Mask-based layouts are available from the Python API:

```python
import numpy as np

from pytimeslice import TimesliceSpec, render_images

diagonal = render_images(
    images=frames,
    spec=TimesliceSpec(layout="diagonal", num_slices=12),
)

circular = render_images(
    images=frames,
    spec=TimesliceSpec(layout="circular", num_slices=12),
)

random_blocks = render_images(
    images=frames,
    spec=TimesliceSpec(layout="random", num_blocks=128, random_seed=7),
)

custom = render_images(
    images=frames,
    spec=TimesliceSpec(
        layout="mask",
        num_slices=12,
        layout_mask=np.linspace(0.0, 1.0, frames[0].shape[0] * frames[0].shape[1]).reshape(
            frames[0].shape[0],
            frames[0].shape[1],
        ),
    ),
)
```

## CLI Usage

A CLI interface is provided on top of the engine so a folder of source
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

Built-in mask layouts are also available from the CLI:

```sh
pytimeslice ./frames \
  --layout diagonal \
  --slices 24

pytimeslice ./frames \
  --layout circular \
  --slices 24

pytimeslice ./frames \
  --layout random \
  --random-blocks 128 \
  --random-seed 7
```

User-defined masks can be loaded from a grayscale image or `.npy` file:

```sh
pytimeslice ./frames \
  --layout mask \
  --layout-mask ./masks/spiral-guide.npy \
  --slices 24
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

The docs site is built with MkDocs and generated API reference
pages from the package docstrings.

Hosted docs are live at
[nxaden.github.io/pytimeslice](https://nxaden.github.io/pytimeslice/).

You can also serve them locally:

```sh
make docs-build
make docs-serve
```

# pytimeslice

| ![Timeslice](assets/timeslice.gif) |
|:--:| 
| *An animated Timeslice of the 401 Highway in Toronto created from `pytimeslice`* |

`pytimeslice` is a Python image processing library for building composite
[timeslice](http://medium.com/@blech/a-slice-of-time-1c70f1b06665) images from ordered frame sequences.

## Features

- Render composite timeslice images from ordered image sequences or sampled video frames
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

To render from a video, install `ffmpeg`/`ffprobe` on your PATH and use the
video APIs. Frames are sampled evenly across the video; by default the sample
count follows `spec.num_slices`, `spec.num_blocks`, or falls back to 24 frames.

```python
from pathlib import Path

from pytimeslice import TimesliceSpec, VideoFrameSelectionSpec, render_video_to_file

saved = render_video_to_file(
    video_file=Path("./clip.mp4"),
    output_file=Path("./out/video-timeslice.png"),
    spec=TimesliceSpec(num_slices=20),
    frame_selection=VideoFrameSelectionSpec(target_frame_count=20),
)

print(saved.sampled_frame_indices)
```

To render an animation export through the unified API:

```python
from pathlib import Path

from pytimeslice import TimesliceSpec, render_animation

animated = render_animation(
    input_folder=Path("./frames"),
    output_file=Path("./out/random-shuffle.gif"),
    spec=TimesliceSpec(layout="random", num_blocks=128, random_seed=7),
    mode="random",
    output_format="gif",
    frame_count=8,
    frame_duration_ms=180,
    loops=2,
    smooth_loop=True,
)

print(animated.emitted_values)
print(animated.output_file)
```

To render a video export, `ffmpeg` must be available on `PATH`:

```python
from pathlib import Path

from pytimeslice import TimesliceSpec, render_animation

video = render_animation(
    input_folder=Path("./frames"),
    output_file=Path("./out/random-shuffle.mov"),
    spec=TimesliceSpec(layout="random", num_blocks=128, random_seed=7),
    mode="random",
    output_format="mov",
    frame_count=8,
    fps=12,
    loops=2,
    smooth_loop=True,
)

print(video.emitted_values)
print(video.output_file)
```

The older `render_progression_gif(...)`, `render_random_gif(...)`,
`render_progression_video(...)`, and `render_random_video(...)` helpers remain
available as compatibility wrappers around the same animation service.

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

Manual slot assignment is also available for future UI flows where the caller
chooses exactly which image belongs in each slice. This requires
`spec.num_slices` to be set explicitly.

Layout metadata for a future client can be described without rendering any user
content:

```python
from pytimeslice import TimesliceSpec, describe_layout

layout = describe_layout(
    TimesliceSpec(layout="diagonal", num_slices=5),
    width=3840,
    height=2160,
)

print(layout.slot_count)
print(layout.slots[0].bounds)
print(layout.mask_for_slot(0).shape)

slot_preview = layout.render_slot_preview(0)
```

That metadata can be serialized for a web client or saved as JSON:

```python
import json

from pytimeslice import (
    deserialize_layout,
    export_layout_json,
    import_layout_json,
    serialize_layout,
)

payload = serialize_layout(layout, include_preview_image=False)
json_blob = json.dumps(payload)
restored = deserialize_layout(json.loads(json_blob))

saved_file = export_layout_json(layout, "./out/layout-metadata.json")
loaded = import_layout_json(saved_file)
```

Client-edited slot maps can also be validated and imported directly:

```python
import numpy as np

from pytimeslice import (
    assign_images_to_slots,
    clear_slot,
    create_manual_timeslice,
    import_slot_map,
    replace_canvas_slot_map,
    swap_slots,
    TimesliceSpec,
    validate_slot_map,
)

edited_slot_map = validate_slot_map(
    np.array(
        [
            [0, 0, 0, 2, 2, 1],
            [0, 0, 0, 2, 2, 1],
        ],
        dtype=np.int_,
    )
)
edited_layout = import_slot_map(edited_slot_map)

canvas = create_manual_timeslice(
    TimesliceSpec(orientation="vertical", num_slices=3),
    width=6,
    height=2,
)
canvas = replace_canvas_slot_map(canvas, edited_slot_map)
canvas = swap_slots(canvas, 0, 2)
canvas = clear_slot(canvas, 1)
canvas = assign_images_to_slots(canvas, {1: replacement_frame})
```

One-shot render from an explicit list of paths:

```python
from pathlib import Path

from pytimeslice import TimesliceSpec, render_assigned_paths

spec = TimesliceSpec(orientation="horizontal", num_slices=5)

canvas = render_assigned_paths(
    paths=[
        Path("./frames/hero.jpg"),
        Path("./frames/detail-a.jpg"),
        Path("./frames/detail-b.jpg"),
        Path("./frames/detail-c.jpg"),
        Path("./frames/detail-d.jpg"),
    ],
    spec=spec,
)

print(canvas.image.shape)  # (2160, 3840, 3) by default
print(canvas.is_complete)  # True
```

Incremental manual build with an empty 4K preview canvas:

```python
from pytimeslice import (
    TimesliceSpec,
    assign_image_to_slot,
    create_manual_timeslice,
)

spec = TimesliceSpec(layout="diagonal", num_slices=5)

canvas = create_manual_timeslice(spec)  # defaults to 3840x2160
canvas = assign_image_to_slot(canvas, 0, first_frame)
canvas = assign_image_to_slot(canvas, 1, second_frame)

preview = canvas.image
slot_map = canvas.layout_description.slot_map
print(canvas.filled_slot_indices)  # [0, 1]
print(canvas.is_complete)  # False until every slot is assigned
```

Empty slots render as black in the preview image, which makes the incremental
canvas suitable for a client that wants to show progress while the user fills
each slice manually. `canvas.layout_description` reuses the same layout
metadata returned by `describe_layout(...)`, so a client can initialize the
geometry once and then keep filling slots against that stable slot map.

## CLI Usage

A CLI interface is provided on top of the engine so a folder of source
frames, or sampled frames from a video, can be rendered directly from the
command line.

```sh
pytimeslice ./frames --orientation vertical --slices 20
```

```sh
pytimeslice ./clip.mp4 ./out/video-timeslice.png --video --slices 20
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

Manual assignment is also available from the CLI. In this mode, the first
positional path is the output file, not an input folder.

Render a custom ordered 5-slice composition from explicit paths:

```sh
pytimeslice ./out/manual-order.png \
  --assigned-path ./frames/a.jpg \
  --assigned-path ./frames/b.jpg \
  --assigned-path ./frames/c.jpg \
  --assigned-path ./frames/d.jpg \
  --assigned-path ./frames/e.jpg \
  --orientation horizontal \
  --slices 5
```

Render a partial preview with only some slots filled:

```sh
pytimeslice ./out/manual-preview.png \
  --slot-path 1 ./frames/b.jpg \
  --slot-path 3 ./frames/d.jpg \
  --orientation horizontal \
  --slices 5
```

Initialize an empty 4K manual canvas:

```sh
pytimeslice ./out/manual-empty.png \
  --manual-empty \
  --layout diagonal \
  --slices 5
```

Render a random-layout animated GIF by advancing the random seed each frame:

```sh
pytimeslice ./frames ./out/random-shuffle.gif \
  --layout random \
  --random-blocks 128 \
  --random-seed 7 \
  --animate \
  --animation-mode random \
  --animation-format gif \
  --animation-frame-count 8 \
  --animation-frame-duration-ms 180 \
  --animation-loops 2 \
  --animation-smooth-loop
```

Render a random-layout video export by advancing the random seed each frame:

```sh
pytimeslice ./frames ./out/random-shuffle.mov \
  --layout random \
  --random-blocks 128 \
  --random-seed 7 \
  --animate \
  --animation-mode random \
  --animation-format mov \
  --animation-frame-count 8 \
  --animation-fps 12 \
  --animation-loops 2 \
  --animation-smooth-loop
```

Render a progression video export:

```sh
pytimeslice ./frames ./out/progression.mp4 \
  --animate \
  --animation-mode progression \
  --animation-format mp4 \
  --animation-fps 12 \
  --animation-loops 2 \
  --animation-smooth-loop \
  --orientation vertical
```

Video exports require `ffmpeg` on `PATH` and support `.mp4` or `.mov` output
paths. The legacy `--progression-gif`, `--random-gif`, `--progression-video`,
and `--random-video` flags still work, but `--animate` is the preferred CLI
entrypoint.

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

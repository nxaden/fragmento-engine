# Quickstart

## Python API

```python
from pathlib import Path

from pytimeslice import SliceEffects, TimesliceSpec, render_folder

spec = TimesliceSpec(
    orientation="vertical",
    num_slices=20,
    effects=SliceEffects(
        border_width=2,
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

response = render_folder(Path("./frames"), spec=spec)
print(response.result.image.shape)
```

To render and save explicitly:

```python
from pathlib import Path

from pytimeslice import render_folder_to_file

saved = render_folder_to_file(Path("./frames"))
print(saved.output_file)
```

To render a random-layout animated GIF:

```python
from pathlib import Path

from pytimeslice import TimesliceSpec, render_random_gif

animated = render_random_gif(
    input_folder=Path("./frames"),
    spec=TimesliceSpec(layout="random", num_blocks=128, random_seed=7),
    frame_count=8,
    frame_duration_ms=180,
    smooth_loop=True,
)
```

Built-in mask layouts are also available from the Python API:

```python
from pytimeslice import TimesliceSpec, render_images

diagonal = render_images(
    images=frames,
    spec=TimesliceSpec(layout="diagonal", num_slices=12),
)

random_blocks = render_images(
    images=frames,
    spec=TimesliceSpec(layout="random", num_blocks=128, random_seed=7),
)
```

Manual slot assignment is available when a caller wants to control the exact
image-to-slice mapping instead of letting the renderer choose frame placement:

```python
from pathlib import Path

from pytimeslice import (
    TimesliceSpec,
    assign_image_to_slot,
    create_manual_timeslice,
    render_assigned_paths,
)

spec = TimesliceSpec(orientation="horizontal", num_slices=5)

final_canvas = render_assigned_paths(
    paths=[
        Path("./frames/a.jpg"),
        Path("./frames/b.jpg"),
        Path("./frames/c.jpg"),
        Path("./frames/d.jpg"),
        Path("./frames/e.jpg"),
    ],
    spec=spec,
)

builder = create_manual_timeslice(spec)  # defaults to 3840x2160
builder = assign_image_to_slot(builder, 0, first_frame)
builder = assign_image_to_slot(builder, 1, second_frame)

print(final_canvas.is_complete)
print(builder.filled_slot_indices)
```

For manual assignment, `spec.num_slices` must be set explicitly. Unfilled slots
render as black in the preview image.

## CLI

```sh
pytimeslice ./frames --orientation vertical --slices 20
```

If no output path is provided, `pytimeslice` writes a timestamped file into an
`out/` folder next to the input folder.

Progression GIF example:

```sh
pytimeslice ./frames \
  --progression-gif \
  --gif-smooth-loop \
  --gif-frame-duration-ms 180 \
  --orientation vertical
```

Other layout examples:

```sh
pytimeslice ./frames --layout circular --slices 24

pytimeslice ./frames --layout random --random-blocks 128 --random-seed 7

pytimeslice ./frames --layout mask --layout-mask ./masks/layout.npy --slices 24
```

Manual CLI assignment examples:

```sh
pytimeslice ./out/manual-order.png \
  --assigned-path ./frames/a.jpg \
  --assigned-path ./frames/b.jpg \
  --assigned-path ./frames/c.jpg \
  --assigned-path ./frames/d.jpg \
  --assigned-path ./frames/e.jpg \
  --orientation horizontal \
  --slices 5

pytimeslice ./out/manual-preview.png \
  --slot-path 1 ./frames/b.jpg \
  --slot-path 3 ./frames/d.jpg \
  --orientation horizontal \
  --slices 5

pytimeslice ./out/manual-empty.png \
  --manual-empty \
  --layout diagonal \
  --slices 5
```

Random-layout animated GIF:

```sh
pytimeslice ./frames ./out/random-shuffle.gif \
  --layout random \
  --random-blocks 128 \
  --random-seed 7 \
  --random-gif \
  --random-gif-frames 8 \
  --gif-smooth-loop \
  --gif-frame-duration-ms 180
```

In manual mode, the first positional path is the output file. Unassigned slots
render as black, and the manual canvas defaults to 3840x2160 unless you pass
`--canvas-width` and `--canvas-height`.

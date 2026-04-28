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
```

The older `render_progression_gif(...)`, `render_random_gif(...)`,
`render_progression_video(...)`, and `render_random_video(...)` helpers remain
available as compatibility wrappers.

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
    describe_layout,
    render_assigned_paths,
)

spec = TimesliceSpec(orientation="horizontal", num_slices=5)
layout = describe_layout(spec, width=3840, height=2160)

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

print(layout.slots[0].bounds)
print(layout.mask_for_slot(0).shape)
print(final_canvas.is_complete)
print(builder.filled_slot_indices)
print(builder.layout_description.slot_count)
```

For manual assignment, `spec.num_slices` must be set explicitly. Unfilled slots
render as black in the preview image. `describe_layout(...)` exposes the stable
slot map, per-slot bounds, and a color-coded preview image that a future client
can use before any slot content is assigned.

The same metadata can be serialized into a JSON-safe transport payload:

```python
import json

from pytimeslice import (
    deserialize_layout,
    export_layout_json,
    import_layout_json,
    serialize_layout,
)

payload = serialize_layout(layout, include_preview_image=False)
round_trip = deserialize_layout(json.loads(json.dumps(payload)))

saved_file = export_layout_json(layout, "./out/layout-metadata.json")
loaded = import_layout_json(saved_file)
```

Client-edited slot maps can be validated and applied to an existing manual
canvas:

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

## CLI

```sh
pytimeslice ./frames --orientation vertical --slices 20
```

If no output path is provided, `pytimeslice` writes a timestamped file into an
`out/` folder next to the input folder.

Unified animation CLI example:

```sh
pytimeslice ./frames \
  --animate \
  --animation-mode progression \
  --animation-format gif \
  --animation-frame-duration-ms 180 \
  --animation-loops 2 \
  --animation-smooth-loop \
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
  --animate \
  --animation-mode random \
  --animation-format gif \
  --animation-frame-count 8 \
  --animation-frame-duration-ms 180 \
  --animation-loops 2 \
  --animation-smooth-loop
```

Random-layout video export:

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

Progression video export:

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

The legacy animation flags still work, but `--animate` is the preferred CLI
entrypoint.

In manual mode, the first positional path is the output file. Unassigned slots
render as black, and the manual canvas defaults to 3840x2160 unless you pass
`--canvas-width` and `--canvas-height`.

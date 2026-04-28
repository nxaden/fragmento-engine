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

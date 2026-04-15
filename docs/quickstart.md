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

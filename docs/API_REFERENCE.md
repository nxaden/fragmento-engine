# API Reference

## Overview

Fragmento Engine exposes a small public API at the package root for the common
library use case:

```python
from fragmento_engine import (
    SliceEffects,
    TimesliceSpec,
    render_folder,
    render_images,
    render_progression_gif,
)
```

For advanced usage, lower-level modules are also available under
`fragmento_engine.application`, `fragmento_engine.domain`,
`fragmento_engine.infrastructure`, and `fragmento_engine.interface`.

## Public API

### `fragmento_engine.TimesliceSpec`

```python
TimesliceSpec(
    orientation: Literal["vertical", "horizontal"] = "vertical",
    num_slices: int | None = None,
    reverse_time: bool = False,
    effects: SliceEffects | None = None,
)
```

Immutable render specification describing how a timeslice should be built.

Fields:

- `orientation`: Slice direction. `"vertical"` creates left-to-right strips.
  `"horizontal"` creates top-to-bottom strips.
- `num_slices`: Number of output bands. If omitted, one slice is generated per
  input image.
- `reverse_time`: Reverses the frame order used across the output span.
- `effects`: Optional `SliceEffects` configuration applied at slice
  boundaries.

Raises:

- `ValueError`: Raised later in the render pipeline if the requested slice count
  is less than `1` or exceeds the available output pixel span.

### `fragmento_engine.render_images`

```python
render_images(
    images: list[RGBImage],
    spec: TimesliceSpec | None = None,
) -> CompositeResult
```

Render a timeslice directly from in-memory RGB images.

Parameters:

- `images`: Ordered sequence of `numpy.uint8` RGB arrays with identical shape
  `(height, width, 3)`.
- `spec`: Optional render specification. Defaults to `TimesliceSpec()`.

Returns:

- `CompositeResult`: Rendered image plus the slice plan and the frame indices
  used in the output.

Raises:

- `ValueError`: If no images are supplied, any image is not RGB, image shapes do
  not match, or the render specification is invalid.

Example:

```python
from fragmento_engine import SliceEffects, TimesliceSpec, render_images

result = render_images(
    images=frames,
    spec=TimesliceSpec(
        orientation="vertical",
        num_slices=20,
        effects=SliceEffects(border_width=2, feather_width=6),
    ),
)

print(result.image.shape)
print(result.used_frame_indices)
```

### `fragmento_engine.render_folder`

```python
render_folder(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: Literal["crop", "resize"] = "crop",
) -> RenderResponse
```

Load an image sequence from a folder, render a timeslice, and save the result
to disk.

Parameters:

- `input_folder`: Directory containing the source images.
- `output_file`: Optional destination path for the rendered image. If omitted,
  a timestamped `.png` is written to an `out/` folder next to `input_folder`.
- `spec`: Optional render specification. Defaults to `TimesliceSpec()`.
- `resize_mode`: Strategy used when later source images do not match the base
  frame size:
  - `"crop"`: Resize to fill, then center crop.
  - `"resize"`: Directly resize to the base frame size.

Returns:

- `RenderResponse`: Composite output plus the ordered input paths used.

Raises:

- `ValueError`: If the folder does not exist, is not a directory, contains no
  supported images, or the render specification is invalid.
- `OSError`: If image loading or output writing fails.

Example:

```python
from pathlib import Path

from fragmento_engine import SliceEffects, TimesliceSpec, render_folder

response = render_folder(
    input_folder=Path("./frames"),
    spec=TimesliceSpec(
        orientation="horizontal",
        num_slices=24,
        reverse_time=False,
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
    ),
    resize_mode="crop",
)

print(response.result.image.shape)
print(len(response.input_paths))
print(response.output_file)
```

### `fragmento_engine.render_progression_gif`

```python
render_progression_gif(
    input_folder: Path,
    output_file: Path | None = None,
    spec: TimesliceSpec | None = None,
    resize_mode: Literal["crop", "resize"] = "crop",
    frame_duration_ms: int = 250,
    smooth_loop: bool = False,
) -> RenderResponse
```

Load an image sequence from a folder, render a power-of-two slice progression,
and save it as an animated GIF.

Behavior:

- Starts at `1` slice.
- Doubles the slice count on each frame.
- Includes the first count that exceeds the number of input images when the
  image span can still support it.
- When `smooth_loop=True`, appends the reverse walk through the slice counts
  without duplicating the peak frame.
- Writes a timestamped `.gif` into an `out/` folder next to `input_folder`
  when `output_file` is omitted.

Returns:

- `RenderResponse`: Final frame result, ordered input paths, saved GIF path,
  and the rendered progression slice counts.

Example:

```python
from pathlib import Path

from fragmento_engine import SliceEffects, TimesliceSpec, render_progression_gif

response = render_progression_gif(
    input_folder=Path("./frames"),
    spec=TimesliceSpec(
        orientation="vertical",
        reverse_time=False,
        effects=SliceEffects(
            border_width=4,
            border_color_mode="gradient",
            shadow_width=8,
            highlight_width=4,
            feather_width=6,
            curve="smoothstep",
        ),
    ),
    frame_duration_ms=180,
    smooth_loop=True,
)

print(response.output_file)
print(response.slice_counts)
```

## Data Types

### `fragmento_engine.domain.models`

#### `Orientation`

```python
Orientation = Literal["vertical", "horizontal"]
```

#### `BoundaryCurve`

```python
BoundaryCurve = Literal["linear", "smoothstep", "cosine", "hard"]
```

Shared ramp shape used by feather, shadow, highlight, and gradient borders.

#### `BorderColorMode`

```python
BorderColorMode = Literal["solid", "auto", "gradient"]
```

Controls whether borders use a fixed color, an auto-sampled seam color, or a
sampled left-to-right gradient.

#### `ResizeMode`

```python
ResizeMode = Literal["crop", "resize"]
```

Resize behavior used by folder-based loading and application-layer services.

#### `RGBImage`

```python
RGBImage = numpy.typing.NDArray[numpy.uint8]
```

Represents an image array with shape `(height, width, 3)`.

#### `RGBColor`

```python
RGBColor = tuple[int, int, int]
```

Represents a single RGB color such as `(255, 255, 255)`.

#### `FrameRef`

```python
FrameRef(index: int, path: Path)
```

Reference to a source frame on disk.

#### `SequenceInfo`

```python
SequenceInfo(
    frames: list[FrameRef],
    height: int,
    width: int,
    channels: int = 3,
)
```

Metadata describing a normalized frame sequence.

#### `SliceBand`

```python
SliceBand(frame_index: int, start: int, end: int)
```

Describes one band in the output composite:

- `frame_index`: Source frame selected for the band.
- `start`: Inclusive band start pixel on the active axis.
- `end`: Exclusive band end pixel on the active axis.

#### `SliceEffects`

```python
SliceEffects(
    border_width: int = 0,
    border_color: RGBColor = (255, 255, 255),
    border_opacity: float = 1.0,
    border_color_mode: BorderColorMode = "solid",
    shadow_width: int = 0,
    shadow_opacity: float = 0.35,
    highlight_width: int = 0,
    highlight_opacity: float = 0.35,
    highlight_color: RGBColor = (255, 255, 255),
    feather_width: int = 0,
    curve: BoundaryCurve = "linear",
)
```

Optional boundary treatments applied after the base timeslice is assembled.

- `border_width`: Thickness of the divider line centered on each slice
  boundary.
- `border_color`: Divider color used when `border_color_mode="solid"`.
- `border_opacity`: Border blend strength from `0.0` to `1.0`.
- `border_color_mode`: Chooses a fixed color, an auto-sampled seam color, or a
  seam-derived gradient.
- `shadow_width`: Inner shadow width in pixels on each side of a boundary.
- `shadow_opacity`: Shadow strength from `0.0` to `1.0`.
- `highlight_width`: Inner highlight width in pixels on each side of a
  boundary.
- `highlight_opacity`: Highlight strength from `0.0` to `1.0`.
- `highlight_color`: Highlight color used when `highlight_width > 0`.
- `feather_width`: Blend width in pixels applied inside each neighboring slice.
- `curve`: Ramp shape used by feather, shadow, highlight, and gradient borders.

#### `TimeslicePlan`

```python
TimeslicePlan(
    orientation: Orientation,
    bands: list[SliceBand],
)
```

Concrete slice layout generated from a `TimesliceSpec`.

#### `CompositeResult`

```python
CompositeResult(
    image: RGBImage,
    plan: TimeslicePlan,
    used_frame_indices: list[int],
)
```

Final render output plus traceable planning metadata.

## Application Layer

### `fragmento_engine.application.services.RenderRequest`

```python
RenderRequest(
    input_folder: Path,
    spec: TimesliceSpec,
    resize_mode: Literal["crop", "resize"] = "crop",
)
```

Structured input for the folder-based render workflow.

### `fragmento_engine.application.services.RenderResponse`

```python
RenderResponse(
    result: CompositeResult,
    input_paths: list[Path],
    output_file: Path | None = None,
    slice_counts: list[int] | None = None,
)
```

Structured output for the folder-based render workflow.

### `fragmento_engine.application.services.ImageSequenceLoader`

Protocol used by the application service to discover and load image sequences.

Methods:

```python
get_image_paths(folder: Path) -> list[Path]
load_images(
    paths: Sequence[Path],
    resize_mode: Literal["crop", "resize"] = "crop",
) -> list[RGBImage]
```

### `fragmento_engine.application.services.ImageWriter`

Protocol used by the application service to save rendered images.

Methods:

```python
save(image: RGBImage, output_file: Path) -> None
save_gif(
    images: Sequence[RGBImage],
    output_file: Path,
    *,
    duration_ms: int = 250,
) -> None
```

### `fragmento_engine.application.services.RenderTimesliceService`

```python
RenderTimesliceService(
    sequence_loader: ImageSequenceLoader,
    image_writer: ImageWriter | None = None,
)
```

Application service that coordinates the folder-based render workflow.

Methods:

#### `render`

```python
render(request: RenderRequest) -> RenderResponse
```

Validates the input folder, discovers image paths, loads normalized images,
renders the composite, and returns the result.

#### `render_to_file`

```python
render_to_file(
    request: RenderRequest,
    output_file: Path | None = None,
) -> RenderResponse
```

Runs `render`, then persists the rendered image through the configured writer.

#### `render_progression_gif_to_file`

```python
render_progression_gif_to_file(
    request: RenderRequest,
    output_file: Path | None = None,
    *,
    duration_ms: int = 250,
    smooth_loop: bool = False,
) -> RenderResponse
```

Builds a power-of-two slice progression and persists it as an animated GIF.

#### `create_render_service`

```python
create_render_service() -> RenderTimesliceService
```

Factory defined in `fragmento_engine.app` that wires the default production
adapters:

- `PILImageSequenceLoader`
- `PILImageWriter`

## Domain Functions

### `fragmento_engine.domain.planner.build_timeslice_plan`

```python
build_timeslice_plan(
    images: Sequence[RGBImage],
    spec: TimesliceSpec,
) -> TimeslicePlan
```

Build a concrete slice plan from normalized source images.

Behavior:

- Validates that images are RGB and share a common shape.
- Uses `spec.num_slices` or defaults to `len(images)`.
- Maps output bands to source frames with evenly spaced frame indices.
- Splits the active output axis into evenly spaced pixel bands.

Raises:

- `ValueError`: If no images are supplied, image shapes are invalid,
  `num_slices < 1`, `orientation` is invalid, or `num_slices` exceeds the
  output pixel span.

### `fragmento_engine.domain.compositor.apply_timeslice_plan`

```python
apply_timeslice_plan(
    images: Sequence[RGBImage],
    plan: TimeslicePlan,
    effects: SliceEffects | None = None,
) -> CompositeResult
```

Apply a previously generated `TimeslicePlan` to a normalized image sequence.

### `fragmento_engine.domain.compositor.build_timeslice`

```python
build_timeslice(
    images: Sequence[RGBImage],
    spec: TimesliceSpec | None = None,
) -> CompositeResult
```

Convenience wrapper that combines planning and compositing.

## Infrastructure

### `fragmento_engine.infrastructure.image_loader.VALID_EXTENSIONS`

```python
{".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
```

Supported file extensions for folder-based discovery.

### `fragmento_engine.infrastructure.image_loader.center_crop_to_size`

```python
center_crop_to_size(
    img: PIL.Image.Image,
    target_w: int,
    target_h: int,
) -> PIL.Image.Image
```

Resize an image to fill the target size, then crop the centered region.

### `fragmento_engine.infrastructure.image_loader.PILImageSequenceLoader`

Pillow-based adapter that implements the `ImageSequenceLoader` protocol.

Methods:

```python
get_image_paths(folder: Path) -> list[Path]
load_images(
    paths: Sequence[Path],
    resize_mode: Literal["crop", "resize"] = "crop",
) -> list[RGBImage]
```

Notes:

- Paths are returned in sorted order.
- The first image establishes the canonical output size.
- Later images are cropped or resized to match the first image.

### `fragmento_engine.infrastructure.image_writer.PILImageWriter`

Pillow-based adapter that implements the `ImageWriter` protocol.

Methods:

```python
save(image: RGBImage, output_file: Path) -> None
save_gif(
    images: Sequence[RGBImage],
    output_file: Path,
    *,
    duration_ms: int = 250,
) -> None
```

Behavior:

- Creates parent directories as needed.
- Saves the output with Pillow using the destination file extension.

## CLI Module

The CLI lives in `fragmento_engine.interface.cli`.

### `build_parser`

```python
build_parser() -> argparse.ArgumentParser
```

Creates the command-line parser for the `fragmento` command.

### `main`

```python
main() -> None
```

Parses CLI arguments, builds a `TimesliceSpec`, renders the folder, and prints
basic status information.

Supported arguments:

- `input_folder`
- `output_file`
- `--orientation {vertical,horizontal}`
- `--slices`
- `--resize-mode {crop,resize}`
- `--progression-gif`
- `--gif-frame-duration-ms`
- `--gif-smooth-loop`
- `--reverse-time`
- `--border`
- `--border-color`
- `--border-opacity`
- `--border-color-mode`
- `--shadow`
- `--shadow-opacity`
- `--highlight`
- `--highlight-opacity`
- `--highlight-color`
- `--feather`
- `--curve`

## Stability Guide

Prefer the package root for normal library usage:

```python
from fragmento_engine import (
    SliceEffects,
    TimesliceSpec,
    render_folder,
    render_images,
    render_progression_gif,
)
```

Use lower-level modules when you need tighter control over the render pipeline:

- `fragmento_engine.application.services`: Workflow orchestration and service
  boundaries.
- `fragmento_engine.domain.*`: Planning and compositing primitives.
- `fragmento_engine.infrastructure.*`: Pillow-based adapters for file I/O.
- `fragmento_engine.interface.cli`: Command-line entry point.

# Usage Examples

This document collects practical CLI recipes for experimenting with the
timeslice overlay system.

Use `pytimeslice` if the package is installed. If not, replace it with:

```sh
python -m pytimeslice.interface.cli
```

If you omit the output path, `pytimeslice` writes a timestamped file into an
`out/` folder next to the input folder.

## Highlight Only

```sh
pytimeslice ./frames ./out/highlight-only.jpg \
  --orientation vertical \
  --slices 24 \
  --highlight 6 \
  --highlight-opacity 0.25
```

## Warm Highlight

```sh
pytimeslice ./frames ./out/highlight-warm.jpg \
  --orientation vertical \
  --slices 24 \
  --highlight 8 \
  --highlight-opacity 0.35 \
  --highlight-color '#ffd7a1'
```

## Soft Fixed Border

```sh
pytimeslice ./frames ./out/border-soft.jpg \
  --orientation vertical \
  --slices 24 \
  --border 4 \
  --border-color '#ffffff' \
  --border-opacity 0.35
```

## Auto-Sampled Border

```sh
pytimeslice ./frames ./out/border-auto.jpg \
  --orientation vertical \
  --slices 24 \
  --border 5 \
  --border-color-mode auto \
  --border-opacity 0.8
```

## Gradient Border

```sh
pytimeslice ./frames ./out/border-gradient.jpg \
  --orientation vertical \
  --slices 24 \
  --border 8 \
  --border-color-mode gradient \
  --border-opacity 0.9
```

## Curve Comparison

Linear:

```sh
pytimeslice ./frames ./out/curve-linear.jpg \
  --orientation vertical \
  --slices 24 \
  --border 6 \
  --border-color-mode gradient \
  --shadow 10 \
  --shadow-opacity 0.35 \
  --highlight 6 \
  --highlight-opacity 0.2 \
  --feather 8 \
  --curve linear
```

Smoothstep:

```sh
pytimeslice ./frames ./out/curve-smoothstep.jpg \
  --orientation vertical \
  --slices 24 \
  --border 6 \
  --border-color-mode gradient \
  --shadow 10 \
  --shadow-opacity 0.35 \
  --highlight 6 \
  --highlight-opacity 0.2 \
  --feather 8 \
  --curve smoothstep
```

Cosine:

```sh
pytimeslice ./frames ./out/curve-cosine.jpg \
  --orientation vertical \
  --slices 24 \
  --border 6 \
  --border-color-mode gradient \
  --shadow 10 \
  --shadow-opacity 0.35 \
  --highlight 6 \
  --highlight-opacity 0.2 \
  --feather 8 \
  --curve cosine
```

Hard:

```sh
pytimeslice ./frames ./out/curve-hard.jpg \
  --orientation vertical \
  --slices 24 \
  --border 6 \
  --border-color-mode gradient \
  --shadow 10 \
  --shadow-opacity 0.35 \
  --highlight 6 \
  --highlight-opacity 0.2 \
  --feather 8 \
  --curve hard
```

## Full Overlay Stack

```sh
pytimeslice ./frames ./out/full-overlay.jpg \
  --orientation horizontal \
  --slices 30 \
  --reverse-time \
  --border 6 \
  --border-color-mode gradient \
  --border-opacity 0.75 \
  --shadow 12 \
  --shadow-opacity 0.4 \
  --highlight 5 \
  --highlight-opacity 0.22 \
  --highlight-color '#fff2cc' \
  --feather 10 \
  --curve smoothstep
```

## Progression GIF

```sh
pytimeslice ./frames \
  --animate \
  --animation-mode progression \
  --animation-format gif \
  --animation-frame-duration-ms 180 \
  --animation-loops 2 \
  --animation-smooth-loop \
  --orientation vertical \
  --border 4 \
  --border-color-mode gradient \
  --border-opacity 0.8 \
  --shadow 8 \
  --shadow-opacity 0.35 \
  --highlight 4 \
  --highlight-opacity 0.2 \
  --feather 6 \
  --curve smoothstep
```

## Progression Video

```sh
pytimeslice ./frames ./out/progression.mp4 \
  --animate \
  --animation-mode progression \
  --animation-format mp4 \
  --animation-fps 12 \
  --animation-loops 2 \
  --animation-smooth-loop \
  --orientation vertical \
  --border 4 \
  --border-color-mode gradient \
  --border-opacity 0.8 \
  --shadow 8 \
  --shadow-opacity 0.35 \
  --highlight 4 \
  --highlight-opacity 0.2 \
  --feather 6 \
  --curve smoothstep
```

## Diagonal Layout

```sh
pytimeslice ./frames ./out/diagonal-layout.jpg \
  --layout diagonal \
  --slices 24
```

## Circular Layout

```sh
pytimeslice ./frames ./out/circular-layout.jpg \
  --layout circular \
  --slices 24
```

## Random Block Layout

```sh
pytimeslice ./frames ./out/random-layout.jpg \
  --layout random \
  --random-blocks 128 \
  --random-seed 7
```

## Random Shuffle GIF

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

This keeps the same random block count but advances the random seed once per
forward keyframe.

## Random Shuffle Video

```sh
pytimeslice ./frames ./out/random-shuffle.mp4 \
  --layout random \
  --random-blocks 128 \
  --random-seed 7 \
  --animate \
  --animation-mode random \
  --animation-format mp4 \
  --animation-frame-count 8 \
  --animation-fps 12 \
  --animation-loops 2 \
  --animation-smooth-loop
```

This emits the same shuffled random layout idea as the GIF workflow, but
encodes it as `.mp4` or `.mov`. Video export requires `ffmpeg` on `PATH`.

## User-Defined Mask Layout

```sh
pytimeslice ./frames ./out/custom-mask-layout.jpg \
  --layout mask \
  --layout-mask ./masks/layout.npy \
  --slices 24
```

## Manual Ordered Slots

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

## Manual Partial Preview

```sh
pytimeslice ./out/manual-preview.png \
  --slot-path 1 ./frames/b.jpg \
  --slot-path 3 ./frames/d.jpg \
  --orientation horizontal \
  --slices 5
```

Unassigned slots render as black. This makes it possible to generate a
preview while another client keeps track of which slots have already been
filled.

## Manual Empty Canvas

```sh
pytimeslice ./out/manual-empty.png \
  --manual-empty \
  --layout diagonal \
  --slices 5
```

In manual mode, the first positional path is the output file. The canvas
defaults to 3840x2160 unless you pass `--canvas-width` and `--canvas-height`.

## Practice Tip

Keep the same input frames and output dimensions, then change only one option at
a time:

- `--border-color-mode`
- `--border-opacity`
- `--curve`
- `--highlight-color`

That makes the visual impact of each control much easier to judge.

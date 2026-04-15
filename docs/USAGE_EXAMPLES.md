# Usage Examples

This document collects practical CLI recipes for experimenting with the
timeslice overlay system.

Use `fragmento` if the package is installed. If not, replace it with:

```sh
python -m fragmento_engine.interface.cli
```

If you omit the output path, Fragmento writes a timestamped file into an
`out/` folder next to the input folder.

## Highlight Only

```sh
fragmento ./frames ./out/highlight-only.jpg \
  --orientation vertical \
  --slices 24 \
  --highlight 6 \
  --highlight-opacity 0.25
```

## Warm Highlight

```sh
fragmento ./frames ./out/highlight-warm.jpg \
  --orientation vertical \
  --slices 24 \
  --highlight 8 \
  --highlight-opacity 0.35 \
  --highlight-color '#ffd7a1'
```

## Soft Fixed Border

```sh
fragmento ./frames ./out/border-soft.jpg \
  --orientation vertical \
  --slices 24 \
  --border 4 \
  --border-color '#ffffff' \
  --border-opacity 0.35
```

## Auto-Sampled Border

```sh
fragmento ./frames ./out/border-auto.jpg \
  --orientation vertical \
  --slices 24 \
  --border 5 \
  --border-color-mode auto \
  --border-opacity 0.8
```

## Gradient Border

```sh
fragmento ./frames ./out/border-gradient.jpg \
  --orientation vertical \
  --slices 24 \
  --border 8 \
  --border-color-mode gradient \
  --border-opacity 0.9
```

## Curve Comparison

Linear:

```sh
fragmento ./frames ./out/curve-linear.jpg \
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
fragmento ./frames ./out/curve-smoothstep.jpg \
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
fragmento ./frames ./out/curve-cosine.jpg \
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
fragmento ./frames ./out/curve-hard.jpg \
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
fragmento ./frames ./out/full-overlay.jpg \
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
fragmento ./frames \
  --progression-gif \
  --gif-smooth-loop \
  --gif-frame-duration-ms 180 \
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

## Practice Tip

Keep the same input frames and output dimensions, then change only one option at
a time:

- `--border-color-mode`
- `--border-opacity`
- `--curve`
- `--highlight-color`

That makes the visual impact of each control much easier to judge.

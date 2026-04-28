"""Command-line interface for rendering pytimeslice outputs."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import numpy.typing as npt
from PIL import Image

from pytimeslice import (
    assign_path_to_slot,
    create_manual_timeslice,
    render_assigned_paths,
    render_folder_to_file,
    render_progression_gif,
    render_random_gif,
)
from pytimeslice import SliceEffects, TimesliceSpec
from pytimeslice.app import DEFAULT_CANVAS_HEIGHT, DEFAULT_CANVAS_WIDTH
from pytimeslice.domain.models import validate_timeslice_spec
from pytimeslice.infrastructure.image_writer import PILImageWriter


def _parse_non_negative_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("Expected an integer value.") from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError("Value must be at least 0.")

    return parsed


def _parse_positive_int(value: str) -> int:
    parsed = _parse_non_negative_int(value)
    if parsed == 0:
        raise argparse.ArgumentTypeError("Value must be greater than 0.")
    return parsed


def _parse_color(value: str) -> tuple[int, int, int]:
    raw = value.strip()

    if "," in raw:
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 3:
            raise argparse.ArgumentTypeError(
                "Expected a color in R,G,B format with exactly 3 channels."
            )

        try:
            channels = (
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
            )
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "RGB channels must be integers between 0 and 255."
            ) from exc
    else:
        hex_value = raw.removeprefix("#")
        if len(hex_value) != 6:
            raise argparse.ArgumentTypeError(
                "Expected a color in #RRGGBB or R,G,B format."
            )

        try:
            channels = (
                int(hex_value[0:2], 16),
                int(hex_value[2:4], 16),
                int(hex_value[4:6], 16),
            )
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "Hex colors must use valid hexadecimal digits."
            ) from exc

    if any(channel < 0 or channel > 255 for channel in channels):
        raise argparse.ArgumentTypeError("Color channels must be between 0 and 255.")

    return channels


def _build_effects(args: argparse.Namespace) -> SliceEffects | None:
    if (
        args.border <= 0
        and args.shadow <= 0
        and args.highlight <= 0
        and args.feather <= 0
    ):
        return None

    return SliceEffects(
        border_width=args.border,
        border_color=args.border_color,
        border_opacity=args.border_opacity,
        border_color_mode=args.border_color_mode,
        shadow_width=args.shadow,
        shadow_opacity=args.shadow_opacity,
        highlight_width=args.highlight,
        highlight_opacity=args.highlight_opacity,
        highlight_color=args.highlight_color,
        feather_width=args.feather,
        curve=args.curve,
    )


def _load_layout_mask(mask_file: Path) -> npt.NDArray[np.float64]:
    if not mask_file.exists():
        raise ValueError(f"Layout mask file does not exist: {mask_file}")

    if mask_file.suffix.lower() == ".npy":
        loaded = np.load(mask_file, allow_pickle=False)
    else:
        try:
            with Image.open(mask_file) as opened:
                loaded = np.array(opened.convert("F"), dtype=np.float64)
        except OSError as exc:
            raise ValueError(
                "Layout mask must be a readable .npy file or single-channel image."
            ) from exc

    if loaded.ndim != 2:
        raise ValueError("Layout mask must be a 2D array or single-channel image.")

    return loaded.astype(np.float64, copy=False)


def _manual_mode_requested(args: argparse.Namespace) -> bool:
    return bool(args.assigned_paths or args.slot_paths or args.manual_empty)


def _resolve_manual_output_file(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> Path:
    if args.output_file is not None:
        parser.error(
            "Manual assignment mode accepts only one positional path: output_file."
        )

    if args.input_folder is None:
        parser.error("Manual assignment mode requires an output_file path.")

    if args.input_folder.suffix == "":
        return args.input_folder.with_suffix(".png")

    return args.input_folder


def _parse_slot_paths(
    raw_slot_paths: list[list[str]] | None,
    *,
    slot_count: int,
    parser: argparse.ArgumentParser,
) -> list[tuple[int, Path]]:
    assignments: list[tuple[int, Path]] = []
    seen_indices: set[int] = set()

    for raw_pair in raw_slot_paths or []:
        raw_index, raw_path = raw_pair
        try:
            slot_index = _parse_non_negative_int(raw_index)
        except argparse.ArgumentTypeError as exc:
            parser.error(f"Invalid --slot-path index {raw_index!r}: {exc}")

        if slot_index >= slot_count:
            parser.error(
                f"--slot-path index {slot_index} is out of range for {slot_count} slots."
            )
        if slot_index in seen_indices:
            parser.error(f"--slot-path index {slot_index} was provided more than once.")

        seen_indices.add(slot_index)
        assignments.append((slot_index, Path(raw_path)))

    return assignments


def _render_manual_assignment(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    spec: TimesliceSpec,
) -> None:
    if args.progression_gif:
        parser.error("Progression GIF is not supported with manual assignment mode.")
    if args.random_gif:
        parser.error("Random GIF is not supported with manual assignment mode.")
    if args.assigned_paths and args.slot_paths:
        parser.error("--assigned-path cannot be combined with --slot-path.")
    if args.manual_empty and (args.assigned_paths or args.slot_paths):
        parser.error("--manual-empty cannot be combined with slot assignments.")
    if spec.num_slices is None:
        parser.error("--slices is required when using manual assignment mode.")

    output_file = _resolve_manual_output_file(args, parser)

    try:
        if args.assigned_paths:
            if len(args.assigned_paths) != spec.num_slices:
                parser.error(
                    f"Expected {spec.num_slices} --assigned-path values, received "
                    f"{len(args.assigned_paths)}."
                )

            canvas = render_assigned_paths(
                paths=args.assigned_paths,
                spec=spec,
                width=args.canvas_width,
                height=args.canvas_height,
                resize_mode=args.resize_mode,
            )
        else:
            canvas = create_manual_timeslice(
                spec,
                width=args.canvas_width,
                height=args.canvas_height,
            )
            assignments = _parse_slot_paths(
                args.slot_paths,
                slot_count=canvas.slot_count,
                parser=parser,
            )
            for slot_index, path in assignments:
                canvas = assign_path_to_slot(
                    canvas,
                    slot_index,
                    path,
                    resize_mode=args.resize_mode,
                )
    except ValueError as exc:
        parser.error(str(exc))

    PILImageWriter().save(canvas.image, output_file)
    print(f"Assigned {len(canvas.filled_slot_indices)}/{canvas.slot_count} slots.")
    print(f"Saved: {output_file}")


def _build_spec(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
) -> TimesliceSpec:
    effects = _build_effects(args)

    if args.layout != "bands" and effects is not None:
        parser.error("Slice effects are currently supported only with --layout bands.")

    if args.layout != "bands" and args.orientation != "vertical":
        parser.error("--orientation is currently supported only with --layout bands.")

    layout_mask: npt.NDArray[np.float64] | None = None
    if args.layout == "mask":
        if args.layout_mask is None:
            parser.error("--layout-mask is required when --layout mask is used.")
        try:
            layout_mask = _load_layout_mask(args.layout_mask)
        except ValueError as exc:
            parser.error(str(exc))
    elif args.layout_mask is not None:
        parser.error("--layout-mask can only be used when --layout mask is selected.")

    spec = TimesliceSpec(
        orientation=args.orientation,
        layout=args.layout,
        num_slices=args.slices,
        num_blocks=args.random_blocks,
        reverse_time=args.reverse_time,
        random_seed=args.random_seed,
        effects=effects,
        layout_mask=layout_mask,
    )

    try:
        validate_timeslice_spec(spec)
    except ValueError as exc:
        parser.error(str(exc))

    return spec


def build_parser() -> argparse.ArgumentParser:
    """Create the argparse parser for the `pytimeslice` command."""
    parser = argparse.ArgumentParser(
        description="Create a time-slice image from a sequence of photos."
    )
    parser.add_argument(
        "input_folder",
        type=Path,
        nargs="?",
        default=None,
        help=(
            "Folder of source frames for standard rendering. In manual "
            "assignment mode, omit this and pass only the output path."
        ),
    )
    parser.add_argument(
        "output_file",
        type=Path,
        nargs="?",
        default=None,
        help="Optional output path for standard folder rendering.",
    )
    parser.add_argument(
        "--layout",
        choices=["bands", "diagonal", "spiral", "circular", "random", "mask"],
        default="bands",
        help=(
            "Layout strategy: straight bands, a built-in diagonal, spiral, or "
            "circular mask, a random block grid, or a user-defined mask loaded "
            "from --layout-mask."
        ),
    )
    parser.add_argument(
        "--random-blocks",
        type=_parse_positive_int,
        default=None,
        metavar="COUNT",
        help=(
            "Total block count for --layout random. Must be at least 4 and a "
            "power of 2; the renderer chooses a rectangular power-of-two grid "
            "that fits the image."
        ),
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=None,
        metavar="SEED",
        help="Optional RNG seed for --layout random.",
    )
    parser.add_argument(
        "--layout-mask",
        type=Path,
        default=None,
        metavar="PATH",
        help=(
            "User-defined layout mask for --layout mask. Supports .npy files "
            "or grayscale image files."
        ),
    )
    parser.add_argument(
        "--assigned-path",
        dest="assigned_paths",
        action="append",
        default=None,
        metavar="PATH",
        help=(
            "Manual mode: explicit ordered slot content. Repeat once per slot; "
            "list order maps directly to slice order."
        ),
    )
    parser.add_argument(
        "--slot-path",
        dest="slot_paths",
        action="append",
        nargs=2,
        default=None,
        metavar=("INDEX", "PATH"),
        help=(
            "Manual mode: assign one slot at a time by index. Repeatable. "
            "Unassigned slots render as black."
        ),
    )
    parser.add_argument(
        "--manual-empty",
        action="store_true",
        help="Manual mode: render an empty black canvas for the requested layout.",
    )
    parser.add_argument(
        "--canvas-width",
        type=_parse_positive_int,
        default=DEFAULT_CANVAS_WIDTH,
        metavar="PX",
        help="Manual mode canvas width in pixels. Defaults to 3840.",
    )
    parser.add_argument(
        "--canvas-height",
        type=_parse_positive_int,
        default=DEFAULT_CANVAS_HEIGHT,
        metavar="PX",
        help="Manual mode canvas height in pixels. Defaults to 2160.",
    )
    parser.add_argument(
        "--orientation",
        choices=["vertical", "horizontal"],
        default="vertical",
        help="Band direction for --layout bands.",
    )
    parser.add_argument("--slices", type=_parse_positive_int, default=None)
    parser.add_argument(
        "--resize-mode",
        choices=["crop", "resize"],
        default="crop",
    )
    parser.add_argument(
        "--progression-gif",
        action="store_true",
        help=(
            "Render an animated GIF with slice counts 1, 2, 4, and so on "
            "until the sequence exceeds the number of input images."
        ),
    )
    parser.add_argument(
        "--random-gif",
        action="store_true",
        help=(
            "Render an animated GIF for --layout random by advancing the "
            "random seed once per keyframe."
        ),
    )
    parser.add_argument(
        "--random-gif-frames",
        type=_parse_positive_int,
        default=8,
        metavar="COUNT",
        help="Number of forward keyframes to render for --random-gif.",
    )
    parser.add_argument(
        "--gif-frame-duration-ms",
        type=_parse_positive_int,
        default=250,
        help="Per-frame duration in milliseconds for animated GIF outputs.",
    )
    parser.add_argument(
        "--gif-smooth-loop",
        action="store_true",
        help=("Use a ping-pong GIF sequence for animated GIF outputs before looping."),
    )
    parser.add_argument("--reverse-time", action="store_true")
    parser.add_argument(
        "--border",
        type=_parse_non_negative_int,
        default=0,
        help="Divider thickness in pixels drawn at slice boundaries.",
    )
    parser.add_argument(
        "--border-color",
        type=_parse_color,
        default=(255, 255, 255),
        metavar="COLOR",
        help="Border color as #RRGGBB or R,G,B.",
    )
    parser.add_argument(
        "--border-opacity",
        type=float,
        default=1.0,
        help="Border blend strength from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--border-color-mode",
        choices=["solid", "auto", "gradient"],
        default="solid",
        help=(
            "How divider colors are resolved: fixed color, auto-sampled, "
            "or sampled gradient."
        ),
    )
    parser.add_argument(
        "--shadow",
        type=_parse_non_negative_int,
        default=0,
        help="Inner shadow width in pixels on each side of a slice boundary.",
    )
    parser.add_argument(
        "--shadow-opacity",
        type=float,
        default=0.35,
        help="Shadow strength from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--highlight",
        type=_parse_non_negative_int,
        default=0,
        help="Inner highlight width in pixels on each side of a slice boundary.",
    )
    parser.add_argument(
        "--highlight-opacity",
        type=float,
        default=0.35,
        help="Highlight strength from 0.0 to 1.0.",
    )
    parser.add_argument(
        "--highlight-color",
        type=_parse_color,
        default=(255, 255, 255),
        metavar="COLOR",
        help="Highlight color as #RRGGBB or R,G,B.",
    )
    parser.add_argument(
        "--feather",
        type=_parse_non_negative_int,
        default=0,
        help="Blend width in pixels applied inside each neighboring slice.",
    )
    parser.add_argument(
        "--curve",
        choices=["linear", "smoothstep", "cosine", "hard"],
        default="linear",
        help=(
            "Boundary ramp curve used by feather, shadow, highlight, "
            "and gradient borders."
        ),
    )
    return parser


def main() -> None:
    """Run the command-line interface."""
    parser = build_parser()
    args = parser.parse_args()
    spec = _build_spec(args, parser)
    if _manual_mode_requested(args):
        _render_manual_assignment(args, parser, spec)
        return

    if args.input_folder is None:
        parser.error("input_folder is required unless manual assignment mode is used.")
    if args.progression_gif and args.random_gif:
        parser.error("--progression-gif cannot be combined with --random-gif.")
    if args.progression_gif and spec.layout == "random":
        parser.error("Progression GIF is not currently supported with --layout random.")
    if args.random_gif and spec.layout != "random":
        parser.error("Random GIF currently requires --layout random.")

    if args.progression_gif:
        progression_response = render_progression_gif(
            input_folder=args.input_folder,
            output_file=args.output_file,
            spec=spec,
            resize_mode=args.resize_mode,
            frame_duration_ms=args.gif_frame_duration_ms,
            smooth_loop=args.gif_smooth_loop,
        )
        print(f"Rendered using {len(progression_response.input_paths)} images.")
        counts = ", ".join(
            str(count) for count in progression_response.emitted_slice_counts
        )
        print(f"Slice counts: {counts}")
        print(f"Saved: {progression_response.output_file}")
    elif args.random_gif:
        random_gif_response = render_random_gif(
            input_folder=args.input_folder,
            output_file=args.output_file,
            spec=spec,
            resize_mode=args.resize_mode,
            frame_duration_ms=args.gif_frame_duration_ms,
            frame_count=args.random_gif_frames,
            smooth_loop=args.gif_smooth_loop,
        )
        print(f"Rendered using {len(random_gif_response.input_paths)} images.")
        seeds = ", ".join(str(seed) for seed in random_gif_response.emitted_seeds)
        print(f"Seeds: {seeds}")
        print(f"Saved: {random_gif_response.output_file}")
    else:
        image_response = render_folder_to_file(
            input_folder=args.input_folder,
            output_file=args.output_file,
            spec=spec,
            resize_mode=args.resize_mode,
        )
        print(f"Rendered using {len(image_response.input_paths)} images.")
        print(f"Saved: {image_response.output_file}")


if __name__ == "__main__":
    main()

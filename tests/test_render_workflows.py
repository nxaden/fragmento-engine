from pathlib import Path

import numpy as np

from fragmento_engine.application.services import (
    RenderRequest,
    RenderTimesliceService,
)
from fragmento_engine.domain.models import RGBImage, TimesliceSpec
from fragmento_engine.interface.cli import build_parser


def _solid_frame(value: int, *, width: int = 8, height: int = 2) -> RGBImage:
    return np.full((height, width, 3), value, dtype=np.uint8)


class RecordingLoader:
    def __init__(self, paths: list[Path], images: list[RGBImage]) -> None:
        self.paths = paths
        self.images = images

    def get_image_paths(self, folder: Path) -> list[Path]:
        return self.paths

    def load_images(
        self,
        paths: list[Path],
        resize_mode: str = "crop",
    ) -> list[RGBImage]:
        return self.images


class RecordingWriter:
    def __init__(self) -> None:
        self.saved_images: list[tuple[RGBImage, Path]] = []
        self.saved_gifs: list[tuple[list[RGBImage], Path, int]] = []

    def save(self, image: RGBImage, output_file: Path) -> None:
        self.saved_images.append((image, output_file))

    def save_gif(
        self,
        images: list[RGBImage],
        output_file: Path,
        *,
        duration_ms: int = 250,
    ) -> None:
        self.saved_gifs.append((images, output_file, duration_ms))


def test_render_to_file_defaults_to_out_folder_when_output_is_omitted(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / "001.png", input_folder / "002.png"]
    images = [_solid_frame(0), _solid_frame(255)]
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=RecordingWriter(),
    )

    response = service.render_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(num_slices=2),
        )
    )

    assert response.output_file is not None
    assert response.output_file.parent == tmp_path / "out"
    assert response.output_file.suffix == ".png"
    assert response.output_file.name.endswith("-timeslice.png")


def test_render_progression_gif_uses_power_of_two_slice_counts(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        duration_ms=120,
    )

    assert response.slice_counts == [1, 2, 4, 8]
    assert response.output_file is not None
    assert response.output_file.parent == tmp_path / "out"
    assert response.output_file.suffix == ".gif"
    assert response.output_file.name.endswith("-progression.gif")
    assert len(response.result.plan.bands) == 8

    assert len(writer.saved_gifs) == 1
    frames, output_file, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 4
    assert output_file == response.output_file
    assert duration_ms == 120


def test_render_progression_gif_can_use_smooth_loop_slice_counts(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(5)]
    images = [_solid_frame(index * 10, width=16) for index in range(5)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(orientation="vertical"),
        ),
        duration_ms=120,
        smooth_loop=True,
    )

    assert response.slice_counts == [1, 2, 4, 8, 4, 2]
    assert len(response.result.plan.bands) == 8

    assert len(writer.saved_gifs) == 1
    frames, _, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 6
    assert duration_ms == 120


def test_cli_output_file_is_optional_for_progression_gif() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--progression-gif",
            "--gif-frame-duration-ms",
            "180",
            "--gif-smooth-loop",
        ]
    )

    assert args.output_file is None
    assert args.progression_gif is True
    assert args.gif_frame_duration_ms == 180
    assert args.gif_smooth_loop is True

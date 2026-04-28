from pathlib import Path

import numpy as np
import pytest

import pytimeslice.app as app_module
from pytimeslice import render_images
from pytimeslice.application.services import (
    ProgressionGifRenderResponse,
    RenderRequest,
    RenderResponse,
    RenderTimesliceService,
)
from pytimeslice.domain.models import RGBImage, SliceEffects, TimesliceSpec
from pytimeslice.interface.cli import _build_spec, build_parser


def _solid_frame(value: int, *, width: int = 8, height: int = 2) -> RGBImage:
    return np.full((height, width, 3), value, dtype=np.uint8)


class RecordingLoader:
    def __init__(self, paths: list[Path], images: list[RGBImage]) -> None:
        self.paths = paths
        self.images = images
        self.get_image_paths_calls = 0
        self.load_images_calls = 0

    def get_image_paths(self, folder: Path) -> list[Path]:
        self.get_image_paths_calls += 1
        return self.paths

    def load_images(
        self,
        paths: list[Path],
        resize_mode: str = "crop",
    ) -> list[RGBImage]:
        self.load_images_calls += 1
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


class RecordingRenderService:
    def __init__(self, response: RenderResponse) -> None:
        self.response = response
        self.render_requests: list[RenderRequest] = []
        self.render_to_file_calls: list[tuple[RenderRequest, Path | None]] = []

    def render(self, request: RenderRequest) -> RenderResponse:
        self.render_requests.append(request)
        return self.response

    def render_to_file(
        self,
        request: RenderRequest,
        output_file: Path | None = None,
    ) -> RenderResponse:
        self.render_to_file_calls.append((request, output_file))
        if output_file is None:
            return self.response
        return RenderResponse(
            result=self.response.result,
            input_paths=self.response.input_paths,
            output_file=output_file,
        )


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


def test_app_render_folder_is_pure_and_does_not_write(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    expected = RenderResponse(
        result=render_images(
            images=[_solid_frame(0), _solid_frame(255)],
            spec=TimesliceSpec(num_slices=2),
        ),
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
    )
    service = RecordingRenderService(response=expected)
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_folder(
        input_folder=input_folder,
        spec=TimesliceSpec(num_slices=2),
    )

    assert response == expected
    assert len(service.render_requests) == 1
    assert service.render_requests[0].input_folder == input_folder
    assert service.render_requests[0].spec == TimesliceSpec(num_slices=2)
    assert service.render_to_file_calls == []


def test_app_render_folder_to_file_delegates_to_explicit_save_path(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    output_file = tmp_path / "out" / "timeslice.png"
    expected = RenderResponse(
        result=render_images(
            images=[_solid_frame(0), _solid_frame(255)],
            spec=TimesliceSpec(num_slices=2),
        ),
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
    )
    service = RecordingRenderService(response=expected)
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_folder_to_file(
        input_folder=input_folder,
        output_file=output_file,
        spec=TimesliceSpec(num_slices=2),
    )

    assert response.output_file == output_file
    assert service.render_requests == []
    assert len(service.render_to_file_calls) == 1
    request, requested_output = service.render_to_file_calls[0]
    assert request.input_folder == input_folder
    assert request.spec == TimesliceSpec(num_slices=2)
    assert requested_output == output_file


def test_app_render_folder_to_file_defaults_output_path_when_omitted(
    monkeypatch,
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    expected = RenderResponse(
        result=render_images(
            images=[_solid_frame(0), _solid_frame(255)],
            spec=TimesliceSpec(num_slices=2),
        ),
        input_paths=[input_folder / "001.png", input_folder / "002.png"],
    )
    service = RecordingRenderService(response=expected)
    monkeypatch.setattr(app_module, "create_render_service", lambda: service)

    response = app_module.render_folder_to_file(
        input_folder=input_folder,
        spec=TimesliceSpec(num_slices=2),
    )

    assert len(service.render_to_file_calls) == 1
    request, requested_output = service.render_to_file_calls[0]
    assert request.input_folder == input_folder
    assert requested_output is None
    assert response.output_file is None


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

    assert isinstance(response, ProgressionGifRenderResponse)
    assert response.base_slice_counts == [1, 2, 4, 8]
    assert response.emitted_slice_counts == [1, 2, 4, 8]
    assert response.output_file.parent == tmp_path / "out"
    assert response.output_file.suffix == ".gif"
    assert response.output_file.name.endswith("-progression.gif")
    assert len(response.peak_result.plan.bands) == 8
    assert len(response.last_emitted_result.plan.bands) == 8

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

    assert isinstance(response, ProgressionGifRenderResponse)
    assert response.base_slice_counts == [1, 2, 4, 8]
    assert response.emitted_slice_counts == [1, 2, 4, 8, 4, 2]
    assert len(response.peak_result.plan.bands) == 8
    assert len(response.last_emitted_result.plan.bands) == 2

    assert len(writer.saved_gifs) == 1
    frames, _, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 6
    assert duration_ms == 120


def test_render_progression_gif_supports_mask_based_layouts(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    paths = [input_folder / f"{index:03}.png" for index in range(3)]
    images = [_solid_frame(index * 10, width=2, height=2) for index in range(3)]
    writer = RecordingWriter()
    service = RenderTimesliceService(
        sequence_loader=RecordingLoader(paths=paths, images=images),
        image_writer=writer,
    )

    response = service.render_progression_gif_to_file(
        RenderRequest(
            input_folder=input_folder,
            spec=TimesliceSpec(layout="diagonal"),
        ),
        duration_ms=90,
    )

    assert response.base_slice_counts == [1, 2, 4]
    assert response.emitted_slice_counts == [1, 2, 4]
    assert response.peak_result.plan.layout == "diagonal"
    assert response.peak_result.plan.slice_map is not None

    assert len(writer.saved_gifs) == 1
    frames, _, duration_ms = writer.saved_gifs[0]
    assert len(frames) == 3
    assert duration_ms == 90


def test_render_progression_gif_rejects_random_layout_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0, width=4, height=4)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(
        ValueError,
        match="Progression GIF is not currently supported for layout='random'.",
    ):
        service.render_progression_gif_to_file(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(layout="random", num_blocks=4),
            ),
            duration_ms=120,
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_service_rejects_invalid_effects_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(ValueError, match="effects.border_width must be at least 0."):
        service.render(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(
                    effects=SliceEffects(border_width=-1),
                ),
            )
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


def test_service_rejects_non_positive_gif_duration_before_loading_images(
    tmp_path: Path,
) -> None:
    input_folder = tmp_path / "frames"
    input_folder.mkdir()
    loader = RecordingLoader(
        paths=[input_folder / "001.png"],
        images=[_solid_frame(0)],
    )
    service = RenderTimesliceService(
        sequence_loader=loader,
        image_writer=RecordingWriter(),
    )

    with pytest.raises(ValueError, match="duration_ms must be greater than 0."):
        service.render_progression_gif_to_file(
            RenderRequest(
                input_folder=input_folder,
                spec=TimesliceSpec(),
            ),
            duration_ms=0,
        )

    assert loader.get_image_paths_calls == 0
    assert loader.load_images_calls == 0


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


def test_cli_builds_diagonal_layout_spec() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "diagonal",
            "--slices",
            "6",
            "--reverse-time",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="diagonal",
        num_slices=6,
        reverse_time=True,
    )


def test_cli_builds_circular_layout_spec() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "circular",
            "--slices",
            "6",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="circular",
        num_slices=6,
    )


def test_cli_builds_random_layout_spec() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "16",
            "--random-seed",
            "7",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="random",
        num_blocks=16,
        random_seed=7,
    )


def test_cli_accepts_rectangular_power_of_two_random_block_counts() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "128",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec == TimesliceSpec(
        orientation="vertical",
        layout="random",
        num_blocks=128,
    )


def test_cli_loads_user_defined_mask_layout_from_npy(tmp_path: Path) -> None:
    parser = build_parser()
    mask_file = tmp_path / "layout-mask.npy"
    expected_mask = np.array([[0.0, 2.0], [3.0, 1.0]], dtype=np.float64)
    np.save(mask_file, expected_mask)

    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "mask",
            "--layout-mask",
            str(mask_file),
            "--slices",
            "2",
        ]
    )

    spec = _build_spec(args, parser)

    assert spec.layout == "mask"
    assert spec.layout_mask is not None
    assert np.array_equal(spec.layout_mask, expected_mask)


def test_cli_requires_layout_mask_for_mask_layout() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "mask",
            "--slices",
            "2",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_slices_for_random_layout() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--slices",
            "8",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_invalid_random_block_count() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "random",
            "--random-blocks",
            "12",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_effects_for_non_band_layouts() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "frames",
            "--layout",
            "spiral",
            "--border",
            "1",
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_layout_mask_without_mask_layout(tmp_path: Path) -> None:
    parser = build_parser()
    mask_file = tmp_path / "layout-mask.npy"
    np.save(mask_file, np.array([[0.0]], dtype=np.float64))
    args = parser.parse_args(
        [
            "frames",
            "--layout-mask",
            str(mask_file),
        ]
    )

    with pytest.raises(SystemExit):
        _build_spec(args, parser)


def test_cli_rejects_negative_effect_widths() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "frames",
                "--border",
                "-1",
            ]
        )


def test_cli_rejects_non_positive_gif_duration() -> None:
    parser = build_parser()

    with pytest.raises(SystemExit):
        parser.parse_args(
            [
                "frames",
                "--progression-gif",
                "--gif-frame-duration-ms",
                "0",
            ]
        )

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pytimeslice import (
    ManualTimesliceCanvas,
    assign_images_to_slots,
    TimesliceSpec,
    assign_image_to_slot,
    assign_path_to_slot,
    clear_slot,
    clear_slots,
    create_manual_timeslice,
    import_slot_map,
    replace_canvas_slot_map,
    render_assigned_images,
    render_assigned_paths,
    swap_slots,
)


def _solid_frame(value: int, *, width: int, height: int) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def test_render_assigned_images_uses_explicit_slot_order() -> None:
    canvas = render_assigned_images(
        images=[
            _solid_frame(10, width=2, height=10),
            _solid_frame(200, width=2, height=10),
            _solid_frame(50, width=2, height=10),
            _solid_frame(0, width=2, height=10),
            _solid_frame(150, width=2, height=10),
        ],
        spec=TimesliceSpec(orientation="horizontal", num_slices=5),
        width=2,
        height=10,
    )

    first_column = canvas.image[:, 0, 0].tolist()
    assert first_column == [10, 10, 200, 200, 50, 50, 0, 0, 150, 150]
    assert canvas.filled_slot_indices == [0, 1, 2, 3, 4]
    assert canvas.is_complete is True


def test_create_manual_timeslice_defaults_to_empty_4k_canvas() -> None:
    canvas = create_manual_timeslice(
        TimesliceSpec(orientation="horizontal", num_slices=5),
    )

    assert isinstance(canvas, ManualTimesliceCanvas)
    assert canvas.width == 3840
    assert canvas.height == 2160
    assert canvas.slot_count == 5
    assert canvas.image.shape == (2160, 3840, 3)
    assert canvas.filled_slot_indices == []
    assert canvas.is_complete is False


def test_create_manual_timeslice_requires_explicit_num_slices() -> None:
    with pytest.raises(ValueError, match="spec.num_slices"):
        create_manual_timeslice(TimesliceSpec(orientation="horizontal"))


def test_create_manual_timeslice_rejects_random_layout() -> None:
    with pytest.raises(ValueError, match="layout='random'"):
        create_manual_timeslice(TimesliceSpec(layout="random", num_blocks=4))


def test_create_manual_timeslice_rejects_reverse_time() -> None:
    with pytest.raises(ValueError, match="does not support reverse_time"):
        create_manual_timeslice(
            TimesliceSpec(
                orientation="horizontal",
                num_slices=5,
                reverse_time=True,
            )
        )


def test_assign_image_to_slot_builds_manual_canvas_progressively() -> None:
    canvas = create_manual_timeslice(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    canvas = assign_image_to_slot(
        canvas,
        1,
        _solid_frame(100, width=6, height=2),
    )
    assert canvas.image[0, :, 0].tolist() == [0, 0, 100, 100, 0, 0]
    assert canvas.filled_slot_indices == [1]

    canvas = assign_image_to_slot(
        canvas,
        0,
        _solid_frame(50, width=6, height=2),
    )
    assert canvas.image[0, :, 0].tolist() == [50, 50, 100, 100, 0, 0]
    assert canvas.filled_slot_indices == [0, 1]


def test_render_assigned_paths_loads_images_in_slot_order(tmp_path: Path) -> None:
    paths: list[Path] = []
    for index, value in enumerate((25, 125, 225)):
        path = tmp_path / f"{index}.png"
        Image.fromarray(_solid_frame(value, width=3, height=2)).save(path)
        paths.append(path)

    canvas = render_assigned_paths(
        paths=paths,
        spec=TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    assert canvas.image[0, :, 0].tolist() == [25, 25, 125, 125, 225, 225]
    assert canvas.filled_slot_indices == [0, 1, 2]


def test_render_assigned_images_rejects_wrong_slot_count() -> None:
    with pytest.raises(ValueError, match="Expected 3 images"):
        render_assigned_images(
            images=[
                _solid_frame(10, width=6, height=2),
                _solid_frame(20, width=6, height=2),
            ],
            spec=TimesliceSpec(orientation="vertical", num_slices=3),
            width=6,
            height=2,
        )


def test_assign_path_to_slot_updates_manual_canvas_from_file(tmp_path: Path) -> None:
    path = tmp_path / "frame.png"
    Image.fromarray(_solid_frame(180, width=3, height=2)).save(path)

    canvas = create_manual_timeslice(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )
    canvas = assign_path_to_slot(canvas, 2, path)

    assert canvas.image[0, :, 0].tolist() == [0, 0, 0, 0, 180, 180]
    assert canvas.filled_slot_indices == [2]


def test_assign_images_to_slots_updates_multiple_slots_in_one_pass() -> None:
    canvas = create_manual_timeslice(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    canvas = assign_images_to_slots(
        canvas,
        {
            0: _solid_frame(25, width=6, height=2),
            2: _solid_frame(200, width=6, height=2),
        },
    )

    assert canvas.image[0, :, 0].tolist() == [25, 25, 0, 0, 200, 200]
    assert canvas.filled_slot_indices == [0, 2]


def test_clear_slot_and_clear_slots_remove_assignments() -> None:
    canvas = render_assigned_images(
        images=[
            _solid_frame(10, width=6, height=2),
            _solid_frame(80, width=6, height=2),
            _solid_frame(160, width=6, height=2),
        ],
        spec=TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    canvas = clear_slot(canvas, 1)
    assert canvas.image[0, :, 0].tolist() == [10, 10, 0, 0, 160, 160]
    assert canvas.filled_slot_indices == [0, 2]

    canvas = clear_slots(canvas, [0, 2])
    assert canvas.image[0, :, 0].tolist() == [0, 0, 0, 0, 0, 0]
    assert canvas.filled_slot_indices == []


def test_swap_slots_swaps_existing_slot_content() -> None:
    canvas = render_assigned_images(
        images=[
            _solid_frame(10, width=6, height=2),
            _solid_frame(80, width=6, height=2),
            _solid_frame(160, width=6, height=2),
        ],
        spec=TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    canvas = swap_slots(canvas, 0, 2)

    assert canvas.image[0, :, 0].tolist() == [160, 160, 80, 80, 10, 10]
    assert canvas.filled_slot_indices == [0, 1, 2]


def test_replace_canvas_slot_map_preserves_existing_slot_assignments() -> None:
    canvas = create_manual_timeslice(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )
    canvas = assign_images_to_slots(
        canvas,
        {
            0: _solid_frame(10, width=6, height=2),
            1: _solid_frame(100, width=6, height=2),
            2: _solid_frame(200, width=6, height=2),
        },
    )

    replacement = np.array(
        [
            [0, 0, 0, 2, 2, 1],
            [0, 0, 0, 2, 2, 1],
        ],
        dtype=np.int_,
    )
    canvas = replace_canvas_slot_map(canvas, replacement)

    assert canvas.layout_description.spec.layout == "slot_map"
    assert np.array_equal(canvas.layout_description.slot_map, replacement)
    assert canvas.image[0, :, 0].tolist() == [10, 10, 10, 200, 200, 100]
    assert canvas.filled_slot_indices == [0, 1, 2]


def test_create_manual_timeslice_accepts_imported_slot_map_layout() -> None:
    layout = import_slot_map(
        np.array(
            [
                [0, 1, 1],
                [0, 2, 2],
            ],
            dtype=np.int_,
        )
    )

    canvas = create_manual_timeslice(layout.spec, width=3, height=2)

    assert canvas.slot_count == 3
    assert np.array_equal(canvas.layout_description.slot_map, layout.slot_map)

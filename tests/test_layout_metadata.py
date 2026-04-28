import numpy as np
import pytest

from pytimeslice import TimesliceSpec, create_manual_timeslice, describe_layout


def test_describe_layout_builds_band_slot_metadata() -> None:
    layout = describe_layout(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    assert layout.slot_count == 3
    assert layout.plan.layout == "bands"
    assert layout.slot_map.tolist() == [[0, 0, 1, 1, 2, 2], [0, 0, 1, 1, 2, 2]]
    assert [slot.pixel_count for slot in layout.slots] == [4, 4, 4]
    assert layout.slots[1].bounds.left == 2
    assert layout.slots[1].bounds.right == 4
    assert layout.slots[1].bounds.top == 0
    assert layout.slots[1].bounds.bottom == 2
    assert layout.slots[1].bounds.width == 2
    assert layout.slots[1].bounds.height == 2

    slot_mask = layout.mask_for_slot(1)
    assert slot_mask.tolist() == [
        [False, False, True, True, False, False],
        [False, False, True, True, False, False],
    ]

    highlighted = layout.render_slot_preview(1, inactive_opacity=0.0)
    assert np.all(highlighted[:, :2, :] == 0)
    assert np.any(highlighted[:, 2:4, :] != 0)
    assert np.all(highlighted[:, 4:, :] == 0)


def test_describe_layout_builds_mask_layout_metadata() -> None:
    layout = describe_layout(
        TimesliceSpec(layout="diagonal", num_slices=3),
        width=2,
        height=2,
    )

    assert layout.slot_count == 3
    assert layout.plan.layout == "diagonal"
    assert layout.preview_image.shape == (2, 2, 3)
    assert layout.slot_map.shape == (2, 2)
    assert set(np.unique(layout.slot_map).tolist()) == {0, 1, 2}
    assert [slot.pixel_count for slot in layout.slots] == [2, 1, 1]


def test_describe_layout_supports_random_block_metadata() -> None:
    layout = describe_layout(
        TimesliceSpec(layout="random", num_blocks=8, random_seed=7),
        width=8,
        height=4,
    )

    assert layout.slot_count == 8
    assert layout.plan.layout == "random"
    assert layout.plan.slice_frame_indices == list(range(8))
    assert set(np.unique(layout.slot_map).tolist()) == set(range(8))
    assert sum(slot.pixel_count for slot in layout.slots) == 32


def test_describe_layout_requires_explicit_num_slices_for_non_random_layouts() -> None:
    with pytest.raises(ValueError, match="spec.num_slices"):
        describe_layout(TimesliceSpec(layout="circular"), width=6, height=6)


def test_manual_canvas_exposes_shared_layout_description() -> None:
    canvas = create_manual_timeslice(
        TimesliceSpec(orientation="horizontal", num_slices=5),
        width=2,
        height=10,
    )

    assert canvas.layout_description.slot_count == canvas.slot_count
    assert canvas.layout_description.spec == canvas.spec
    assert canvas.layout_description.plan == canvas.plan
    assert canvas.layout_description.preview_image.shape == (10, 2, 3)
    assert canvas.layout_description.slot_map.shape == (10, 2)

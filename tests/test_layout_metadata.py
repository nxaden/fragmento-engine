import json

import numpy as np
import pytest

from pytimeslice import (
    TimesliceSpec,
    create_manual_timeslice,
    deserialize_layout,
    describe_layout,
    export_layout_json,
    import_layout_json,
    import_slot_map,
    replace_layout_slot_map,
    serialize_layout,
    validate_slot_map,
)


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


def test_serialize_layout_round_trips_through_json() -> None:
    layout = describe_layout(
        TimesliceSpec(layout="diagonal", num_slices=3),
        width=2,
        height=2,
    )

    payload = serialize_layout(layout)
    serialized = json.dumps(payload)
    restored = deserialize_layout(json.loads(serialized))

    assert restored.spec == layout.spec
    assert restored.plan.layout == layout.plan.layout
    assert restored.plan.orientation == layout.plan.orientation
    assert restored.plan.bands == layout.plan.bands
    assert restored.plan.slice_frame_indices == layout.plan.slice_frame_indices
    assert np.array_equal(restored.plan.slice_map, layout.plan.slice_map)
    assert restored.slot_count == layout.slot_count
    assert np.array_equal(restored.slot_map, layout.slot_map)
    assert np.array_equal(restored.preview_image, layout.preview_image)
    assert restored.slots == layout.slots


def test_serialize_layout_can_omit_preview_image() -> None:
    layout = describe_layout(
        TimesliceSpec(layout="random", num_blocks=8, random_seed=7),
        width=8,
        height=4,
    )

    payload = serialize_layout(layout, include_preview_image=False)

    assert payload["preview_image"] is None

    restored = deserialize_layout(payload)
    assert np.array_equal(restored.preview_image, layout.preview_image)


def test_export_and_import_layout_json_round_trip(tmp_path) -> None:
    layout = describe_layout(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    output_file = export_layout_json(
        layout,
        tmp_path / "saved-layout",
        include_preview_image=False,
    )
    restored = import_layout_json(output_file)

    assert output_file.suffix == ".json"
    assert np.array_equal(restored.slot_map, layout.slot_map)
    assert restored.plan == layout.plan
    assert restored.slots == layout.slots


def test_deserialize_layout_rebuilds_mask_spec_from_serialized_slot_map() -> None:
    layout = describe_layout(
        TimesliceSpec(
            layout="mask",
            num_slices=2,
            layout_mask=np.array([[0.0, 0.1], [0.9, 1.0]], dtype=np.float64),
        ),
        width=2,
        height=2,
    )

    restored = deserialize_layout(serialize_layout(layout))

    assert restored.spec.layout == "mask"
    assert restored.spec.layout_mask is not None
    replayed = describe_layout(restored.spec, width=2, height=2)
    assert np.array_equal(replayed.slot_map, layout.slot_map)


def test_validate_slot_map_normalizes_client_edited_maps() -> None:
    validated = validate_slot_map(
        np.array(
            [
                [0.0, 0.0, 2.0],
                [1.0, 1.0, 2.0],
            ],
            dtype=np.float64,
        )
    )

    assert validated.dtype == np.int_
    assert np.array_equal(
        validated,
        np.array(
            [
                [0, 0, 2],
                [1, 1, 2],
            ],
            dtype=np.int_,
        ),
    )


def test_validate_slot_map_rejects_missing_slot_indices() -> None:
    with pytest.raises(ValueError, match="contiguous range"):
        validate_slot_map(np.array([[0, 2]], dtype=np.int_))


def test_import_slot_map_creates_explicit_slot_map_layout() -> None:
    layout = import_slot_map(
        np.array(
            [
                [0, 0, 2],
                [1, 1, 2],
            ],
            dtype=np.int_,
        )
    )

    assert layout.spec.layout == "slot_map"
    assert layout.spec.layout_slot_map is not None
    assert np.array_equal(layout.slot_map, layout.spec.layout_slot_map)
    assert layout.slot_count == 3


def test_replace_layout_slot_map_uses_new_client_geometry() -> None:
    layout = describe_layout(
        TimesliceSpec(orientation="vertical", num_slices=3),
        width=6,
        height=2,
    )

    replaced = replace_layout_slot_map(
        layout,
        np.array(
            [
                [0, 0, 0, 2, 2, 1],
                [0, 0, 0, 2, 2, 1],
            ],
            dtype=np.int_,
        ),
    )

    assert replaced.spec.layout == "slot_map"
    assert np.array_equal(
        replaced.slot_map,
        np.array(
            [
                [0, 0, 0, 2, 2, 1],
                [0, 0, 0, 2, 2, 1],
            ],
            dtype=np.int_,
        ),
    )


def test_serialize_layout_round_trips_imported_slot_map_layout() -> None:
    layout = import_slot_map(
        np.array(
            [
                [0, 0, 0, 2, 2, 1],
                [0, 0, 0, 2, 2, 1],
            ],
            dtype=np.int_,
        )
    )

    restored = deserialize_layout(serialize_layout(layout))

    assert restored.spec.layout == "slot_map"
    assert restored.spec.layout_slot_map is not None
    assert np.array_equal(restored.slot_map, layout.slot_map)
    assert np.array_equal(restored.spec.layout_slot_map, layout.slot_map)

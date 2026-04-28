import numpy as np
import pytest

from pytimeslice import SliceEffects, TimesliceSpec, render_images


def _solid_frame(value: int, *, width: int, height: int) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def test_diagonal_layout_assigns_frames_along_the_image_diagonal() -> None:
    result = render_images(
        images=[
            _solid_frame(0, width=3, height=3),
            _solid_frame(100, width=3, height=3),
            _solid_frame(200, width=3, height=3),
        ],
        spec=TimesliceSpec(layout="diagonal", num_slices=3),
    )

    first_channel = result.image[:, :, 0].tolist()
    assert first_channel == [
        [0, 0, 100],
        [0, 100, 200],
        [100, 200, 200],
    ]
    assert result.plan.layout == "diagonal"
    assert result.plan.slice_map is not None
    assert result.plan.slice_frame_indices == [0, 1, 2]


def test_spiral_layout_assigns_frames_from_center_outward() -> None:
    result = render_images(
        images=[
            _solid_frame(0, width=3, height=3),
            _solid_frame(100, width=3, height=3),
            _solid_frame(200, width=3, height=3),
        ],
        spec=TimesliceSpec(layout="spiral", num_slices=3),
    )

    first_channel = result.image[:, :, 0].tolist()
    assert first_channel == [
        [200, 200, 200],
        [100, 0, 0],
        [100, 100, 0],
    ]
    assert result.plan.layout == "spiral"
    assert result.plan.slice_map is not None
    assert result.plan.slice_frame_indices == [0, 1, 2]


def test_circular_layout_assigns_frames_in_concentric_rings() -> None:
    result = render_images(
        images=[
            _solid_frame(0, width=5, height=5),
            _solid_frame(100, width=5, height=5),
            _solid_frame(200, width=5, height=5),
        ],
        spec=TimesliceSpec(layout="circular", num_slices=3),
    )

    first_channel = result.image[:, :, 0].tolist()
    assert first_channel == [
        [200, 100, 100, 100, 200],
        [100, 0, 0, 0, 100],
        [100, 0, 0, 0, 100],
        [100, 0, 0, 0, 100],
        [200, 100, 100, 100, 200],
    ]
    assert result.plan.layout == "circular"
    assert result.plan.slice_map is not None
    assert result.plan.slice_frame_indices == [0, 1, 2]


def test_random_layout_assigns_seeded_frames_to_power_of_two_block_grid() -> None:
    result = render_images(
        images=[
            _solid_frame(0, width=4, height=4),
            _solid_frame(100, width=4, height=4),
            _solid_frame(200, width=4, height=4),
        ],
        spec=TimesliceSpec(layout="random", num_blocks=4, random_seed=7),
    )

    first_channel = result.image[:, :, 0].tolist()
    assert first_channel == [
        [200, 200, 100, 100],
        [200, 200, 100, 100],
        [200, 200, 200, 200],
        [200, 200, 200, 200],
    ]
    assert result.plan.layout == "random"
    assert result.plan.slice_map is not None
    assert result.plan.slice_frame_indices == [2, 1, 2, 2]


def test_random_layout_accepts_rectangular_power_of_two_block_counts() -> None:
    result = render_images(
        images=[
            _solid_frame(0, width=16, height=16),
            _solid_frame(255, width=16, height=16),
        ],
        spec=TimesliceSpec(layout="random", num_blocks=128, random_seed=7),
    )

    assert result.plan.layout == "random"
    assert result.plan.slice_map is not None
    assert len(result.plan.slice_frame_indices or []) == 128
    assert len(np.unique(result.plan.slice_map)) == 128


def test_user_defined_layout_mask_controls_pixel_order() -> None:
    result = render_images(
        images=[
            _solid_frame(0, width=2, height=2),
            _solid_frame(200, width=2, height=2),
        ],
        spec=TimesliceSpec(
            layout="mask",
            num_slices=2,
            layout_mask=np.array([[0, 3], [2, 1]], dtype=np.float64),
        ),
    )

    first_channel = result.image[:, :, 0].tolist()
    assert first_channel == [
        [0, 200],
        [200, 0],
    ]
    assert result.plan.layout == "mask"
    assert result.plan.slice_map is not None
    assert result.plan.slice_frame_indices == [0, 1]


def test_mask_layout_requires_a_layout_mask() -> None:
    with pytest.raises(ValueError, match="layout_mask is required"):
        render_images(
            images=[
                _solid_frame(0, width=2, height=2),
                _solid_frame(255, width=2, height=2),
            ],
            spec=TimesliceSpec(layout="mask", num_slices=2),
        )


def test_slice_effects_are_rejected_for_mask_based_layouts() -> None:
    with pytest.raises(
        ValueError,
        match="Slice effects are currently supported only for layout='bands'.",
    ):
        render_images(
            images=[
                _solid_frame(0, width=3, height=3),
                _solid_frame(255, width=3, height=3),
            ],
            spec=TimesliceSpec(
                layout="diagonal",
                num_slices=2,
                effects=SliceEffects(border_width=1),
            ),
        )


def test_random_layout_rejects_invalid_block_count() -> None:
    with pytest.raises(ValueError, match="num_blocks for layout='random'"):
        render_images(
            images=[
                _solid_frame(0, width=4, height=4),
                _solid_frame(255, width=4, height=4),
            ],
            spec=TimesliceSpec(layout="random", num_blocks=12),
        )

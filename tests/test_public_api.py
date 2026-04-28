from importlib.metadata import version

import pytimeslice


def test_package_version_is_exposed() -> None:
    assert pytimeslice.__version__ == version("pytimeslice")


def test_manual_assignment_helpers_are_exposed() -> None:
    assert pytimeslice.LayoutBounds is not None
    assert pytimeslice.LayoutDescription is not None
    assert pytimeslice.LayoutSlot is not None
    assert pytimeslice.ManualTimesliceCanvas is not None
    assert pytimeslice.assign_images_to_slots is not None
    assert pytimeslice.create_manual_timeslice is not None
    assert pytimeslice.clear_slot is not None
    assert pytimeslice.clear_slots is not None
    assert pytimeslice.deserialize_layout is not None
    assert pytimeslice.describe_layout is not None
    assert pytimeslice.export_layout_json is not None
    assert pytimeslice.import_layout_json is not None
    assert pytimeslice.import_slot_map is not None
    assert pytimeslice.assign_image_to_slot is not None
    assert pytimeslice.assign_path_to_slot is not None
    assert pytimeslice.replace_canvas_slot_map is not None
    assert pytimeslice.replace_layout_slot_map is not None
    assert pytimeslice.render_animation is not None
    assert pytimeslice.render_assigned_images is not None
    assert pytimeslice.render_assigned_paths is not None
    assert pytimeslice.render_random_gif is not None
    assert pytimeslice.render_progression_video is not None
    assert pytimeslice.render_random_video is not None
    assert pytimeslice.serialize_layout is not None
    assert pytimeslice.swap_slots is not None
    assert pytimeslice.validate_slot_map is not None

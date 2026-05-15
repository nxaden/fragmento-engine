"""Public package API for pytimeslice."""

from importlib.metadata import PackageNotFoundError, version

from pytimeslice.app import (
    assign_images_to_slots,
    assign_image_to_slot,
    assign_path_to_slot,
    clear_slot,
    clear_slots,
    create_manual_timeslice,
    deserialize_layout,
    describe_layout,
    export_layout_json,
    import_layout_json,
    import_slot_map,
    replace_canvas_slot_map,
    replace_layout_slot_map,
    render_animation,
    render_folder,
    render_folder_to_file,
    render_assigned_images,
    render_assigned_paths,
    render_images,
    render_progression_gif,
    render_progression_video,
    render_random_gif,
    render_random_video,
    render_video,
    render_video_to_file,
    serialize_layout,
    swap_slots,
    validate_slot_map,
)
from pytimeslice.application.services import ManualTimesliceCanvas
from pytimeslice.domain.models import (
    LayoutBounds,
    LayoutDescription,
    LayoutSlot,
    SliceEffects,
    TimesliceSpec,
    VideoFrameSelectionSpec,
)

try:
    __version__ = version("pytimeslice")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "assign_images_to_slots",
    "assign_image_to_slot",
    "assign_path_to_slot",
    "clear_slot",
    "clear_slots",
    "create_manual_timeslice",
    "deserialize_layout",
    "describe_layout",
    "export_layout_json",
    "import_layout_json",
    "import_slot_map",
    "LayoutBounds",
    "LayoutDescription",
    "LayoutSlot",
    "ManualTimesliceCanvas",
    "replace_canvas_slot_map",
    "replace_layout_slot_map",
    "render_animation",
    "render_folder",
    "render_folder_to_file",
    "render_assigned_images",
    "render_assigned_paths",
    "render_images",
    "render_progression_gif",
    "render_progression_video",
    "render_random_gif",
    "render_random_video",
    "render_video",
    "render_video_to_file",
    "serialize_layout",
    "SliceEffects",
    "swap_slots",
    "TimesliceSpec",
    "validate_slot_map",
    "VideoFrameSelectionSpec",
]

"""Public package API for pytimeslice."""

from importlib.metadata import PackageNotFoundError, version

from pytimeslice.app import (
    assign_image_to_slot,
    assign_path_to_slot,
    create_manual_timeslice,
    deserialize_layout,
    describe_layout,
    export_layout_json,
    import_layout_json,
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
    serialize_layout,
)
from pytimeslice.application.services import ManualTimesliceCanvas
from pytimeslice.domain.models import (
    LayoutBounds,
    LayoutDescription,
    LayoutSlot,
    SliceEffects,
    TimesliceSpec,
)

try:
    __version__ = version("pytimeslice")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "assign_image_to_slot",
    "assign_path_to_slot",
    "create_manual_timeslice",
    "deserialize_layout",
    "describe_layout",
    "export_layout_json",
    "import_layout_json",
    "LayoutBounds",
    "LayoutDescription",
    "LayoutSlot",
    "ManualTimesliceCanvas",
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
    "serialize_layout",
    "SliceEffects",
    "TimesliceSpec",
]

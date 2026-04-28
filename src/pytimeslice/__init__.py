"""Public package API for pytimeslice."""

from importlib.metadata import PackageNotFoundError, version

from pytimeslice.app import (
    assign_image_to_slot,
    assign_path_to_slot,
    create_manual_timeslice,
    render_folder,
    render_folder_to_file,
    render_assigned_images,
    render_assigned_paths,
    render_images,
    render_progression_gif,
)
from pytimeslice.application.services import ManualTimesliceCanvas
from pytimeslice.domain.models import SliceEffects, TimesliceSpec

try:
    __version__ = version("pytimeslice")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "assign_image_to_slot",
    "assign_path_to_slot",
    "create_manual_timeslice",
    "ManualTimesliceCanvas",
    "render_folder",
    "render_folder_to_file",
    "render_assigned_images",
    "render_assigned_paths",
    "render_images",
    "render_progression_gif",
    "SliceEffects",
    "TimesliceSpec",
]

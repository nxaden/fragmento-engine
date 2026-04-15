"""Public package API for pytimeslice."""

from importlib.metadata import PackageNotFoundError, version

from pytimeslice.app import (
    render_folder,
    render_folder_to_file,
    render_images,
    render_progression_gif,
)
from pytimeslice.domain.models import SliceEffects, TimesliceSpec

try:
    __version__ = version("pytimeslice")
except PackageNotFoundError:
    __version__ = "0+unknown"

__all__ = [
    "__version__",
    "render_folder",
    "render_folder_to_file",
    "render_images",
    "render_progression_gif",
    "SliceEffects",
    "TimesliceSpec",
]

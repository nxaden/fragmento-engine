# Changelog

All notable changes to this project will be documented in this file.

The format is based on Keep a Changelog. The repository does not have release
tags yet, so historical entries are grouped by commit date until versioned
releases begin.

## [Unreleased]

### Added

- Mask-based layout planning in the domain layer with built-in `diagonal`,
  `spiral`, `circular`, and `random` layouts plus user-defined `layout_mask`
  support through `TimesliceSpec`.
- Progression GIF support for mask-based layouts through the existing
  application workflow.
- CLI support for `--layout`, file-backed `--layout-mask` inputs, and seeded
  random block layouts.
- Random block layouts now accept rectangular power-of-two totals such as
  `128`, not just square totals such as `64` or `256`.
- Manual slot-assignment helpers for future client flows, including explicit
  per-slice path/image rendering and an incremental empty-canvas builder that
  defaults to 4K previews.
- Client-facing layout metadata through `describe_layout(...)`, including
  slot maps, per-slot bounds, color-coded preview images, and shared metadata
  on manual canvases.
- CLI support for manual assignment with `--assigned-path`, `--slot-path`, and
  `--manual-empty`, including partial black-slot previews and configurable
  manual canvas dimensions.
- Random-layout animated GIF support in both the Python API and CLI through a
  dedicated seed-shuffle workflow, including configurable frame counts and
  smooth-loop emission.
- `.mp4` and `.mov` animation export support for progression and random-shuffle
  workflows, including configurable video frame rates and repeat counts.
- A unified `render_animation(...)` API plus `--animate` CLI workflow for GIF,
  `.mp4`, and `.mov` exports across both progression and random animation
  modes.

### Changed

- Archived low-value legacy docs and retired standalone requirements into the
  local `.archive/` folder, and simplified the active MkDocs navigation to the
  generated `docs/api/` pages.
- Refactored the separate GIF and video export paths onto one shared animation
  service while keeping the older helper functions and CLI flags as
  compatibility wrappers.

## [2026-04-27]

### Changed

- Refreshed the README copy and external links.
- Added the `assets/timeslice.gif` demo animation to the project landing page.

## [2026-04-15]

### Added

- Slice-boundary effects including borders, feathering, shadows, highlight
  controls, and selectable boundary curves.
- Explicit output workflows including default `out/` directory handling,
  still-image export, progression GIF export, smooth-loop GIF sequencing, and
  writer-backed integration tests.
- A split public API that keeps pure rendering separate from explicit file
  export helpers.
- Placeholder example and test fixture image sequences committed into the
  repository.
- Packaging and release support including `MANIFEST.in`, `py.typed`,
  `RELEASING.md`, runtime `__version__`, and public API tests.
- GitHub Actions workflows for linting, type checking, tests, builds,
  `twine check`, and docs deployment.
- A MkDocs site, generated API reference pages, installation and quickstart
  docs, and hosted documentation wiring.
- Repository agent guidance and a canonical `make check` target.

### Changed

- Renamed the project, distribution, package, and CLI from
  `fragmento_engine` to `pytimeslice`.
- Clarified progression GIF response semantics in the application service and
  CLI.

### Fixed

- Made CI and Makefile shell usage compatible across environments.

## [2026-04-11]

### Added

- A hand-written API reference covering the package-root and layered modules.
- Detailed architecture documentation for the domain, infrastructure,
  application, and interface layers.
- Project license and expanded package metadata in `pyproject.toml`.

## [2026-04-10]

### Added

- A clearer domain split between models, planning, and compositing.
- Application services, infrastructure adapters for image loading and writing,
  and a CLI interface layer.
- A package-root public API for library consumers.

### Changed

- Refactored the project into the current layered architecture and retired the
  original basic demo in favor of reusable library and service entry points.
- Updated the README to reflect the project's library-first direction.

## [2026-04-09]

### Added

- Initial project scaffold with `pyproject.toml`, `Makefile`, dependencies,
  pre-commit config, and starter package layout.
- Early domain compositor wiring and a basic demo.

### Changed

- Renamed the package from `fragmento_core` to `fragmento_engine` during the
  first round of restructuring.

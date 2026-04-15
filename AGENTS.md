# AGENTS

This file is the fast-path guide for future coding agents working in this
repository.

## Canonical Commands

Assume the local virtual environment created by `make setup`.

- `make test`: run the full test suite
- `make lint`: run Ruff checks
- `make typecheck`: run `mypy src`
- `make check`: run the canonical verification stack in this order:
  `ruff check .`, `mypy src`, `pytest`

Prefer `make check` before finishing a feature unless the change is docs-only.

## Architecture Rules

Use the existing layer split consistently:

- `src/fragmento_engine/domain/`: slice math, planning, compositing, render
  validation that changes what the engine means
- `src/fragmento_engine/application/`: workflows and orchestration
- `src/fragmento_engine/infrastructure/`: Pillow, filesystem, loading, writing
- `src/fragmento_engine/interface/`: CLI and user-facing invocation

If a change crosses layers, keep the business rule in the lower layer and keep
the upper layer thin.

## Public API Rules

Package-root imports live in `src/fragmento_engine/__init__.py`.

Current public workflow split:

- `render_images(...)`: pure in-memory render
- `render_folder(...)`: pure folder render, no file write
- `render_folder_to_file(...)`: explicit still-image export
- `render_progression_gif(...)`: explicit GIF export

Do not reintroduce hidden file writes into pure render functions.

If you change a public return type or add a public helper:

- update `__init__.py`
- update `README.md`
- update `docs/API_REFERENCE.md`

## Testing Rules

Match test scope to change scope:

- domain changes: add or update domain tests
- workflow changes: add or update application/service tests
- writer or export changes: add real file-output tests that reopen files from
  disk with Pillow
- CLI flag changes: add parser tests and validation tests

The repo already uses both fast double-based workflow tests and real
writer-backed integration tests. Keep both styles where appropriate.

## Validation Rules

Fail as early as practical:

- CLI should reject invalid numeric inputs before execution
- application services should reject invalid workflow parameters before loading
  files
- domain validation should remain reusable from multiple entrypoints

Avoid duplicating validation logic across modules when one shared helper will do.

## Repo Hygiene

- Do not commit generated outputs, caches, or local experiment files
- Keep sample assets in `examples/` or `tests/fixtures/` rather than the repo
  root
- Keep output paths under an `out/` directory when a workflow writes files by
  default
- Prefer small, focused commits with conventional prefixes such as `feat:`,
  `fix:`, and `chore:`

## Practical Guidance

Before adding a new feature, ask:

1. Is this a domain rule, a workflow, an infrastructure concern, or an
   interface concern?
2. Does it need a pure API, an explicit export API, or both?
3. What is the narrowest test that proves the change?

When in doubt, keep rendering pure and make exports explicit.

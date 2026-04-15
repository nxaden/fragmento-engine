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
- `make build`: create wheel and sdist artifacts under `dist/`
- `make check-dist`: validate built package metadata and README rendering with
  Twine
- `make docs-build`: build the external docs site with MkDocs

Prefer `make check` before finishing a feature unless the change is docs-only.
Prefer `make build` and `make check-dist` before finishing packaging or release
work.
GitHub Actions mirrors `make check` and `make build` plus `make check-dist`;
keep the workflow and Make targets aligned.
For docs changes, prefer `make docs-build` before finishing.

## Architecture Rules

Use the existing layer split consistently:

- `src/pytimeslice/domain/`: slice math, planning, compositing, render
  validation that changes what the engine means
- `src/pytimeslice/application/`: workflows and orchestration
- `src/pytimeslice/infrastructure/`: Pillow, filesystem, loading, writing
- `src/pytimeslice/interface/`: CLI and user-facing invocation

If a change crosses layers, keep the business rule in the lower layer and keep
the upper layer thin.

## Public API Rules

Package-root imports live in `src/pytimeslice/__init__.py`.

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
- Canonical committed sample input locations:
  `examples/media/placeholder-sequence/` and `tests/fixtures/placeholder-sequence/`
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

PYTHON := python3
VENV := .venv
VENV_BIN := $(VENV)/bin
VENV_PYTHON := $(VENV_BIN)/python
VENV_PIP := $(VENV_BIN)/pip
PRE_COMMIT := $(VENV_BIN)/pre-commit
PYTEST := $(VENV_BIN)/pytest
RUFF := $(VENV_BIN)/ruff
BLACK := $(VENV_BIN)/black
MYPY := $(VENV_BIN)/mypy
TWINE := $(VENV_BIN)/python -m twine
BUILD := $(VENV_BIN)/python -m build
MKDOCS := $(VENV_BIN)/mkdocs

bootstrap:
	$(PYTHON) -m venv $(VENV)
	$(VENV_PIP) install --upgrade pip
	$(VENV_PIP) install -e ".[dev]"

setup: bootstrap
	$(PRE_COMMIT) install

run:
	$(VENV_PYTHON) -m pytimeslice.interface.cli --help

test:
	$(PYTEST)

lint:
	$(RUFF) check .

format:
	$(BLACK) .

typecheck:
	$(MYPY) src

check:
	$(RUFF) check .
	$(MYPY) src
	$(PYTEST)

clean:
	rm -rf build dist src/*.egg-info

build:
	$(BUILD)

check-dist:
	$(TWINE) check dist/*

publish-testpypi:
	$(TWINE) upload --repository testpypi dist/*

docs-build:
	$(MKDOCS) build --strict

docs-serve:
	$(MKDOCS) serve

release-check: check build check-dist

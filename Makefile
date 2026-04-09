PYTHON := python3
VENV := .venv
ACTIVATE := source $(VENV)/bin/activate

setup:
	$(PYTHON) -m venv $(VENV)
	$(ACTIVATE) && pip install --upgrade pip
	$(ACTIVATE) && pip install -r requirements.txt -r requirements-dev.txt
	$(ACTIVATE) && pre-commit install

run:
	$(ACTIVATE) && python app.py

test:
	$(ACTIVATE) && pytest

lint:
	$(ACTIVATE) && ruff check .

format:
	$(ACTIVATE) && black .

typecheck:
	$(ACTIVATE) && mypy .
.PHONY: setup test lint format check clean

setup:
	pip install -e ".[dev]"

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .

check: lint test

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache build dist *.egg-info src/*.egg-info

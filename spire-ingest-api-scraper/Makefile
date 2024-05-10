# -------
# Develop
# -------

dev-install:  ## Install development and production dependencies in .venv
	pip install -U pip
	pipenv sync --dev

clean-all:  # restore working environment to time-zero state
	deactivate >/dev/null 2>&1 || true && pipenv --rm >/dev/null 2>&1 || true \
	pipenv -- clear \
	&& rm -rf .mypy_cache && rm -rf .pytest_cache && rm -f .coverage

# -----
# Hygiene & Testing
# -----

format:
	pipenv run black .

dependency-check:
	pipenv check
	pipenv verify

lint:
	pipenv run ruff format --check .
	pipenv run ruff check .

type-check:
	pipenv run mypy .

pytest:
	pipenv run pytest --cov . --cov-report term-missing

test: dependency-check lint type-check pytest

# Don't capture stdout: pytest will capture logs
test-with-logs:
	pipenv run pytest --log-cli-level=DEBUG --show-capture=no

.PHONY: install
install:  ## Install development and production dependencies in .venv
	PIPENV_VENV_IN_PROJECT=1 pipenv install --dev

.PHONY: check
check:  ## Run static analysis tools
	pipenv run ruff format --check src tests
	pipenv run ruff check src tests
	pipenv run mypy src tests

.PHONY: test
test:  ## Run local tests.
	pipenv run pytest

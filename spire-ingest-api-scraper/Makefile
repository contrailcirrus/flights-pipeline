DOCKER_COMMAND = docker
IMAGE_NAME = spire-ingest-api-scraper
TAG ?= $(shell git describe --tags)


.PHONY: help
help:
	echo "See Makefile for recipe list"

.PHONY: install
install:  ## Install development and production dependencies in .venv
	PIPENV_VENV_IN_PROJECT=1 pipenv install --dev

# -----
# Hygiene & Testing
# -----

format:
	pipenv run black .

dependency-check:
	pipenv check
	pipenv verify

lint:
	pipenv run ruff format --check src tests
	pipenv run ruff check src tests

type-check:
	pipenv run mypy --install-types --non-interactive src tests

pytest:
	pipenv run pytest --cov app --cov-report term-missing

test: dependency-check lint type-check pytest

# Don't capture stdout: pytest will capture logs
test-with-logs:
	pipenv run pytest --log-cli-level=DEBUG --show-capture=no

# ---------------
# Docker / podman
# ---------------

docker-build:
	-$(DOCKER_COMMAND) build --tag $(IMAGE_NAME) .
	$(DOCKER_COMMAND) image prune -f

docker-test:
	$(DOCKER_COMMAND) build --tag $(IMAGE_NAME) --target test .
	$(DOCKER_COMMAND) image prune -f

docker-build-fresh:
	$(DOCKER_COMMAND) build --no-cache --tag $(IMAGE_NAME) .
	$(DOCKER_COMMAND) image prune -f

docker-bash:
	$(DOCKER_COMMAND) run --rm -e CONTRAILS_API_DEBUG=1 -it --entrypoint bash $(IMAGE_NAME)

docker-run:
	$(DOCKER_COMMAND) run --rm -e CONTRAILS_API_DEBUG=1 -p 8000:8000 -it $(IMAGE_NAME)

# reclaim disk space eaten up by docker
# https://docs.docker.com/docker-for-mac/space/
docker-clean:
	-buildah rm --all
	$(DOCKER_COMMAND) system prune

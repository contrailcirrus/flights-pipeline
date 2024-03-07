
IMAGE_NAME = contrails-api


# -------
# Develop
# -------

prod-install:  # install pinned prod packages in lockfile
	pip install -U pip
	pipenv sync

dev-install: # install pinned dev+prod packages in lockfile
	pip install -U pip
	pipenv sync --dev

activate:  # active virtenv associated with Pipfile in the project dir for the current shell
	@pipenv shell

clean-all:  # restore working environment to time-zero state
	deactivate >/dev/null 2>&1 || true && pipenv --rm >/dev/null 2>&1 || true \
	pipenv -- clear \
	&& rm -rf .mypy_cache && rm -rf .pytest_cache && rm -f .coverage


# -----
# Hygiene & Testing
# -----

format:
	black .

dependency-check:
	pipenv check
	pipenv verify

lint:
	ruff app tests

type-check:
	mypy --install-types --non-interactive app tests

pytest:
	python -m pytest --cov app --cov-report term-missing

# There are often issues with workers crashing, hence reruns on failures
pytest-parallel:
	USE_MULTIPROCESS_LRU_STORE=1 python -m pytest --durations 10 -n auto --reruns 10
	--reruns-delay 1

test: dependency-check lint type-check pytest

# Don't capture stdout: pytest will capture logs
test-with-logs:
	python -m pytest --log-cli-level=DEBUG --show-capture=no

test-integration:
	python -m pytest -vv tests/integration --durations=0


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


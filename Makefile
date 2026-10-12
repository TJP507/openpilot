SHELL := /bin/bash

# TylerPilot fork CI helpers (STANDARD §5).
#
# The build system (scons) is not yet restored in this fork — the root
# `SConstruct`/`SConscript` are missing — so there is deliberately no `build`
# target. See `.github/workflows/ci.yml`.

.PHONY: help act act-clean lint unit tylerpilot

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN{FS=":.*?## "};{printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

act-clean: ## Reap orphaned act containers from previous runs
	@ids=$$(docker ps -aq --filter "name=act-" || true); \
	if [ -n "$$ids" ]; then docker rm -f $$ids >/dev/null; fi

act: act-clean ## Run the CI workflow locally with act
	act pull_request -W .github/workflows/ci.yml

lint: ## ruff + codespell over the repo
	ruff check .
	codespell

unit: ## Build-free pure-Python unit subset
	pytest -o addopts="" --confcutdir=sunnypilot -m "not slow and not tici" \
	  sunnypilot/mapd/tests/test_mapd_version.py \
	  sunnypilot/selfdrive/selfdrived/tests/test_button_state_tracker.py

tylerpilot: ## Run the TylerPilot unit tests
	pytest -o addopts="" --confcutdir=sunnypilot sunnypilot/tylerpilot/tests

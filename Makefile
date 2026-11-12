setup: requirements.txt
	pip install -r requirements.txt
clean:
	rm -rf __pycache__
	rm -rf src/aiocasambi.egg-info
	rm -rf dist/*
	rm -rf src/aiocasambi/__pycache__
build:
	python3 setup.py sdist bdist_wheel
upload: clean build
	python3 setup.py sdist bdist_wheel; twine upload dist/*
.PHONY: build clean upload test coverage-badge renovate renovate-summary hooks secrets trivy

test: ## Run unit tests with coverage
	PYTHONPATH=src uv run --with pytest --with pytest-asyncio --with pytest-cov --with aiohttp --with pyyaml pytest --cov=aiocasambi --cov-fail-under=80 --cov-report=term-missing --cov-report=json tests/

coverage-badge: test ## Generate coverage.svg badge from coverage report
	uv run python3 .github/scripts/generate_coverage_badge.py

renovate:
	@./bin/renovate/run.sh

renovate-summary:
	@./bin/renovate/run.sh --summary
hooks: ## Install git pre-commit hook
	@chmod +x .githooks/pre-commit 2>/dev/null || true
	@git config core.hooksPath .githooks
	@echo "Git pre-commit hook installed and core.hooksPath set to .githooks."

secrets: ## Run TruffleHog secret scanning
	@echo "Running TruffleHog secret scan..."
	@if command -v trufflehog >/dev/null 2>&1; then \
		trufflehog --no-update git file://$$(pwd) --only-verified --fail; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm -v $$(pwd):/src -w /src trufflesecurity/trufflehog:latest git file:///src --only-verified --fail; \
	else \
		echo "ERROR: trufflehog or docker is required!" >&2 && exit 1; \
	fi

trivy: ## Run Trivy vulnerability scanning
	@echo "Running Trivy vulnerability scan..."
	@if command -v trivy >/dev/null 2>&1; then \
		trivy fs --severity HIGH,CRITICAL --exit-code 1 .; \
	elif command -v docker >/dev/null 2>&1; then \
		docker run --rm -v $$(pwd):/src -v trivy-cache:/root/.cache -w /src aquasec/trivy:latest fs --severity HIGH,CRITICAL --exit-code 1 .; \
	else \
		echo "ERROR: trivy or docker is required!" >&2 && exit 1; \
	fi


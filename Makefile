.PHONY: dev test lint check run status

PYTHON := venv/bin/python3
PYTEST := venv/bin/pytest
RUFF   := venv/bin/ruff

# Start the Flask WebUI (port 5050)
dev:
	$(PYTHON) webui/app.py

# Run tests, skipping GPU-dependent tests
test:
	$(PYTEST) -m "not gpu" -v

# Lint with ruff
lint:
	$(RUFF) check .

# Lint + test
check: lint test

# Start the APScheduler (production mode)
run:
	./run.sh

# Show running jobs and their status
status:
	$(PYTHON) main.py status

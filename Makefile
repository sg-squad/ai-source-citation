.PHONY: help install install-browsers lint typecheck test check-pass check-fail fmt

help:
	@echo "Available targets:"
	@echo "  make install           - Install project dependencies via Poetry"
	@echo "  make install-browsers  - Install Playwright browsers"
	@echo "  make lint              - Run ruff lint checks"
	@echo "  make typecheck         - Run mypy"
	@echo "  make test              - Run pytest"
	@echo "  make check-pass        - Run pass batch config"
	@echo "  make check-fail        - Run fail batch config"
	@echo "  make fmt               - Format code with ruff"

install:
	poetry install

install-browsers:
	poetry run playwright install

lint:
	poetry run ruff check .

typecheck:
	poetry run mypy src

test:
	poetry run pytest || ([ $$? -eq 5 ] && echo "No tests collected; treating as pass")

check-pass:
	poetry run ai-source-citation check-config input/single_search_pass.json \
	  --csv output/results_pass.csv \
	  --json output/results_pass.json \
	  --html output/results_pass.html \
	  --interactive \
	  --expand-answer \
	  --no-headless

check-fail:
	poetry run ai-source-citation check-config input/single_search_fail.json \
	  --csv output/results_fail.csv \
	  --json output/results_fail.json \
	  --html output/results_fail.html \
	  --interactive \
	  --expand-answer \
	  --no-headless

fmt:
	poetry run ruff format .

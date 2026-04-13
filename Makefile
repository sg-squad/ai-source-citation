.PHONY: help install playwright-install lint format typecheck test run-pass run-fail

help:
	@echo "Available targets:"
	@echo "  make install             - Install project dependencies via Poetry"
	@echo "  make playwright-install  - Install Playwright browsers"
	@echo "  make lint                - Run Ruff lint checks"
	@echo "  make format              - Run Ruff formatter"
	@echo "  make typecheck           - Run mypy"
	@echo "  make test                - Run pytest"
	@echo "  make run-pass            - Run the known-pass batch config"
	@echo "  make run-fail            - Run the known-fail batch config"

install:
	poetry install

playwright-install:
	poetry run playwright install

lint:
	poetry run ruff check .

format:
	poetry run ruff format .

typecheck:
	poetry run mypy src/ai_source_citation

test:
	poetry run pytest || ([ $$? -eq 5 ] && echo "No tests collected; treating as pass")

run-pass:
	poetry run ai-source-citation check-config input/single_search_pass.json \
	  --csv output/results_pass.csv \
	  --json output/results_pass.json \
	  --html output/results_pass.html \
	  --interactive \
	  --expand-answer \
	  --no-headless

run-fail:
	poetry run ai-source-citation check-config input/single_search_fail.json \
	  --csv output/results_fail.csv \
	  --json output/results_fail.json \
	  --html output/results_fail.html \
	  --interactive \
	  --expand-answer \
	  --no-headless

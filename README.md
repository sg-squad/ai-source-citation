# AI Source Citation

A Python CLI for validating Google AI Overview responses against expected citation domains and (optionally) expected answer text.

## Workflow: batch first, single-shot second

Use **batch mode** (`check-config`) for normal work and repeatable runs. Use **single-shot** (`check`) only for quick ad-hoc checks.

## Requirements

- Python 3.12+ (repo pin: `3.12.12`)
- Poetry 2.3.2
- Playwright browsers
- Google account (recommended for reliable AI Overview visibility)

## Setup

```bash
pyenv install 3.12.12
pyenv local 3.12.12
poetry env use "$(pyenv which python)"
poetry install
poetry run playwright install
poetry run ai-source-citation --help
```

## Key CLI flags (current)

Supported across `check` and `check-config`:

- `--csv <path>`
- `--json <path>`
- `--html <path>`
- `--profile <path>`
- `--interactive`
- `--headless` / `--no-headless`
- `--expand-answer`

Single-shot (`check`) also supports:

- `--expected <domain>` (required for `check`)
- `--expected-answer <text>`

## Batch mode (recommended)

### Pass example

```bash
poetry run ai-source-citation check-config input/single_search_pass.json \
  --csv output/results_pass.csv \
  --json output/results_pass.json \
  --html output/results_pass.html \
  --interactive \
  --expand-answer \
  --no-headless
```

Expected outcome: run exits success with passed checks.

### Fail example

```bash
poetry run ai-source-citation check-config input/single_search_fail.json \
  --csv output/results_fail.csv \
  --json output/results_fail.json \
  --html output/results_fail.html \
  --interactive \
  --expand-answer \
  --no-headless
```

Expected outcome: run exits non-zero with a failed check (for expected-answer mismatch).

### Interactive/login guidance

With `--interactive --no-headless`, the CLI pauses so you can sign into Google and accept prompts in the browser. After login, return to terminal and press Enter to continue.

## Single-shot mode (quick ad-hoc only)

```bash
poetry run ai-source-citation check \
  "what is the population in the uk in 2025?" \
  --expected ons.gov.uk \
  --expected-answer "69,487,000" \
  --csv output/single.csv \
  --json output/single.json \
  --html output/single.html \
  --profile .pw-profile \
  --interactive \
  --expand-answer \
  --no-headless
```

Use this when you want a one-off check; use batch for repeatable test packs.

## Output artifacts

- `output/*.csv`: tabular export for spreadsheets
- `output/*.json`: structured report (`summary`, `failures`, `results`)
- `output/*.html`: human-readable report

Important fields:

- `matched`: expected citation source(s) were found
- `answer_matched`: expected answer snippet matched
- `status`: `passed` or `failed`

## Makefile targets

- `make install` – install dependencies
- `make playwright-install` – install Playwright browsers
- `make lint` – run Ruff checks
- `make format` – run Ruff formatter
- `make typecheck` – run mypy
- `make test` – run pytest
- `make run-pass` – execute batch pass config with CSV/JSON/HTML outputs
- `make run-fail` – execute batch fail config with CSV/JSON/HTML outputs

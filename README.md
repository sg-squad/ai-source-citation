# AI Source Citation

A Python toolkit for extracting, analysing, and validating sources referenced in AI-generated responses.
While the current CLI focuses on checking Google AI Overview answers, the longer-term goal is to run the same validation pipeline across other AI surfaces.

1. cite the expected source domain(s), and
2. contain an expected answer snippet (optional).

## Batch-first workflow (recommended)

The primary workflow is running `check-config` against JSON files in `input/` and writing machine-readable artifacts to `output/`.

- Use `input/single_search_pass.json` for a known-pass check.
- Use `input/single_search_fail.json` for a known-fail check.
- Use `input/example_batch_search.json` (or your own config) for larger batches.

## Requirements

- Python **3.12+** (repo pins `3.12.12` via `.python-version`)
- Poetry **2.3.2**
- Playwright browsers
- Google account (recommended for stable AI Overview visibility)

## Setup

### 1) Python via pyenv

```bash
pyenv install 3.12.12
pyenv local 3.12.12
```

Verify:

```bash
pyenv version
python --version
```

### 2) Install dependencies (Poetry 2.3.2)

```bash
poetry env use "$(pyenv which python)"
poetry install
```

### 3) Install Playwright browsers

```bash
poetry run playwright install
```

### 4) Confirm CLI

```bash
poetry run ai-source-citation --help
```

## Login guidance (interactive mode)

For reliable AI Overview extraction, run with `--interactive --no-headless` and sign in to Google when prompted.

Interactive mode pauses with:

> Press ENTER in the terminal when ready to continue...

After sign-in/consent in the opened browser, return to terminal and press Enter.

## CLI flags (currently supported)

### Shared output/browser flags (`check` and `check-config`)

- `--csv <path>`: write CSV report
- `--json <path>`: write JSON report
- `--html <path>`: write HTML report
- `--profile <path>`: Playwright user-data directory
- `--interactive`: pause to manually log in / consent
- `--headless` / `--no-headless`: toggle visible browser
- `--expand-answer`: click "Show more" before scraping answer text

### Single-shot extras (`check`)

- `--expected <domain>` (repeatable or comma-separated) — required
- `--expected-answer <text>` (optional snippet match)

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

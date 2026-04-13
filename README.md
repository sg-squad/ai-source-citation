# AI Source Citation

A Python CLI for checking whether Google AI Overview responses:

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
- `--interactive`: pause for manual login
- `--headless` / `--no-headless`: browser visibility mode
- `--expand-answer`: click “Show more” before capture

### Single-shot-only validation flags (`check`)

- `--expected <domain>`: expected citation domain(s); repeatable/comma-separated
- `--expected-answer <text>`: expected answer text snippet

## Input config format (`check-config`)

`check-config` expects a JSON object with a `search` array:

```json
{
  "search": [
    {
      "question": "What is the latest UK unemployment rate percentage?",
      "expected_citation": "ons.gov.uk",
      "expected_answer": "5.2%"
    }
  ]
}
```

`expected_answer` is optional.

## Usage

### Batch pass/fail examples (recommended)

Pass scenario:

```bash
poetry run ai-source-citation check-config input/single_search_pass.json \
  --csv output/results_pass.csv \
  --json output/results_pass.json \
  --html output/results_pass.html \
  --interactive \
  --expand-answer \
  --no-headless
```

Fail scenario (expected to fail answer match):

```bash
poetry run ai-source-citation check-config input/single_search_fail.json \
  --csv output/results_fail.csv \
  --json output/results_fail.json \
  --html output/results_fail.html \
  --interactive \
  --expand-answer \
  --no-headless
```

### Single-shot example (modern CLI)

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

## Artifacts and result interpretation

Typical outputs:

- `output/*.csv`: flat table for spreadsheet use
- `output/*.json`: structured run summary + per-check details
- `output/*.html`: human-readable report

Key result fields:

- `matched`: expected citation domain found in extracted citation domains
- `answer_matched`: expected answer snippet found in `answer_text` (`true` / `false` / `null`)
- `status`: `passed` or `failed`

In JSON batch output:

- `summary.checks_passed` and `summary.checks_failed` provide run-level totals.
- `failures[]` explains why checks failed (for example, `answer did not match expected`).

## Makefile shortcuts

Common tasks are wrapped in `Makefile`:

- `make install` – install Python dependencies
- `make install-browsers` – install Playwright browsers
- `make lint` – run Ruff lint checks
- `make typecheck` – run mypy strict checks
- `make test` – run pytest
- `make check-pass` – run `input/single_search_pass.json` batch to `output/results_pass.*`
- `make check-fail` – run `input/single_search_fail.json` batch to `output/results_fail.*`
- `make fmt` – run Ruff formatter

Use `make help` to list targets.

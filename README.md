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
- `--llm-judge <path>`: optional LLM-as-judge config file for answer mismatches

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

Each row in the CLI/CSV/JSON/HTML output captures:

* **provider / question** – metadata about the search that ran.
* **expected citations** – the list of `{domain, url?}` pairs plus whether each domain/url matched.
* **answer fields** – the returned `answer_text`, optional `expected_answer`, and whether the match succeeded.
* **citations / citation_domains / citation_labels** – raw data pulled from Google AI Overview.
* **status** – `passed` only when every required domain (and URL, if supplied) was observed.

CSV exports also include helper columns such as `expected_domains`, `expected_urls`, `matched_domains`, `matched_urls`, and `missing_urls` to make triage easier.

An abbreviated JSON example looks like this:

```json
{
  "provider": "google",
  "question": "what is the population in the uk in 2025?",
  "expected_citations": [
    {
      "domain": "ons.gov.uk",
      "url": "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/bulletins/provisionalpopulationestimatefortheuk/mid2025",
      "domain_matched": true,
      "url_matched": true
    }
  ],
  "expected_answer": "69,487,000",
  "answer_text": "The provisional UK population for mid-2025 ...",
  "answer_matched": true,
  "citations": [
    "https://www.ons.gov.uk/.../mid2025",
    "https://cy.ons.gov.uk/.../mid2025"
  ],
  "citation_domains": ["ons.gov.uk", "cy.ons.gov.uk"],
  "matched": true
}
```

In addition to the structured JSON/HTML reports:

- `output/*.csv`: tabular export for spreadsheets.
- `output/*.json`: summarized run report (`summary`, `failures`, `results`).
- `output/*.html`: human-readable dashboard for browsing results.

## Makefile targets

- `make install` – install dependencies
- `make playwright-install` – install Playwright browsers
- `make lint` – run Ruff checks
- `make format` – run Ruff formatter
- `make typecheck` – run mypy
- `make test` – run pytest
- `make run-pass` – execute batch pass config with CSV/JSON/HTML outputs
- `make run-fail` – execute batch fail config with CSV/JSON/HTML outputs

## Added Features

- `--expand-answer` clicks "Show more" under the AI Overview before scraping answer text.
- `--html output/filename.html` generates a shareable HTML report that mirrors the CLI/CSV output.



## Development workflow

Before starting a new change, always ensure you are up to date with `main` to avoid conflicts:

```bash
git checkout main
git pull origin main --ff-only
git checkout -b <feature-branch>
```

After implementing changes, run `make lint`, `make typecheck`, and `make test` before opening a PR.


## LLM as a judge (optional)

You can optionally run an LLM judge for rows where `expected_answer` does **not** match `answer_text`.

```bash
poetry run ai-source-citation check-config input/single_search_fail.json \
  --csv output/results_fail.csv \
  --json output/results_fail.json \
  --html output/results_fail.html \
  --expand-answer \
  --no-headless \
  --profile .pw-profile \
  --llm-judge config/llm_judge.example.json
```

### LLM judge config file

Create a JSON file containing:

```json
{
  "provider": "openai",
  "model": "gpt-5.4-2026-03-05",
  "prompt_path": "llm_judge.prompt.txt",
  "response_schema_path": "llm_judge.response.schema.json",
  "project": "optional-gcp-project-id",
  "location": "optional-vertex-location"
}
```

- `provider`: `openai` or `gemini`
- `model`: model id for the selected provider
- `prompt_path`: prompt template file
- `response_schema_path`: schema/shape the judge must return
- `project` (optional): GCP project for Gemini Vertex ADC mode
- `location` (optional): Vertex region for Gemini ADC mode (defaults to `us-central1`)

Relative paths are resolved relative to the config file location.

### Prompt placeholders

The prompt file can include:

- `{{expected_answer}}`
- `{{actual_answer}}`
- `{{response_schema}}`

### Judge output fields

When judge runs, JSON/CSV/HTML include:

- `llm_judge.matched`
- `llm_judge.confidence` (0..1)
- `llm_judge.reasoning`
- `llm_judge.provider` and `llm_judge.model`

### Credentials / ADC behavior

- If Gemini/OpenAI API key env vars are present (`GEMINI_API_KEY`, `GOOGLE_API_KEY`, or `OPENAI_API_KEY`), the judge keeps API-key behavior.
- If no API key env vars are present and provider is `gemini`, the judge uses **Application Default Credentials** via `google.auth.default()`.
- Gemini ADC project resolution order:
  1. `project` in LLM judge config
  2. `GOOGLE_CLOUD_PROJECT`
  3. `GCP_PROJECT`
  4. inferred project from ADC
- Gemini ADC location resolution order:
  1. `location` in LLM judge config
  2. `GOOGLE_CLOUD_LOCATION`
  3. `GOOGLE_CLOUD_REGION`
  4. `VERTEX_AI_LOCATION`
  5. fallback `us-central1`
- Never commit secrets to GitHub.

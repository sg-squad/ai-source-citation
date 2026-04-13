# AI Source Citation

A Python toolkit for extracting, analysing, and validating sources referenced in AI-generated responses.

The project is designed to support AI transparency and citation validation by identifying referenced sources, retrieving their content, and checking whether claims made by AI models are supported by those sources.

This repository provides reusable utilities for:

- Extracting citations and references from AI outputs

- Retrieving referenced web pages

- Analysing source credibility

- Validating whether claims are supported by the cited material

The library is designed to integrate into AI evaluation pipelines, research workflows, and automated fact-checking systems.

## Requirements

- Python 3.12
- Poetry 2.x
- Playwright
- Google account (required to reliably obtain AI Overviews in search)

## Initialisation

This project uses **Python 3.12**, **pyenv** for Python version management, and **Poetry 2.x** for dependency management.

### Install Python using pyenv

If Python 3.12 is not installed:

```bash
pyenv install 3.12
```

Set the local Python version for the project:

```bash
pyenv local 3.12
```

Verify:

```bash
python --version
```

Expected output:

```
Python 3.12.x
```

### Install Dependencies with Poetry

Install project dependencies:

```bash
poetry install
```

Poetry will:

* create a virtual environment
* install all dependencies defined in `pyproject.toml`

Find the environment to activate:

```bash
poetry env activate
```

Source in the returned script.

### Verify the CLI Commands

This project exposes a CLI tool via Poetry.

Check the CLI is available:

```bash
poetry run ai-source-citation --help
```

You should see the CLI usage instructions.

## Usage Instructions - Single Shot

### Run the Tool (Interactive)

Interactive mode runs the tool, opening a browser window and pausing to allow you to **login to your google account** (this is recommended as AI Overiew is more reliably shown when logged in to an account).

Example:

```bash
poetry run ai-source-citation check \
  "what is the population in the uk in 2026?" \
  --expected ons.org.uk \ 
  --no-headless \
  --profile .pw-profile \
  --interactive
```


This will:

* Load a browser
* Pause to allow login to Google
* Run a search
* Extract sources
* Analyse citations
* Output results to the cli

### Run the Tool (Non-Headless Mode)

Non-headless mode launches a visible browser so you can observe the automation.  It is better if you have logged into Google using the interactive instructions above first.

Example:

```bash
poetry run ai-source-citation check \
  "what is the population in the uk in 2026?" \      
  --expected ons.org.uk \
  --no-headless \
  --profile .pw-profile
```

This is useful for:

* Debugging
* Inspecting page behaviour
* Development work.

### Run the Tool (Headless Mode)

Headless mode runs the full analysis without opening a browser window.

Example:

```bash
poetry run ai-source-citation check \
  "what is the population in the uk in 2026?" \
  --expected ons.gov.uk \
  --headless \
  --profile .pw-profile
```

This will:

* Run a search
* Extract sources
* Analyse citations
* Output results to the console.

### Run the Tool (Expected Answer)

You can check for the expected answer by providing an --expected-answer option

Example:

```bash
poetry run ai-source-citation check \
  "What is the latest uk unemployment rate percentage?" \
  --expected ons.gov.uk \
  --expected-answer "5.2%" \
  --no-headless \
  --profile .pw-profile
```

--expected-answer optionally validates that the returned AI answer contains the expected value.

## Usage Instructions - Batch

The following instructions allow a list of search results to be tested for citations.

As with the single shot version, it is best to have used interactive mode to have logged in to a Google Account first.

### Input File

`check-config` now expects each `expected_citation` value to be an **object** (or list of objects) with a required `domain` and an optional `url`. When a URL is provided, the result only passes if the exact URL appears in the AI Overview citations.

```json
{
  "search": [
    {
      "question": "What is the latest uk unemployment rate percentage?",
      "expected_citation": [
        {
          "domain": "ons.gov.uk",
          "url": "https://www.ons.gov.uk/economy/inflationandpriceindices"
        }
      ],
      "expected_answer": "5.2%"
    },
    {
      "question": "when is eastenders shown in the uk",
      "expected_citation": [
        {
          "domain": "bbc.co.uk"
        }
      ],
      "expected_answer": "Wednesday"
    }
  ]
}
```

`expected_answer` remains optional. If provided, the tool checks whether the returned answer text contains the expected value.

### Batch Run (no-headless)

Useful for seeing the browser being launched with each test.

```bash
poetry run ai-source-citation check-config input/example_batch_search.json \
  --csv output/results.csv \
  --json output/results.json \
  --html output/results.html \
  --profile .pw-profile \
  --expand-answer \
  --no-headless
```

--csv will output results as CSV
--json will output results as JSON

### Batch Run (headless)

**Not suggested for initial runs** This runs without the browser being launched.

```bash
poetry run ai-source-citation check-config input/example_batch_search.json \
  --csv output/results.csv \
  --json output/results.json \
  --profile .pw-profile \
  --headless
```

--csv will output results as CSV
--json will output results as JSON

## Example Output

Each row in the CLI/CSV/JSON/HTML output now includes the following:

* **provider** – which search provider handled the question (currently Google only)
* **question** – the input question
* **expected_citations** – list of `{domain, url?}` pairs plus `domain_matched` and `url_matched` flags
* **expected_answer / answer_text / answer_matched** – optional answer validation metadata
* **citations / citation_domains / citation_labels** – the raw URLs/domains/labels returned by AI Overview
* **matched** – `true` only when every expected domain (and, if specified, URL) was observed

CSV exports contain helper columns such as `expected_domains`, `expected_urls`, `matched_domains`, `matched_urls`, and `missing_urls` to make triage easier.

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
  "citation_labels": ["Office for National Statistics"],
  "matched": true
}
```
## Added Features

By using the **--expand-answer** option the tool will click the "Show More" buttun under Google's AI Overview and capture the full AI response as the answer_text.

By using the **--html output/filename.html** option the tool will generate a simple html report of the results that can be viewed in a browser.
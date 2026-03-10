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

## Usage Instructions

### Run the Tool (Interactive)

Interactive mode runs the tool, opening a browser window and pausing to allow you to **login to your google account** (this is recommended as AI Overiew is more reliably shown when logged in to an account).

Example:

```bash
poetry run ai-source-citation check \
  "what time is the population in the uk?" \
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
  "what time is the population in the uk?" \      
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

```bash
poetry run source-checker run-headless "your search query"
```

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

## Example Output

The output is displayed as a table with the following elements:

**provider** - Which search is analysed (initially only Google is supported)

**question** - the question analysed

**expected_sources** - the sources that are expected to be cited, those selected with the --expected flag

**answer_text** - the scraped response returned by the search

**citations** - the citations URLs returned alongside the associated search 

**citation_domains** - the top level domain associated with the citations (e.g ons.gov.uk)

**citation_labels** - the labels associated with the citations extracted from the browser (e.g Office for National Statistics)

**matched** - was AI Overview found and was the expected citation returned. (True or False)

**matched_sources** - the expected sources that matched in the citations



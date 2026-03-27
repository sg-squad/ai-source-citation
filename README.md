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

The following is an example file of searches and exected citations.

```json
{
  "search": [
    {
      "question": "What is the latest uk unemployment rate percentage?",
      "expected_citation": "ons.gov.uk",
      "expected_answer": "5.2%"
    },
    {
      "question": "What is the latest official figure for inflation in the uk?",
      "expected_citation": "ons.gov.uk"
    },
    {
      "question": "How many alcohol related deaths were there in 2023?",
      "expected_citation": "ons.gov.uk"
    },
    {
      "question": "when is eastenders shown in the uk",
      "expected_citation": "bbc.co.uk"
    }
  ]
}
```

expected_answer is optional. When provided, the tool will check whether the AI response contains the expected answer text.

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

**expected_answer** – optional expected value to check in the AI answer

**answer_matched** – whether the AI answer text contains the expected answer (True / False / null)

### Single shot at the CLI

This will return a tabular output

### Batch mode at the CLI

If the --csv flag is used a CSV file will be written containing the results.

#### CSV Output Headings
```bash
provider,question,expected_sources,expected_answer,answer_text,answer_matched,citations,citation_domains,citation_labels,matched,matched_sources
```

If the --json flag is used a JSON file will be written containing the results.

#### Example JSON Output

```json
[
  {
    "provider": "google",
    "question": "What is the latest uk unemployment rate percentage?",
    "expected_sources": "ons.gov.uk",
    "expected_answer": "5.2%",
    "answer_text": "The UK unemployment rate for October to December 2025 was 5.2%. This rate, representing 1.88 million people aged 16 and over, is the highest level since 2021. Data released in February 2026 shows an increase in unemployment of 331,000 compared to the previous year. The House of Commons Library +2",
    "answer_matched": true,
    "citations": "...https://www.ons.gov.uk&quot;\nhttps://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment#:~:text\\u003dUnemployment%20rate%20(aged%2016%20and\nhttps://encrypted-tbn0.gstatic.com/images?q\\u003dtbn:ANd9GcQWWGtZDUF7R3LsMGLoUAa8xvrreJxS516IFj0FqTXNdLwOpmb6&quot;\nhttps://www.ons.gov.uk/employmentandlabourmarket/peoplenotinwork/unemployment&quot;\n...",
    "citation_domains": "..ons.gov.uk&quot;, ons.gov.uk, ...",
    "citation_labels": "The House of Commons Library",
    "matched": true,
    "matched_sources": "ons.gov.uk"
  },
  {
    "provider": "google",
    "question": "What is the latest official figure for inflation in the uk?",
    "expected_sources": "ons.gov.uk",
    "answer_text": "The UK annual inflation rate, measured by the Consumer Prices Index (CPI), was 3.0% in January 2026, according to the Office for National Statistics. This is a decrease from 3.4% in December 2025, driven by lower prices for transport and food. The Office for National Statistics (CPIH) (including owner occupiers' housing costs) was 3.2% in January 2026. Office for National Statistics +2",
    "citations": "https://encrypted-tbn0.gstatic.com/faviconV2?url\\u003dhttps://www.ons.gov.uk\\u0026client\\u003dAIM\\u0026size\\u003d128\\u0026type\\u003dFAVICON\\u0026fallback_opts\\u003dTYPE\nhttps://www.ons.gov.uk&quot;\nhttps://www.ons.gov.uk/economy/inflationandpriceindices#:~:text\\u003dCPIH%20ANNUAL%20RATE%2000:%20ALL\nhttps://encrypted-tbn0.gstatic.com/images?q\\u003dtbn:ANd9GcQWWGtZDUF7R3LsMGLoUAa8xvrreJxS516IFj0FqTXNdLwOpmb6&quot;\nhttps://www.ons.gov.uk/economy/inflationandpriceindices&quot;\nhttps://www.google.com&quot;\nhttps://encrypted-tbn1.gstatic.com/faviconV2?url\\u003dhttps://commonslibrary.parliament.uk\\u0026client\\u003dAIM\\u0026size\\u003d128\\u0026type\\u003dFAVICON\\u0026fallback_opts\\u003dTYPE\nhttps://commonslibrary.parliament.uk&quot;\nhttps://commonslibrary.parliament.uk/research-briefings/sn02792/#:~:text\\u003dLatest%20inflation%20data\nhttps://encrypted-tbn0.gstatic.com/images?q\\u003dtbn:ANd9GcSBdCwc-0eNjUUsUdj9sjx_6DVOYzQ5BpPEBtkQt5YBWJKPo8tv&quot;\nhttps://commonslibrary.parliament.uk/research-briefings/sn02792/&quot;\nhttps://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/december2025#:~:text\\u003dImage%20.csv%20.xls-\nhttps://encrypted-tbn0.gstatic.com/images?q\\u003dtbn:ANd9GcQW6LTfbhxMK32_YtY1th1ofF_gKICmdboxe8KLOM2c5X_BgKnr&quot;\nhttps://www.ons.gov.uk/economy/inflationandpriceindices/bulletins/consumerpriceinflation/december2025&quot;",
    "citation_domains": "encrypted-tbn0.gstatic.com, ons.gov.uk&quot;, ons.gov.uk, encrypted-tbn0.gstatic.com, ons.gov.uk, google.com&quot;, encrypted-tbn1.gstatic.com, commonslibrary.parliament.uk&quot;, commonslibrary.parliament.uk, encrypted-tbn0.gstatic.com, commonslibrary.parliament.uk, ons.gov.uk, encrypted-tbn0.gstatic.com, ons.gov.uk",
    "citation_labels": "Office for National Statistics",
    "matched": true,
    "matched_sources": "ons.gov.uk"
  },
  {
    "provider": "google",
    "question": "How many alcohol related deaths were there in 2023?",
    "expected_sources": "ons.gov.uk",
    "answer_text": "In 2023, there were 10,473 deaths from alcohol-specific causes registered in the UK, marking the highest number on record and a 4% increase from 2022. The death rate was 15.9 per 100,000 people, with men being twice as likely as women to die from these causes. Office for National Statistics +2",
    "citations": "https://encrypted-tbn0.gstatic.com/faviconV2?url\\u003dhttps://www.ons.gov.uk\\u0026client\\u003dAIM\\u0026size\\u003d128\\u0026type\\u003dFAVICON\\u0026fallback_opts\\u003dTYPE\nhttps://www.ons.gov.uk&quot;\n...",
    "citation_domains": "encrypted-tbn0.gstatic.com, ons.gov.uk&quot;, ons.gov.uk, e...",
    "citation_labels": "Office for National Statistics",
    "matched": true,
    "matched_sources": "ons.gov.uk"
  },
  {
    "provider": "google",
    "question": "when is eastenders shown in the uk",
    "expected_sources": "bbc.co.uk",
    "answer_text": "EastEnders typically airs Monday to Thursday at 7:30 pm on BBC One in the UK. Episodes are also available to stream on BBC iPlayer at 6:00 am from Monday to Thursday, allowing viewers to watch early. Schedule changes can occur due to sports or special events. Facebook +6",
    "citations": "...https://www.bbc.co.uk/programmes/b006m86d/broadcasts/upcoming&quot;",
    "citation_domains": "... bbc.co.uk&quot;, bbc.co.uk, encrypted-tbn1.gstatic.com, bbc.co.uk",
    "citation_labels": "Facebook",
    "matched": true,
    "matched_sources": "bbc.co.uk"
  }
]
```

## Added Features

By using the **--expand-answer** option the tool will click the "Show More" buttun under Google's AI Overview and capture the full AI response as the answer_text.

By using the **--html output/filename.html** option the tool will generate a simple html report of the results that can be viewed in a browser.
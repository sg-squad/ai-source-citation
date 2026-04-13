from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Any
from urllib.parse import quote_plus

ASSETS_DIR = Path(__file__).parent / "assets"


def _load_asset(name: str) -> str:
    return (ASSETS_DIR / name).read_text(encoding="utf-8")


def _search_url(provider: str, question: str) -> str:
    query = quote_plus(question)

    provider_name = (provider or "").strip().lower()
    if provider_name == "google":
        return f"https://www.google.com/search?q={query}"
    if provider_name == "bing":
        return f"https://www.bing.com/search?q={query}"

    return f"https://www.google.com/search?q={query}"


def _normalise_results_payload(payload: dict[str, Any]) -> dict[str, Any]:
    run = payload.get("run", {})
    summary = payload.get("summary", {})
    failures = payload.get("failures", [])
    results = payload.get("results", [])

    enriched_results: list[dict[str, Any]] = []
    failure_reason_by_question = {
        failure.get("question"): failure.get("reason", "check failed") for failure in failures
    }

    for result in results:
        question = result.get("question", "")
        matched = bool(result.get("matched", False))
        answer_matched = result.get("answer_matched")
        answer_ok = answer_matched is not False
        expected_answer = result.get("expected_answer")
        answer_text = result.get("answer_text")
        expected_sources = result.get("expected_sources", [])
        matched_sources = result.get("matched_sources", [])
        citation_domains = result.get("citation_domains", [])

        enriched = dict(result)
        enriched["status"] = "passed" if matched and answer_ok else "failed"
        enriched["failure_reason"] = failure_reason_by_question.get(question, "")
        enriched["search_url"] = _search_url(
            str(result.get("provider", run.get("provider", ""))), question
        )
        enriched["expected_answer"] = expected_answer or ""
        enriched["answer_text"] = answer_text or ""
        enriched["expected_sources"] = expected_sources
        enriched["matched_sources"] = matched_sources
        enriched["citation_domains"] = citation_domains
        enriched_results.append(enriched)

    return {
        "run": run,
        "summary": summary,
        "results": enriched_results,
    }


def build_html_report(payload: dict[str, Any]) -> str:
    css = _load_asset("report.css")
    js = _load_asset("report.js")
    normalised_payload = _normalise_results_payload(payload)
    report_json = json.dumps(normalised_payload, ensure_ascii=False)
    report_json = report_json.replace("</script>", "<\\/script>")

    return f"""<!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>AI Source Citation Report</title>
    <style>
    {css}
    </style>
    </head>
    <body>
    <main class="page" id="app">
        <noscript>
        <p>This report needs JavaScript enabled to render the full interactive view.</p>
        </noscript>
    </main>

    <script id="report-data" type="application/json">{report_json}</script>
    <script>
    {js}
    </script>
    </body>
    </html>
    """


def write_html_report(payload: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_html_report(payload), encoding="utf-8")
    return output_path


def open_html_report(output_path: Path) -> None:
    webbrowser.open(output_path.resolve().as_uri())

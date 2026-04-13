from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

from rich.console import Console
from rich.table import Table

from ai_source_citation.models import CheckResultRow, ExpectedCitation
from ai_source_citation.providers.google import GoogleAiOverviewProvider
from ai_source_citation.reporting import build_json_report, build_row, to_dataframe
from ai_source_citation.ui.html_report import open_html_report, write_html_report

console = Console()


class SearchRequest:
    def __init__(
        self,
        *,
        question: str,
        expected_citations: list[ExpectedCitation],
        expected_answer: str | None = None,
    ) -> None:
        self.question = question
        self.expected_citations = expected_citations
        self.expected_answer = expected_answer


def _parse_expected(values: Iterable[str]) -> List[str]:
    """
    Supports:
      --expected bbc.co.uk
      --expected bbc.co.uk --expected wikipedia.org
      --expected bbc.co.uk,wikipedia.org
    """
    out: list[str] = []
    for v in values:
        parts = [p.strip() for p in v.split(",")]
        out.extend([p for p in parts if p])

    return _dedupe_preserve_order(out)


def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _coerce_expected_citations(value: Any, *, item_index: int) -> list[ExpectedCitation]:
    def parse_obj(obj: Any) -> ExpectedCitation:
        if not isinstance(obj, dict):
            raise ValueError(
                f"search[{item_index}].expected_citation entries must be objects with 'domain'"
            )

        domain = obj.get("domain")
        if not isinstance(domain, str) or not domain.strip():
            raise ValueError(
                f"search[{item_index}].expected_citation.domain must be a non-empty string"
            )

        url = obj.get("url")
        if url is not None:
            if not isinstance(url, str):
                raise ValueError(
                    f"search[{item_index}].expected_citation.url must be a string when provided"
                )
            url = url.strip() or None

        return ExpectedCitation(domain=domain.strip(), url=url)

    if isinstance(value, dict):
        expected = [parse_obj(value)]
    elif isinstance(value, list) and value:
        expected = [parse_obj(item) for item in value]
    else:
        raise ValueError(
            f"search[{item_index}].expected_citation must be an object or non-empty list of objects"
        )

    return expected


def _coerce_expected_answer(value: Any, *, item_index: int) -> str | None:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ValueError(f"search[{item_index}].expected_answer must be a string")

    value = value.strip()
    return value or None


def _load_search_requests(config_path: Path) -> list[SearchRequest]:
    import json

    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Config file not found: {config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file {config_path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Config root must be a JSON object")

    search_items = payload.get("search")
    if not isinstance(search_items, list):
        raise ValueError("Config must contain a 'search' array")

    requests: list[SearchRequest] = []
    for idx, item in enumerate(search_items):
        if not isinstance(item, dict):
            raise ValueError(f"search[{idx}] must be an object")

        question = item.get("question")
        if not isinstance(question, str) or not question.strip():
            raise ValueError(f"search[{idx}].question must be a non-empty string")

        if "expected_citation" not in item:
            raise ValueError(f"search[{idx}].expected_citation is required")

        expected_citations = _coerce_expected_citations(
            item["expected_citation"],
            item_index=idx,
        )
        expected_answer = _coerce_expected_answer(
            item.get("expected_answer"),
            item_index=idx,
        )

        requests.append(
            SearchRequest(
                question=question.strip(),
                expected_citations=expected_citations,
                expected_answer=expected_answer,
            )
        )

    if not requests:
        raise ValueError("Config 'search' array must not be empty")

    return requests


async def _run_checks_async(
    requests: Sequence[SearchRequest],
    *,
    headless: bool,
    profile: Optional[str],
    interactive: bool,
    expand_answer: bool,
) -> list[CheckResultRow]:
    provider = GoogleAiOverviewProvider(
        headless=headless,
        user_data_dir=profile,
        interactive=interactive,
        expand_answer=expand_answer,
    )

    rows: list[CheckResultRow] = []
    for request in requests:
        answer = await provider.fetch(request.question)

        row = build_row(
            answer,
            expected_citations=request.expected_citations,
            expected_answer=request.expected_answer,
        )

        rows.append(row)

    return rows


def _print_rich_table(df: Any) -> None:
    table = Table(title="AI Source Citation")
    for col in df.columns:
        table.add_column(col)

    for _, r in df.iterrows():
        table.add_row(*[str(r[c]) for c in df.columns])

    console.print(table)


def _print_run_summary(summary: dict[str, int]) -> None:
    summary_table = Table(title="Run Summary")
    summary_table.add_column("Metric")
    summary_table.add_column("Value")

    summary_table.add_row("Number of checks run", str(summary["checks_run"]))
    summary_table.add_row("Number of checks passed", str(summary["checks_passed"]))
    summary_table.add_row("Number of checks failed", str(summary["checks_failed"]))

    console.print(summary_table)


def _write_outputs(
    rows: Sequence[CheckResultRow],
    *,
    csv_path: Path | None,
    json_path: Path | None,
    html_path: Path | None,
    open_html: bool,
) -> dict[str, Any]:
    import json

    row_list = list(rows)
    df = to_dataframe(row_list)
    _print_rich_table(df)

    provider = row_list[0].provider if row_list else "unknown"
    report_payload = build_json_report(row_list, provider=provider)

    if csv_path:
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
        console.print(f"[green]Wrote CSV:[/green] {csv_path}")

    if json_path:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report_payload, indent=2), encoding="utf-8")
        console.print(f"[green]Wrote JSON:[/green] {json_path}")

    if html_path:
        write_html_report(report_payload, html_path)
        console.print(f"[green]Wrote HTML:[/green] {html_path}")

        if open_html:
            open_html_report(html_path)

    _print_run_summary(report_payload["summary"])
    return report_payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-source-citation")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run a single Google AI Overview citation check")
    check.add_argument(
        "--expand-answer",
        action="store_true",
        help="Click 'Show more' in the AI Overview before extracting answer text.",
    )
    check.add_argument("question", help="Search question to run (quote it).")
    check.add_argument(
        "--expected",
        action="append",
        default=[],
        help="Expected source domain(s). Repeatable or comma-separated.",
    )
    check.add_argument(
        "--expected-answer",
        default=None,
        help="Optional expected answer text to validate against the returned answer_text.",
    )
    check.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    check.add_argument("--csv", type=Path, default=None, help="Write CSV output to path.")
    check.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="Write JSON output to path.",
    )
    check.add_argument(
        "--html",
        dest="html_path",
        type=Path,
        default=None,
        help="Write HTML output to path.",
    )
    check.add_argument(
        "--open-html",
        action="store_true",
        help="Open the generated HTML report in a browser.",
    )
    check.add_argument("--profile", default=None, help="Path to Playwright user data dir.")
    check.add_argument(
        "--interactive",
        action="store_true",
        help="Pause after page load so you can sign in manually.",
    )

    check_config = sub.add_parser(
        "check-config",
        help="Run citation checks from a JSON config file",
    )
    check_config.add_argument(
        "--expand-answer",
        action="store_true",
        help="Click 'Show more' in the AI Overview before extracting answer text.",
    )
    check_config.add_argument(
        "config",
        type=Path,
        help="Path to JSON config file containing a 'search' array.",
    )
    check_config.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    check_config.add_argument("--csv", type=Path, default=None, help="Write CSV output to path.")
    check_config.add_argument(
        "--json",
        dest="json_path",
        type=Path,
        default=None,
        help="Write JSON output to path.",
    )
    check_config.add_argument(
        "--html",
        dest="html_path",
        type=Path,
        default=None,
        help="Write HTML output to path.",
    )
    check_config.add_argument(
        "--open-html",
        action="store_true",
        help="Open the generated HTML report in a browser.",
    )
    check_config.add_argument("--profile", default=None, help="Path to Playwright user data dir.")
    check_config.add_argument(
        "--interactive",
        action="store_true",
        help="Pause after page load so you can sign in manually.",
    )

    args = parser.parse_args(argv)

    if args.command == "check":
        question = args.question.strip()
        if not question:
            parser.error("question must not be empty")

        expected_sources = _parse_expected(args.expected)
        if not expected_sources:
            parser.error("at least one --expected value is required")

        requests = [
            SearchRequest(
                question=question,
                expected_citations=[ExpectedCitation(domain=src) for src in expected_sources],
                expected_answer=args.expected_answer.strip() if args.expected_answer else None,
            )
        ]

        rows = asyncio.run(
            _run_checks_async(
                requests,
                headless=args.headless,
                profile=args.profile,
                interactive=args.interactive,
                expand_answer=args.expand_answer,
            )
        )

        report_payload = _write_outputs(
            rows,
            csv_path=args.csv,
            json_path=args.json_path,
            html_path=args.html_path,
            open_html=args.open_html,
        )

        return 0 if report_payload["summary"]["checks_failed"] == 0 else 1

    if args.command == "check-config":
        try:
            requests = _load_search_requests(args.config)
        except ValueError as exc:
            parser.error(str(exc))

        rows = asyncio.run(
            _run_checks_async(
                requests,
                headless=args.headless,
                profile=args.profile,
                interactive=args.interactive,
                expand_answer=args.expand_answer,
            )
        )

        report_payload = _write_outputs(
            rows,
            csv_path=args.csv,
            json_path=args.json_path,
            html_path=args.html_path,
            open_html=args.open_html,
        )

        return 0 if report_payload["summary"]["checks_failed"] == 0 else 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())

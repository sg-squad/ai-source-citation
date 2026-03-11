from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

from rich.console import Console
from rich.table import Table

from ai_source_citation.providers.google import GoogleAiOverviewProvider
from ai_source_citation.reporting import build_row, to_dataframe

console = Console()


@dataclass(frozen=True)
class SearchRequest:
    question: str
    expected_sources: list[str]
    expected_answer: str | None = None


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


def _coerce_expected_citations(value: Any, *, item_index: int) -> list[str]:
    if isinstance(value, str):
        expected = [value.strip()]
    elif isinstance(value, list) and all(isinstance(v, str) for v in value):
        expected = [v.strip() for v in value]
    else:
        raise ValueError(
            f"search[{item_index}].expected_citation must be a string or list of strings"
        )

    expected = [v for v in expected if v]
    expected = _dedupe_preserve_order(expected)

    if not expected:
        raise ValueError(
            f"search[{item_index}].expected_citation must contain at least one non-empty value"
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

        expected_sources = _coerce_expected_citations(
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
                expected_sources=expected_sources,
                expected_answer=expected_answer,
            )
        )

    if not requests:
        raise ValueError("Config 'search' array must not be empty")

    return requests


def _normalize_text(value: str) -> str:
    """
    Normalize text for simple containment checks:
    - lowercase
    - collapse whitespace
    """
    return re.sub(r"\s+", " ", value).strip().lower()


def _answer_matches(answer_text: str | None, expected_answer: str | None) -> bool | None:
    """
    Returns:
      - True/False when expected_answer is provided
      - None when no expected_answer is supplied
    """
    if expected_answer is None:
        return None

    if not answer_text:
        return False

    normalized_answer = _normalize_text(answer_text)
    normalized_expected = _normalize_text(expected_answer)
    return normalized_expected in normalized_answer


async def _run_checks_async(
    requests: Sequence[SearchRequest],
    *,
    headless: bool,
    profile: Optional[str],
    interactive: bool,
) -> list:
    provider = GoogleAiOverviewProvider(
        headless=headless,
        user_data_dir=profile,
        interactive=interactive,
    )

    rows: list = []
    for request in requests:
        answer = await provider.fetch(request.question)

        row = build_row(
                answer,
                expected_sources=request.expected_sources,
                expected_answer=request.expected_answer,
        )

        rows.append(row)

    return rows


def _print_rich_table(df) -> None:
    table = Table(title="AI Source Citation")
    for col in df.columns:
        table.add_column(col)

    for _, r in df.iterrows():
        table.add_row(*[str(r[c]) for c in df.columns])

    console.print(table)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ai-source-citation")
    sub = parser.add_subparsers(dest="command", required=True)

    check = sub.add_parser("check", help="Run a single Google AI Overview citation check")
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
                expected_sources=expected_sources,
                expected_answer=args.expected_answer.strip() if args.expected_answer else None,
            )
        ]

        rows = asyncio.run(
            _run_checks_async(
                requests,
                headless=args.headless,
                profile=args.profile,
                interactive=args.interactive,
            )
        )
        df = to_dataframe(rows)
        _print_rich_table(df)

        if args.csv:
            df.to_csv(args.csv, index=False)
            console.print(f"[green]Wrote CSV:[/green] {args.csv}")

        if args.json_path:
            records = df.to_dict(orient="records")
            args.json_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
            console.print(f"[green]Wrote JSON:[/green] {args.json_path}")

        return 0

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
            )
        )
        df = to_dataframe(rows)
        _print_rich_table(df)

        if args.csv:
            df.to_csv(args.csv, index=False)
            console.print(f"[green]Wrote CSV:[/green] {args.csv}")

        if args.json_path:
            records = df.to_dict(orient="records")
            args.json_path.write_text(json.dumps(records, indent=2), encoding="utf-8")
            console.print(f"[green]Wrote JSON:[/green] {args.json_path}")

        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
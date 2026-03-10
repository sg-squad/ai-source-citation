from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Iterable, List, Optional

from rich.console import Console
from rich.table import Table

from ai_source_citation.providers.google import GoogleAiOverviewProvider
from ai_source_citation.reporting import build_row, to_dataframe

console = Console()


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

    # dedupe, keep order
    seen: set[str] = set()
    deduped: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            deduped.append(x)
    return deduped


async def _check_async(
    question: str,
    expected_sources: list[str],
    *,
    headless: bool,
    profile: Optional[str],
    interactive: bool,
) -> list:
    provider = GoogleAiOverviewProvider(headless=headless,
                                        user_data_dir=profile,
                                        interactive=interactive)
    answer = await provider.fetch(question)

    print(answer.raw_debug.get("source"))
    print(answer.raw_debug)
    row = build_row(answer, expected_sources=expected_sources)
    return [row]


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

    check = sub.add_parser("check", help="Run a Google AI Overview citation check")
    check.add_argument("question", help="Search question to run (quote it).")
    check.add_argument(
        "--expected",
        action="append",
        default=[],
        help="Expected source domain(s). Repeatable or comma-separated.",
    )
    check.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True)
    check.add_argument("--csv", type=Path, default=None, help="Write CSV output to path.")
    check.add_argument("--json", dest="json_path", type=Path, default=None, help="Write JSON output to path.")
    check.add_argument("--profile", default=None, help="Path to Playwright user data dir.")
    check.add_argument(
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

        rows = asyncio.run(
            _check_async(
                question,
                expected_sources,
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
from __future__ import annotations

import re

from datetime import datetime, timezone
from typing import Any, Sequence
import pandas as pd

from ai_source_citation.models import AiAnswer, CheckResultRow
from ai_source_citation.matching import find_matches, normalize_expected_source


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().lower()


def _answer_matches(answer_text: str | None, expected_answer: str | None) -> bool | None:
    if expected_answer is None:
        return None

    if not answer_text:
        return False

    normalized_answer = _normalize_text(answer_text)
    normalized_expected = _normalize_text(expected_answer)
    return normalized_expected in normalized_answer


def _label_matches_expected(expected: str, label: str) -> bool:
    """
    Loose matching between an expected source and a citation chip label.

    Examples:
      expected: bbc.co.uk
      label: BBC

      expected: ons.gov.uk
      label: Office for National Statistics
    """
    e = normalize_expected_source(expected)
    label_normalized = label.strip().lower()

    if not label_normalized:
        return False

    first_token = e.split(".")[0]

    if first_token and first_token in label_normalized:
        return True

    aliases: dict[str, set[str]] = {
        "bbc.co.uk": {"bbc", "bbc news"},
        "ons.gov.uk": {"ons", "office for national statistics"},
        "wikipedia.org": {"wikipedia"},
        "worldometers.info": {"worldometer", "worldometers"},
        "gov.uk": {"gov.uk", "uk government"},
    }

    for alias in aliases.get(e, set()):
        if alias in label_normalized:
            return True

    return False


def _result_status(row: CheckResultRow) -> str:
    source_match_passed = row.matched
    answer_match_passed = row.answer_matched is not False
    return "passed" if source_match_passed and answer_match_passed else "failed"


def _failure_reason(row: CheckResultRow) -> str:
    if row.answer_text and row.answer_text.startswith("BLOCKED"):
        return row.answer_text

    source_failed = not row.matched
    answer_failed = row.answer_matched is False

    if source_failed and answer_failed:
        return "sources and answer did not match expected"
    if source_failed:
        return "sources did not match expected"
    if answer_failed:
        return "answer did not match expected"

    return ""


def _build_run_summary(rows: Sequence[CheckResultRow]) -> dict[str, int]:
    checks_run = len(rows)
    checks_passed = sum(1 for row in rows if _result_status(row) == "passed")
    checks_failed = checks_run - checks_passed

    return {
        "checks_run": checks_run,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
    }


def _row_to_json_record(row: CheckResultRow) -> dict[str, Any]:
    return {
        "provider": row.provider,
        "question": row.question,
        "expected_sources": list(row.expected_sources),
        "expected_answer": row.expected_answer,
        "answer_text": row.answer_text,
        "answer_matched": row.answer_matched,
        "citations": list(row.citations),
        "citation_domains": list(row.citation_domains),
        "citation_labels": list(row.citation_labels),
        "matched": row.matched,
        "matched_sources": list(row.matched_sources),
        "status": _result_status(row),
    }


def build_json_report(
    rows: Sequence[CheckResultRow],
    *,
    provider: str,
) -> dict[str, Any]:
    summary = _build_run_summary(rows)

    failures = [
        {
            "question": row.question,
            "reason": _failure_reason(row),
            "expected_answer": row.expected_answer,
            "actual_answer": row.answer_text,
            "expected_sources": list(row.expected_sources),
            "matched_sources": list(row.matched_sources),
        }
        for row in rows
        if _result_status(row) == "failed"
    ]

    return {
        "run": {
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        },
        "summary": summary,
        "failures": failures,
        "results": [_row_to_json_record(row) for row in rows],
    }


def build_row(
    answer: AiAnswer,
    expected_sources: list[str],
    expected_answer: str | None = None,
) -> CheckResultRow:
    citation_urls = tuple(c.url for c in answer.citations)
    citation_domains = tuple(c.domain for c in answer.citations)
    citation_labels = tuple(answer.citation_labels)

    answer_matched = _answer_matches(answer.answer_text, expected_answer)

    if getattr(answer, "is_blocked", False):
        return CheckResultRow(
            provider=answer.provider,
            question=answer.question,
            expected_sources=tuple(expected_sources),
            expected_answer=expected_answer,
            answer_text=f"BLOCKED ({answer.blocked_reason})",
            answer_matched=False if expected_answer is not None else None,
            citations=tuple(),
            citation_domains=tuple(),
            citation_labels=tuple(),
            matched=False,
            matched_sources=tuple(),
        )

    matched_by_domain = set(find_matches(expected_sources, citation_domains))

    matched_by_label = {
        normalize_expected_source(exp)
        for exp in expected_sources
        if any(_label_matches_expected(exp, label) for label in citation_labels)
    }

    matched_sources = tuple(
        s
        for s in [normalize_expected_source(exp) for exp in expected_sources]
        if s in matched_by_domain or s in matched_by_label
    )

    matched = len(set(matched_sources)) == len(
        {normalize_expected_source(s) for s in expected_sources}
    )

    return CheckResultRow(
        provider=answer.provider,
        question=answer.question,
        expected_sources=tuple(expected_sources),
        expected_answer=expected_answer,
        answer_text=answer.answer_text,
        answer_matched=answer_matched,
        citations=citation_urls,
        citation_domains=citation_domains,
        citation_labels=citation_labels,
        matched=matched,
        matched_sources=matched_sources,
    )


def to_dataframe(rows: list[CheckResultRow]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "provider": r.provider,
                "question": r.question,
                "expected_sources": ", ".join(r.expected_sources),
                "expected_answer": r.expected_answer,
                "answer_text": r.answer_text,
                "answer_matched": r.answer_matched,
                "citations": "\n".join(r.citations),
                "citation_domains": ", ".join(r.citation_domains),
                "citation_labels": ", ".join(r.citation_labels),
                "matched": r.matched,
                "matched_sources": ", ".join(r.matched_sources),
            }
            for r in rows
        ]
    )

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Sequence

import pandas as pd

from ai_source_citation.models import (
    AiAnswer,
    CheckResultRow,
    ExpectedCitation,
    ExpectedCitationResult,
)
from ai_source_citation.llm_judge import LlmJudgeResult
from ai_source_citation.matching import (
    find_matches,
    normalize_expected_source,
    normalize_url_for_match,
)


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

    domain_failed = any(not item.domain_matched for item in row.expected_citations)
    url_failed = any(item.url_matched is False for item in row.expected_citations)
    answer_failed = row.answer_matched is False

    if domain_failed and url_failed and answer_failed:
        return "domains, URLs, and answer did not match expected"
    if domain_failed and url_failed:
        return "domains and URLs did not match expected"
    if domain_failed and answer_failed:
        return "sources and answer did not match expected"
    if url_failed and answer_failed:
        return "URLs and answer did not match expected"
    if domain_failed:
        return "sources did not match expected"
    if url_failed:
        return "URLs did not match expected"
    if answer_failed:
        return "answer did not match expected"

    return ""


def _build_citation_health_summary(rows: Sequence[CheckResultRow]) -> dict[str, int]:
    all_health = [item for row in rows for item in row.citation_health if item is not None]
    total = len(all_health)
    healthy = sum(1 for item in all_health if item.is_ok)
    blocked = sum(1 for item in all_health if item.is_blocked)
    failed = total - healthy - blocked

    return {
        "total_citations_checked": total,
        "healthy_citations": healthy,
        "blocked_citations": blocked,
        "failed_citations": failed,
    }


def _build_run_summary(rows: Sequence[CheckResultRow]) -> dict[str, int]:
    checks_run = len(rows)
    checks_passed = sum(1 for row in rows if _result_status(row) == "passed")
    checks_failed = checks_run - checks_passed

    return {
        "checks_run": checks_run,
        "checks_passed": checks_passed,
        "checks_failed": checks_failed,
        **_build_citation_health_summary(rows),
    }


def _row_to_json_record(row: CheckResultRow) -> dict[str, Any]:
    return {
        "provider": row.provider,
        "question": row.question,
        "expected_citations": [
            {
                "domain": item.domain,
                "url": item.url,
                "domain_matched": item.domain_matched,
                "url_matched": item.url_matched,
            }
            for item in row.expected_citations
        ],
        "expected_answer": row.expected_answer,
        "answer_text": row.answer_text,
        "answer_matched": row.answer_matched,
        "llm_judge": (
            {
                "provider": row.llm_judge.provider,
                "model": row.llm_judge.model,
                "matched": row.llm_judge.matched,
                "confidence": row.llm_judge.confidence,
                "reasoning": row.llm_judge.reasoning,
            }
            if row.llm_judge is not None
            else None
        ),
        "citations": list(row.citations),
        "citation_domains": list(row.citation_domains),
        "citation_labels": list(row.citation_labels),
        "citation_health": [
            (
                {
                    "url": item.url,
                    "final_url": item.final_url,
                    "status_code": item.status_code,
                    "is_ok": item.is_ok,
                    "is_redirect": item.is_redirect,
                    "is_blocked": item.is_blocked,
                    "error": item.error,
                    "response_time_ms": item.response_time_ms,
                }
                if item is not None
                else None
            )
            for item in row.citation_health
        ],
        "matched": row.matched,
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
            "expected_citations": [
                {
                    "domain": item.domain,
                    "url": item.url,
                    "domain_matched": item.domain_matched,
                    "url_matched": item.url_matched,
                }
                for item in row.expected_citations
            ],
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


def _evaluate_expected_citations(
    expected_citations: Sequence[ExpectedCitation],
    citation_domains: Sequence[str],
    citation_labels: Sequence[str],
    citation_urls: Sequence[str],
) -> list[ExpectedCitationResult]:
    matched_by_domain = set(
        find_matches([citation.domain for citation in expected_citations], citation_domains)
    )
    matched_by_label = {
        normalize_expected_source(citation.domain)
        for citation in expected_citations
        if any(_label_matches_expected(citation.domain, label) for label in citation_labels)
    }
    normalized_citation_urls = {normalize_url_for_match(url) for url in citation_urls}

    results: list[ExpectedCitationResult] = []
    for expected in expected_citations:
        normalized_domain = normalize_expected_source(expected.domain)
        domain_matched = (
            normalized_domain in matched_by_domain or normalized_domain in matched_by_label
        )

        url_norm = expected.url.strip() if expected.url else None
        url_matched = None
        if url_norm:
            expected_url_normalized = normalize_url_for_match(url_norm)
            url_matched = expected_url_normalized in normalized_citation_urls

        results.append(
            ExpectedCitationResult(
                domain=expected.domain,
                url=url_norm,
                domain_matched=domain_matched,
                url_matched=url_matched,
            )
        )

    return results


def build_row(
    answer: AiAnswer,
    expected_citations: list[ExpectedCitation],
    expected_answer: str | None = None,
    llm_judge: LlmJudgeResult | None = None,
) -> CheckResultRow:
    citation_urls = tuple(c.url for c in answer.citations)
    citation_domains = tuple(c.domain for c in answer.citations)
    citation_labels = tuple(answer.citation_labels)
    citation_health = tuple(c.health for c in answer.citations)

    answer_matched = _answer_matches(answer.answer_text, expected_answer)

    expected_results = _evaluate_expected_citations(
        expected_citations,
        citation_domains,
        citation_labels,
        citation_urls,
    )

    matched = all(
        result.domain_matched and (result.url_matched in (True, None))
        for result in expected_results
    )

    if getattr(answer, "is_blocked", False):
        return CheckResultRow(
            provider=answer.provider,
            question=answer.question,
            expected_citations=tuple(expected_results),
            expected_answer=expected_answer,
            answer_text=f"BLOCKED ({answer.blocked_reason})",
            answer_matched=False if expected_answer is not None else None,
            llm_judge=llm_judge,
            citations=tuple(),
            citation_domains=tuple(),
            citation_labels=tuple(),
            citation_health=tuple(),
            matched=False,
        )

    return CheckResultRow(
        provider=answer.provider,
        question=answer.question,
        expected_citations=tuple(expected_results),
        expected_answer=expected_answer,
        answer_text=answer.answer_text,
        answer_matched=answer_matched,
        llm_judge=llm_judge,
        citations=citation_urls,
        citation_domains=citation_domains,
        citation_labels=citation_labels,
        citation_health=citation_health,
        matched=matched,
    )


def to_dataframe(rows: list[CheckResultRow]) -> pd.DataFrame:
    frame_rows: list[dict[str, Any]] = []
    for row in rows:
        expected_domains = [item.domain for item in row.expected_citations]
        expected_urls = [item.url for item in row.expected_citations if item.url]
        matched_domains = [item.domain for item in row.expected_citations if item.domain_matched]
        matched_urls = [item.url for item in row.expected_citations if item.url_matched]
        missing_urls = [item.url for item in row.expected_citations if item.url_matched is False]
        health_items = [item for item in row.citation_health if item is not None]
        health_ok = sum(1 for item in health_items if item.is_ok)
        health_blocked = sum(1 for item in health_items if item.is_blocked)
        health_failed = len(health_items) - health_ok - health_blocked
        health_statuses = [
            f"{item.url} -> {item.status_code if item.status_code is not None else 'ERR'}"
            for item in health_items
        ]

        frame_rows.append(
            {
                "provider": row.provider,
                "question": row.question,
                "expected_domains": ", ".join(expected_domains),
                "expected_urls": ", ".join(expected_urls),
                "expected_answer": row.expected_answer,
                "answer_text": row.answer_text,
                "answer_matched": row.answer_matched,
                "llm_judge_matched": row.llm_judge.matched if row.llm_judge else None,
                "llm_judge_confidence": row.llm_judge.confidence if row.llm_judge else None,
                "llm_judge_reasoning": row.llm_judge.reasoning if row.llm_judge else None,
                "llm_judge_model": row.llm_judge.model if row.llm_judge else None,
                "citations": "\n".join(row.citations),
                "citation_domains": ", ".join(row.citation_domains),
                "citation_labels": ", ".join(row.citation_labels),
                "matched": row.matched,
                "matched_domains": ", ".join(matched_domains),
                "matched_urls": ", ".join(filter(None, matched_urls)),
                "missing_urls": ", ".join(filter(None, missing_urls)),
                "citations_checked": len(health_items),
                "citations_healthy": health_ok,
                "citations_blocked": health_blocked,
                "citations_failed": health_failed,
                "citation_health": "\n".join(health_statuses),
            }
        )

    return pd.DataFrame(frame_rows)

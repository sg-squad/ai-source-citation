from __future__ import annotations

import pandas as pd

from ai_source_citation.models import AiAnswer, CheckResultRow
from ai_source_citation.matching import find_matches, normalize_expected_source


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
    l = label.strip().lower()

    if not l:
        return False

    # Basic domain-derived token
    # bbc.co.uk -> bbc
    # ons.gov.uk -> ons
    first_token = e.split(".")[0]

    if first_token and first_token in l:
        return True

    # A few useful source-name aliases for common cases
    aliases: dict[str, set[str]] = {
        "bbc.co.uk": {"bbc", "bbc news"},
        "ons.gov.uk": {"ons", "office for national statistics"},
        "wikipedia.org": {"wikipedia"},
        "worldometers.info": {"worldometer", "worldometers"},
        "gov.uk": {"gov.uk", "uk government"},
    }

    for alias in aliases.get(e, set()):
        if alias in l:
            return True

    return False


def build_row(answer: AiAnswer, expected_sources: list[str]) -> CheckResultRow:
    citation_urls = tuple(c.url for c in answer.citations)
    citation_domains = tuple(c.domain for c in answer.citations)
    citation_labels = tuple(answer.citation_labels)


    if getattr(answer, "is_blocked", False):
        return CheckResultRow(
            provider=answer.provider,
            question=answer.question,
            expected_sources=tuple(expected_sources),
            answer_text=f"BLOCKED ({answer.blocked_reason})",
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
        answer_text=answer.answer_text,
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
                "answer_text": r.answer_text,
                "citations": "\n".join(r.citations),
                "citation_domains": ", ".join(r.citation_domains),
                "citation_labels": ", ".join(r.citation_labels),
                "matched": r.matched,
                "matched_sources": ", ".join(r.matched_sources),
            }
            for r in rows
        ]
    )
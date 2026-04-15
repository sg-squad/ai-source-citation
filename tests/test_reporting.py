from ai_source_citation.models import AiAnswer, Citation, ExpectedCitation
from ai_source_citation.reporting import build_row, _failure_reason
from ai_source_citation.ui.html_report import build_html_report


def _basic_answer(citations):
    return AiAnswer(
        provider="google",
        question="test question",
        answer_text="Example answer",
        citations=tuple(citations),
        raw_debug={},
        citation_labels=("Office for National Statistics",),
    )


def test_build_row_domain_only_passes():
    answer = _basic_answer(
        [
            Citation(
                url="https://www.ons.gov.uk/example",
                domain="ons.gov.uk",
            )
        ]
    )

    row = build_row(answer, [ExpectedCitation(domain="ons.gov.uk")])

    assert row.matched is True
    assert all(item.domain_matched for item in row.expected_citations)


def test_build_row_requires_url_match_when_provided():
    answer = _basic_answer(
        [
            Citation(
                url="https://www.ons.gov.uk/example",
                domain="ons.gov.uk",
            )
        ]
    )

    row = build_row(
        answer,
        [
            ExpectedCitation(
                domain="ons.gov.uk",
                url="https://www.ons.gov.uk/example",
            )
        ],
    )

    assert row.matched is True
    assert row.expected_citations[0].url_matched is True


def test_build_row_fails_when_url_missing():
    answer = _basic_answer(
        [
            Citation(
                url="https://www.ons.gov.uk/example",
                domain="ons.gov.uk",
            )
        ]
    )

    row = build_row(
        answer,
        [
            ExpectedCitation(
                domain="ons.gov.uk",
                url="https://www.ons.gov.uk/other",
            )
        ],
    )

    assert row.matched is False
    assert row.expected_citations[0].url_matched is False
    assert "URLs" in _failure_reason(row)


def test_html_report_contains_citation_urls():
    payload = {
        "run": {"provider": "google", "timestamp": "2026-04-14T00:00:00Z"},
        "summary": {"checks_run": 1, "checks_passed": 1, "checks_failed": 0},
        "results": [
            {
                "provider": "google",
                "question": "sample question",
                "matched": True,
                "answer_matched": True,
                "expected_answer": "demo",
                "answer_text": "demo",
                "citations": ["https://example.com/matched", "https://example.com/other"],
                "citation_domains": ["example.com"],
                "citation_labels": ["Example"],
                "expected_citations": [
                    {
                        "domain": "example.com",
                        "url": "https://example.com/matched",
                        "domain_matched": True,
                        "url_matched": True,
                    }
                ],
            }
        ],
    }

    html = build_html_report(payload)

    assert "https://example.com/matched" in html
    assert "https://example.com/other" in html
    assert "chip--matched" in html

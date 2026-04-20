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


def test_build_row_url_match_ignores_text_fragment():
    answer = _basic_answer(
        [
            Citation(
                url=(
                    "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/"
                    "populationestimates/bulletins/provisionalpopulationestimatefortheuk/mid2025"
                    "#:~:text=The%20provisional%20mid%2Dyear%20estimate"
                ),
                domain="ons.gov.uk",
            )
        ]
    )

    row = build_row(
        answer,
        [
            ExpectedCitation(
                domain="ons.gov.uk",
                url=(
                    "https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/"
                    "populationestimates/bulletins/provisionalpopulationestimatefortheuk/mid2025"
                ),
            )
        ],
    )

    assert row.matched is True
    assert row.expected_citations[0].url_matched is True


def test_html_report_expected_and_missing_urls_are_links():
    payload = {
        "run": {"provider": "google", "timestamp": "2026-04-15T00:00:00Z"},
        "summary": {"checks_run": 1, "checks_passed": 0, "checks_failed": 1},
        "failures": [{"question": "sample", "reason": "URLs did not match expected"}],
        "results": [
            {
                "provider": "google",
                "question": "sample",
                "matched": False,
                "answer_matched": True,
                "expected_answer": "demo",
                "answer_text": "demo",
                "citations": [
                    "https://example.com/path#:~:text=fragment",
                    "https://example.com/other",
                ],
                "citation_domains": ["example.com"],
                "citation_labels": ["Example"],
                "expected_citations": [
                    {
                        "domain": "example.com",
                        "url": "https://example.com/path",
                        "domain_matched": True,
                        "url_matched": True,
                    },
                    {
                        "domain": "example.com",
                        "url": "https://example.com/missing",
                        "domain_matched": True,
                        "url_matched": False,
                    },
                ],
            }
        ],
    }

    html = build_html_report(payload)

    assert '"expected_urls": ["https://example.com/path", "https://example.com/missing"]' in html
    assert '"missing_urls": ["https://example.com/missing"]' in html
    assert '"url": "https://example.com/path#:~:text=fragment", "matched": true' in html
    assert "renderUrlList(result.expected_urls || [])" in html
    assert "renderUrlList(result.missing_urls || [])" in html
    assert "chip--matched" in html


def test_json_report_includes_llm_judge():
    from ai_source_citation.llm_judge import LlmJudgeResult
    from ai_source_citation.reporting import build_json_report

    answer = _basic_answer([Citation(url="https://example.com", domain="example.com")])

    row = build_row(
        answer,
        [ExpectedCitation(domain="example.com")],
        expected_answer="95,456,000",
        llm_judge=LlmJudgeResult(
            matched=True,
            confidence=0.92,
            reasoning="semantic match",
            provider="openai",
            model="gpt-test",
        ),
    )

    payload = build_json_report([row], provider="google")

    judge = payload["results"][0]["llm_judge"]
    assert judge is not None
    assert judge["matched"] is True
    assert judge["confidence"] == 0.92
    assert judge["provider"] == "openai"

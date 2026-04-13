from ai_source_citation.models import AiAnswer, Citation, ExpectedCitation
from ai_source_citation.reporting import build_row, _failure_reason


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

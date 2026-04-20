import asyncio

from ai_source_citation.citation_health import CitationHealthChecker


def test_health_checker_status_classification() -> None:
    checker = CitationHealthChecker(
        fetcher=lambda _url, _timeout: (200, "https://example.com/final")
    )
    result = asyncio.run(checker.check("https://example.com"))

    assert result.is_ok is True
    assert result.is_redirect is False
    assert result.is_blocked is False
    assert result.status_code == 200
    assert result.final_url == "https://example.com/final"


def test_health_checker_blocked_status() -> None:
    checker = CitationHealthChecker(fetcher=lambda _url, _timeout: (403, "https://example.com"))
    result = asyncio.run(checker.check("https://example.com"))

    assert result.is_ok is False
    assert result.is_blocked is True
    assert result.error == "403 Forbidden"


def test_health_checker_cache_reuses_result() -> None:
    calls = {"count": 0}

    def fetcher(_url: str, _timeout: float) -> tuple[int | None, str | None]:
        calls["count"] += 1
        return 200, "https://example.com"

    checker = CitationHealthChecker(fetcher=fetcher)
    result1 = asyncio.run(checker.check("https://example.com"))
    result2 = asyncio.run(checker.check("https://example.com"))

    assert calls["count"] == 1
    assert result1 == result2

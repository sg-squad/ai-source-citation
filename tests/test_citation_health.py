import asyncio
import socket
from urllib.error import URLError

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


def test_health_checker_redirect_status_is_pass() -> None:
    checker = CitationHealthChecker(
        fetcher=lambda _url, _timeout: (302, "https://example.com/redirected")
    )
    result = asyncio.run(checker.check("https://example.com"))

    assert result.is_ok is True
    assert result.is_redirect is True
    assert result.is_blocked is False
    assert result.status_code == 302
    assert result.final_url == "https://example.com/redirected"


def test_health_checker_blocked_status() -> None:
    checker = CitationHealthChecker(fetcher=lambda _url, _timeout: (403, "https://example.com"))
    result = asyncio.run(checker.check("https://example.com"))

    assert result.is_ok is False
    assert result.is_blocked is True
    assert result.status_code == 403
    assert result.error == "403 Forbidden"


def test_health_checker_not_found_status_is_failure() -> None:
    checker = CitationHealthChecker(fetcher=lambda _url, _timeout: (404, "https://example.com"))
    result = asyncio.run(checker.check("https://example.com/missing"))

    assert result.is_ok is False
    assert result.is_blocked is False
    assert result.status_code == 404
    assert result.error == "404 Not Found"


def test_health_checker_server_error_status_is_failure() -> None:
    checker = CitationHealthChecker(fetcher=lambda _url, _timeout: (503, "https://example.com"))
    result = asyncio.run(checker.check("https://example.com/down"))

    assert result.is_ok is False
    assert result.is_blocked is False
    assert result.status_code == 503
    assert result.error == "503 Server Error"


def test_health_checker_timeout_error() -> None:
    def fetcher(_url: str, _timeout: float) -> tuple[int | None, str | None]:
        raise socket.timeout("timed out")

    checker = CitationHealthChecker(fetcher=fetcher)
    result = asyncio.run(checker.check("https://example.com/slow"))

    assert result.is_ok is False
    assert result.is_blocked is False
    assert result.status_code is None
    assert result.error == "timeout"


def test_health_checker_network_error() -> None:
    def fetcher(_url: str, _timeout: float) -> tuple[int | None, str | None]:
        raise URLError("dns failure")

    checker = CitationHealthChecker(fetcher=fetcher)
    result = asyncio.run(checker.check("https://example.com/dns"))

    assert result.is_ok is False
    assert result.is_blocked is False
    assert result.status_code is None
    assert "dns failure" in (result.error or "")


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


def test_health_checker_check_many_deduplicates_urls() -> None:
    calls = {"count": 0}

    def fetcher(_url: str, _timeout: float) -> tuple[int | None, str | None]:
        calls["count"] += 1
        return 200, "https://example.com"

    checker = CitationHealthChecker(fetcher=fetcher)
    result = asyncio.run(
        checker.check_many(
            [
                "https://example.com/a",
                "https://example.com/a",
                "https://example.com/b",
            ]
        )
    )

    assert len(result) == 2
    assert calls["count"] == 2

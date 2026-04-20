from __future__ import annotations

import asyncio
import socket
import time
from dataclasses import dataclass
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class CitationHealthResult:
    url: str
    final_url: str | None
    status_code: int | None
    is_ok: bool
    is_redirect: bool
    is_blocked: bool
    error: str | None
    response_time_ms: int | None


def _classify_status(
    url: str, status_code: int | None, final_url: str | None
) -> CitationHealthResult:
    is_redirect = status_code is not None and 300 <= status_code <= 399
    is_ok = status_code is not None and (200 <= status_code <= 299 or 300 <= status_code <= 399)
    is_blocked = status_code == 403

    error: str | None = None
    if status_code == 403:
        error = "403 Forbidden"
    elif status_code == 404:
        error = "404 Not Found"
    elif status_code is not None and 500 <= status_code <= 599:
        error = f"{status_code} Server Error"
    elif status_code is not None and 400 <= status_code <= 499 and status_code != 403:
        error = f"{status_code} Client Error"

    return CitationHealthResult(
        url=url,
        final_url=final_url,
        status_code=status_code,
        is_ok=is_ok,
        is_redirect=is_redirect,
        is_blocked=is_blocked,
        error=error,
        response_time_ms=None,
    )


class CitationHealthChecker:
    def __init__(
        self,
        *,
        timeout_seconds: float = 4.0,
        max_concurrency: int = 8,
        fetcher: Callable[[str, float], tuple[int | None, str | None]] | None = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._sem = asyncio.Semaphore(max_concurrency)
        self._cache: dict[str, CitationHealthResult] = {}
        self._fetcher = fetcher or self._fetch_sync

    def _fetch_sync(self, url: str, timeout_seconds: float) -> tuple[int | None, str | None]:
        req = Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            },
        )
        with urlopen(req, timeout=timeout_seconds) as response:  # noqa: S310
            status = response.getcode()
            final_url = response.geturl()
            return status, final_url

    async def check(self, url: str) -> CitationHealthResult:
        cached = self._cache.get(url)
        if cached is not None:
            return cached

        async with self._sem:
            # double-check after waiting on semaphore
            cached = self._cache.get(url)
            if cached is not None:
                return cached

            start = time.perf_counter()
            try:
                status_code, final_url = await asyncio.to_thread(
                    self._fetcher,
                    url,
                    self._timeout_seconds,
                )
                result = _classify_status(url, status_code, final_url)
            except HTTPError as exc:
                result = _classify_status(
                    url, exc.code, exc.geturl() if hasattr(exc, "geturl") else None
                )
            except (TimeoutError, socket.timeout):
                result = CitationHealthResult(
                    url=url,
                    final_url=None,
                    status_code=None,
                    is_ok=False,
                    is_redirect=False,
                    is_blocked=False,
                    error="timeout",
                    response_time_ms=None,
                )
            except URLError as exc:
                result = CitationHealthResult(
                    url=url,
                    final_url=None,
                    status_code=None,
                    is_ok=False,
                    is_redirect=False,
                    is_blocked=False,
                    error=str(exc.reason),
                    response_time_ms=None,
                )
            except Exception as exc:  # noqa: BLE001
                result = CitationHealthResult(
                    url=url,
                    final_url=None,
                    status_code=None,
                    is_ok=False,
                    is_redirect=False,
                    is_blocked=False,
                    error=str(exc),
                    response_time_ms=None,
                )

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            result = CitationHealthResult(
                url=result.url,
                final_url=result.final_url,
                status_code=result.status_code,
                is_ok=result.is_ok,
                is_redirect=result.is_redirect,
                is_blocked=result.is_blocked,
                error=result.error,
                response_time_ms=elapsed_ms,
            )
            self._cache[url] = result
            return result

    async def check_many(
        self, urls: list[str] | tuple[str, ...]
    ) -> dict[str, CitationHealthResult]:
        unique_urls: list[str] = []
        seen: set[str] = set()
        for url in urls:
            if url not in seen:
                seen.add(url)
                unique_urls.append(url)

        results = await asyncio.gather(*(self.check(url) for url in unique_urls))
        return {item.url: item for item in results}

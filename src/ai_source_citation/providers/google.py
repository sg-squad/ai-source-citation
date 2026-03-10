from __future__ import annotations

import asyncio
import re
from typing import Optional
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup
from playwright.async_api import Page, async_playwright

from ai_source_citation.models import AiAnswer, Citation
from ai_source_citation.providers.base import SearchProvider

_BLOCK_PATTERNS = [
    r"enable javascript",
    r"unusual traffic",
    r"systems have detected unusual traffic",
    r"not a robot",
    r"captcha",
    r"to continue, please type the characters",
]


def _detect_blocked_page(html: str) -> str | None:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True).lower()
    for pat in _BLOCK_PATTERNS:
        if re.search(pat, text):
            return pat
    if "sorry" in html and "google.com/sorry" in html:
        return "google.com/sorry"
    return None


def _normalize_domain(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host.lstrip("www.")


def _domain_from_url(url: str) -> str:
    return urlparse(url).netloc.lower().lstrip("www.")


def _dedupe_keep_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for x in items:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def _urlencode(q: str) -> str:
    from urllib.parse import quote_plus

    return quote_plus(q)


def _clean_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _clean_google_href(href: str) -> str | None:
    if not href:
        return None

    if href.startswith("/url?") or href.startswith("https://www.google.com/url?"):
        m = re.search(r"[?&]q=([^&]+)", href)
        if m:
            return unquote(m.group(1))

    if href.startswith("http://") or href.startswith("https://"):
        return href

    return None


def _parse_chip_label(label: str) -> str | None:
    """
    Examples:
      'Worldometer (+5) – View related links'
      'Office for National Statistics (+1) – View related links'
    """
    if not label:
        return None

    base = label.split("(")[0].split("–")[0].strip()
    return base or None


class GoogleAiOverviewProvider(SearchProvider):
    """
    Google provider with Playwright-first DOM extraction for AI Overview.

    Strategy:
      1. Load search page in a real browser context.
      2. Detect Google block/interstitial pages.
      3. Extract AI Overview from live DOM using data-subtree markers seen in Google markup.
      4. Fall back to HTML parsing only if DOM extraction fails.
    """

    def __init__(
        self,
        user_data_dir: Optional[str] = None,
        locale: str = "en-GB",
        country: str = "GB",
        headless: bool = True,
        timeout_ms: int = 30_000,
        use_chrome_channel: bool = True,
        interactive: bool = False,
    ) -> None:
        self._user_data_dir = user_data_dir
        self._locale = locale
        self._country = country
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._use_chrome_channel = use_chrome_channel
        self._interactive = interactive

    async def fetch(self, question: str) -> AiAnswer:
        url = (
            "https://www.google.com/search"
            f"?q={_urlencode(question)}"
            f"&hl={self._locale}"
            f"&gl={self._country}"
        )

        html = ""
        ai_text_dom: str | None = None
        citation_urls_dom: list[str] = []
        dom_debug: dict[str, str] = {}
        citation_labels_dom: tuple[str, ...] = tuple()

        async with async_playwright() as p:
            browser = None

            if self._user_data_dir:
                context = await p.chromium.launch_persistent_context(
                    user_data_dir=self._user_data_dir,
                    headless=self._headless,
                    channel="chrome" if self._use_chrome_channel else None,
                    locale=self._locale,
                    timezone_id="Europe/London",
                    viewport={"width": 1365, "height": 900},
                    args=["--disable-blink-features=AutomationControlled"],
                )
                page = await context.new_page()
            else:
                browser = await p.chromium.launch(
                    headless=self._headless,
                    channel="chrome" if self._use_chrome_channel else None,
                    args=["--disable-blink-features=AutomationControlled"],
                )
                context = await browser.new_context(
                    locale=self._locale,
                    timezone_id="Europe/London",
                    viewport={"width": 1365, "height": 900},
                )
                page = await context.new_page()

            page.set_default_timeout(self._timeout_ms)

            await page.goto(url, wait_until="domcontentloaded")
            await _best_effort_accept_consent(page)

            try:
                await page.wait_for_load_state("networkidle")
            except Exception:
                pass

            await asyncio.sleep(1.5)

            # Trigger some lazy-rendered sections
            try:
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(1.0)
                await page.mouse.wheel(0, -800)
                await asyncio.sleep(0.5)
            except Exception:
                pass

            if self._interactive and not self._headless:
                print("\nInteractive mode enabled.")
                print("Sign in / accept consent if needed.")
                print("Press ENTER in the terminal when ready to continue...\n")
                input()

            html = await page.content()

            blocked_reason = _detect_blocked_page(html)
            if blocked_reason:
                await context.close()
                if browser is not None:
                    await browser.close()

                return AiAnswer(
                    provider="google",
                    question=question,
                    answer_text="BLOCKED_BY_GOOGLE",
                    citations=tuple(),
                    raw_debug={"blocked_reason": blocked_reason, "url": url},
                    citation_labels=tuple(),
                    is_blocked=True,
                    blocked_reason=blocked_reason,
                )

            ai_text_dom, citation_urls_dom, citation_labels_dom, dom_debug = (
                await _extract_ai_overview_from_dom(page)
            )

            await context.close()
            if browser is not None:
                await browser.close()

        # Prefer DOM extraction from live page
        if ai_text_dom:
            citations = tuple(
                Citation(url=u, domain=_normalize_domain(u)) for u in citation_urls_dom
            )
            return AiAnswer(
                provider="google",
                question=question,
                answer_text=_clean_text(ai_text_dom),
                citations=citations,
                raw_debug={"source": "playwright_dom", **dom_debug},
                citation_labels=citation_labels_dom,
            )

        # HTML fallback
        answer_text, citation_urls, debug = _parse_google_ai_overview(html)
        citations = tuple(Citation(url=u, domain=_normalize_domain(u)) for u in citation_urls)

        return AiAnswer(
            provider="google",
            question=question,
            answer_text=answer_text,
            citations=citations,
            raw_debug={"source": "html_fallback", **dom_debug, **debug},
            citation_labels=tuple(),
        )


async def _best_effort_accept_consent(page: Page) -> None:
    candidates = [
        "button:has-text('Accept all')",
        "button:has-text('I agree')",
        "button:has-text('Accept')",
    ]
    for sel in candidates:
        try:
            btn = page.locator(sel).first
            if await btn.count() > 0:
                await btn.click(timeout=2_000)
                return
        except Exception:
            continue


async def _extract_ai_overview_from_dom(
    page: Page,
) -> tuple[str | None, list[str], tuple[str, ...], dict[str, str]]:
    """
    Extract AI Overview from the live DOM.

    Returns:
      answer_text_or_none,
      citation_urls,
      citation_labels,
      debug
    """
    debug: dict[str, str] = {"dom_ai_overview_found": "false"}

    # Based on observed Google markup in your session
    container = page.locator("[data-subtree='aimfl'], [data-subtree='aimba']").first
    if await container.count() == 0:
        return None, [], tuple(), debug

    debug["dom_ai_overview_found"] = "true"
    debug["dom_ai_overview_selector"] = "[data-subtree='aimfl'], [data-subtree='aimba']"

    # The subtree node itself is often display: contents, so move up to a real ancestor
    module = container.locator("xpath=ancestor::div[1]").first

    # Walk up a few ancestors until we get enough text to plausibly be the overview block
    for _ in range(4):
        try:
            txt = (await module.inner_text()).strip()
        except Exception:
            txt = ""

        if len(txt) >= 120:
            break
        module = module.locator("xpath=ancestor::div[1]").first

    try:
        answer_text = (await module.inner_text()).strip()
    except Exception:
        return None, [], tuple(), debug

    if not answer_text:
        return None, [], tuple(), debug

    # Collect citation chip labels
    chip_buttons = module.locator("button[aria-label*='View related links']")
    chip_count = await chip_buttons.count()

    chip_names: list[str] = []
    for i in range(min(chip_count, 20)):
        try:
            label = await chip_buttons.nth(i).get_attribute("aria-label")
            name = _parse_chip_label(label or "")
            if name:
                chip_names.append(name)
        except Exception:
            continue

    chip_names = _dedupe_keep_order(chip_names)
    debug["chip_names"] = ", ".join(chip_names)

    # Best-effort: click chips to discover URLs
    urls: list[str] = []
    for i in range(min(chip_count, 8)):
        try:
            btn = chip_buttons.nth(i)
            await btn.click(timeout=2_000)

            await asyncio.sleep(0.5)

            popup_links = page.locator(
                "a[href^='/url?'], a[href^='https://www.google.com/url?'], a[href^='http']"
            )
            n = await popup_links.count()

            for j in range(min(n, 40)):
                href = await popup_links.nth(j).get_attribute("href")
                cleaned = _clean_google_href(href or "")
                if cleaned:
                    d = _domain_from_url(cleaned)
                    if d not in {"google.com", "www.google.com"}:
                        urls.append(cleaned)

            try:
                await page.keyboard.press("Escape")
            except Exception:
                pass
        except Exception:
            continue

    urls = _dedupe_keep_order(urls)
    debug["citation_url_count"] = str(len(urls))

    # Avoid returning the whole page as the answer if the container is too broad
    if len(answer_text) > 12000:
        debug["dom_ai_overview_rejected"] = "module too large"
        return None, [], tuple(chip_names), debug

    return answer_text, urls, tuple(chip_names), debug


def _parse_google_ai_overview(html: str) -> tuple[str, list[str], dict[str, str]]:
    """
    HTML fallback parser.
    Prefer DOM extraction; this exists only as a backup.
    """
    soup = BeautifulSoup(html, "lxml")
    debug: dict[str, str] = {}

    aios = _find_ai_overview_container(soup)
    if aios is None:
        debug["ai_overview_found"] = "false"
        answer_text = _extract_reasonable_fallback_text(soup)
        return answer_text, [], debug

    debug["ai_overview_found"] = "true"
    debug["ai_overview_html_snippet"] = str(aios)[:20_000]

    answer_text = _clean_text(aios.get_text(" ", strip=True))
    citation_urls = _extract_links(aios)

    return answer_text, citation_urls, debug


def _find_ai_overview_container(soup: BeautifulSoup):
    # Prefer subtree markers found in current Google AI Overview markup
    node = soup.find(attrs={"data-subtree": re.compile(r"^aim")})
    if node:
        return node

    # Fallback: old "web answers" attrid markers
    node = soup.find(attrs={"data-attrid": "wa:/description"})
    if node:
        return node

    node = soup.find(attrs={"data-attrid": re.compile(r"^wa:")})
    if node:
        return node

    heading = soup.find(string=re.compile(r"\bAI Overview\b", re.IGNORECASE))
    if heading:
        return heading.parent

    return None


def _extract_links(container) -> list[str]:
    urls: list[str] = []

    candidates: list[str] = []
    for a in container.find_all("a"):
        href = a.get("href")
        if href:
            candidates.append(href)
        data_href = a.get("data-href")
        if data_href:
            candidates.append(data_href)

    for href in candidates:
        if not href or href.startswith("#"):
            continue

        cleaned = _clean_google_href(href)
        if cleaned:
            urls.append(cleaned)

    filtered = []
    for u in urls:
        d = _normalize_domain(u)
        if d in {"google.com", "www.google.com"}:
            continue
        filtered.append(u)

    return _dedupe_keep_order(filtered)


def _extract_reasonable_fallback_text(soup: BeautifulSoup) -> str:
    text = _clean_text(soup.get_text(" ", strip=True))
    return text[:2_000]
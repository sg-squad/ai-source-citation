from __future__ import annotations

import asyncio
import re
from typing import Optional
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup, Comment
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
    return host.removeprefix("www.")


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
    if not label:
        return None
    base = label.split("(")[0].split("–")[0].strip()
    return base or None


def _extract_urls_from_comments(html: str) -> list[str]:
    """
    Extract source URLs embedded in Google comment payloads like:
    <!--TgQPHd|[[...,"https://www.ons.gov.uk/...",...]]-->
    """
    soup = BeautifulSoup(html, "lxml")
    urls: list[str] = []

    for comment in soup.find_all(string=lambda text: isinstance(text, Comment)):
        text = str(comment)
        if "TgQPHd|" not in text:
            continue

        found = re.findall(r'https://[^\s,"\']+', text)
        for url in found:
            # Trim escaped endings or junk punctuation
            cleaned = url.rstrip("\\")
            cleaned = cleaned.rstrip("]")
            cleaned = cleaned.rstrip("}")
            cleaned = cleaned.rstrip('"')
            cleaned = cleaned.rstrip("'")
            if _normalize_domain(cleaned) != "google.com":
                urls.append(cleaned)

    return _dedupe_keep_order(urls)


class GoogleAiOverviewProvider(SearchProvider):
    def __init__(
        self,
        user_data_dir: Optional[str] = None,
        locale: str = "en-GB",
        country: str = "GB",
        headless: bool = True,
        timeout_ms: int = 15_000,
        use_chrome_channel: bool = True,
        interactive: bool = False,
        expand_answer: bool = False,
    ) -> None:
        self._user_data_dir = user_data_dir
        self._locale = locale
        self._country = country
        self._headless = headless
        self._timeout_ms = timeout_ms
        self._use_chrome_channel = use_chrome_channel
        self._interactive = interactive
        self._expand_answer = expand_answer

    async def _expand_ai_overview_answer(self, page) -> None:
        candidates = [
            page.locator("span", has_text="Show more"),
            page.locator("button", has_text="Show more"),
            page.locator("[role='button']", has_text="Show more"),
            page.locator("text=Show more"),
        ]

        for locator in candidates:
            try:
                count = await locator.count()
                if count > 0:
                    first = locator.first
                    if await first.is_visible():
                        await first.click(timeout=2000)
                        await page.wait_for_timeout(750)
                        return
            except Exception:
                continue

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
        citation_labels_dom: tuple[str, ...] = tuple()
        dom_debug: dict[str, str] = {}

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
                print("Expand AI Overview if you want full sources visible.")
                print("Press ENTER in the terminal when ready to continue...\n")
                input()

            if self._expand_answer:
                await self._expand_ai_overview_answer(page)
                await asyncio.sleep(0.5)

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
                await _extract_ai_overview_from_dom(page, html)
            )

            await context.close()
            if browser is not None:
                await browser.close()

        if ai_text_dom:
            citations = tuple(
                Citation(url=u, domain=_normalize_domain(u))
                for u in citation_urls_dom
            )
            return AiAnswer(
                provider="google",
                question=question,
                answer_text=_clean_text(ai_text_dom),
                citations=citations,
                raw_debug={"source": "playwright_dom", **dom_debug},
                citation_labels=citation_labels_dom,
            )

        return AiAnswer(
            provider="google",
            question=question,
            answer_text="NO_AI_OVERVIEW_FOUND",
            citations=tuple(),
            raw_debug={"source": "playwright_dom", **dom_debug},
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
    html: str,
) -> tuple[str | None, list[str], tuple[str, ...], dict[str, str]]:
    debug: dict[str, str] = {"dom_ai_overview_found": "false"}

    container = page.locator("[data-subtree*='aimfl'], [data-subtree*='aimba']").first
    if await container.count() == 0:
        return None, [], tuple(), debug

    debug["dom_ai_overview_found"] = "true"
    debug["dom_ai_overview_selector"] = "[data-subtree*='aimfl'], [data-subtree*='aimba']"

    module = container.locator(
        "xpath=ancestor::div[contains(@class, 'mZJni') and contains(@class, 'Dn7Fzd')]"
    ).first

    if await module.count() == 0:
        module = container.locator("xpath=ancestor::div[1]").first

        for _ in range(5):
            try:
                txt = (await module.inner_text()).strip()
            except Exception:
                txt = ""

            if len(txt) >= 120:
                break
            module = module.locator("xpath=ancestor::div[1]").first

    try:
        answer_text = (await module.inner_text()).strip()
        debug["answer_text_preview"] = answer_text[:500]
    except Exception:
        return None, [], tuple(), debug

    if not answer_text:
        return None, [], tuple(), debug

    # Visible inline source links inside AI Overview
    visible_urls: list[str] = []
    try:
        links = module.locator("a[href]")
        count = await links.count()
        for i in range(min(count, 50)):
            href = await links.nth(i).get_attribute("href")
            cleaned = _clean_google_href(href or "")
            if cleaned:
                domain = _normalize_domain(cleaned)
                if domain not in {"google.com", "www.google.com"}:
                    visible_urls.append(cleaned)
    except Exception:
        pass

    # Citation chip labels
    chip_labels: list[str] = []
    try:
        chip_buttons = module.locator("button[aria-label*='View related links']")
        chip_count = await chip_buttons.count()
        for i in range(min(chip_count, 20)):
            label = await chip_buttons.nth(i).get_attribute("aria-label")
            parsed = _parse_chip_label(label or "")
            if parsed:
                chip_labels.append(parsed)
    except Exception:
        pass

    # Hidden structured source URLs from comment payloads
    hidden_urls = _extract_urls_from_comments(html)

    all_urls = _dedupe_keep_order(visible_urls + hidden_urls)
    chip_labels = _dedupe_keep_order(chip_labels)

    debug["visible_url_count"] = str(len(visible_urls))
    debug["hidden_url_count"] = str(len(hidden_urls))
    debug["chip_names"] = ", ".join(chip_labels)

    if len(answer_text) > 12000:
        debug["dom_ai_overview_rejected"] = "module too large"
        return None, [], tuple(chip_labels), debug

    return answer_text, all_urls, tuple(chip_labels), debug
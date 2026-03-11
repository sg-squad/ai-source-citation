from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Optional, Tuple

ProviderName = Literal["google"]  # extend later


@dataclass(frozen=True)
class Citation:
    url: str
    domain: str


@dataclass(frozen=True)
class AiAnswer:
    provider: ProviderName
    question: str
    answer_text: str
    citations: tuple[Citation, ...]
    raw_debug: dict[str, str]  # store html snippets, selectors hit, etc.
    citation_labels: tuple[str, ...] = field(default_factory=tuple)
    is_blocked: bool = False
    blocked_reason: Optional[str] = None


@dataclass(frozen=True)
class CheckResultRow:
    provider: str
    question: str
    expected_sources: tuple[str, ...]
    expected_answer: str | None
    answer_text: str
    answer_matched: bool | None
    citations: tuple[str, ...]
    citation_domains: tuple[str, ...]
    citation_labels: tuple[str, ...]
    matched: bool
    matched_sources: tuple[str, ...]
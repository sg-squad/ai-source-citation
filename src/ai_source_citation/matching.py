from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class DomainMatchPolicy:
    suffix_match: bool = True  # bbc.co.uk matches news.bbc.co.uk
    case_insensitive: bool = True


def normalize_expected_source(s: str) -> str:
    s = s.strip().lower()
    s = s.removeprefix("http://").removeprefix("https://")
    s = s.split("/")[0]
    s = s.removeprefix("www.")
    return s


def domain_matches(expected: str, actual_domain: str, policy: DomainMatchPolicy) -> bool:
    e = normalize_expected_source(expected)
    a = actual_domain.lower().removeprefix("www.") if policy.case_insensitive else actual_domain.removeprefix("www.")
    if policy.suffix_match:
        return a == e or a.endswith("." + e)
    return a == e


def find_matches(
    expected_sources: Iterable[str],
    citation_domains: Iterable[str],
    policy: DomainMatchPolicy | None = None,
) -> list[str]:
    pol = policy or DomainMatchPolicy()
    found: list[str] = []
    domains = list(citation_domains)

    for exp in expected_sources:
        if any(domain_matches(exp, d, pol) for d in domains):
            found.append(normalize_expected_source(exp))

    # dedupe keep order
    out: list[str] = []
    seen: set[str] = set()
    for x in found:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out
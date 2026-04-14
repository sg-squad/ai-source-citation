from __future__ import annotations

from abc import ABC, abstractmethod
from ai_source_citation.models import AiAnswer


class SearchProvider(ABC):
    """A provider fetches an AI answer + citations for a question."""

    @abstractmethod
    async def fetch(self, question: str) -> AiAnswer:
        raise NotImplementedError

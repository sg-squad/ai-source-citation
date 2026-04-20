import asyncio

from ai_source_citation import cli as cli_mod
from ai_source_citation.llm_judge import LlmJudgeResult
from ai_source_citation.models import AiAnswer, Citation, ExpectedCitation


class _FakeProvider:
    def __init__(self, *_args, **_kwargs) -> None:
        pass

    async def fetch(self, question: str) -> AiAnswer:
        return AiAnswer(
            provider="google",
            question=question,
            answer_text="actual answer",
            citations=(Citation(url="https://example.com", domain="example.com"),),
            raw_debug={},
        )


class _FakeHealthChecker:
    async def check_many(self, _urls):
        return {}


class _FakeJudge:
    def __init__(self) -> None:
        self.calls = 0

    async def judge(self, *, expected_answer: str, actual_answer: str) -> LlmJudgeResult:
        self.calls += 1
        assert expected_answer
        assert actual_answer
        return LlmJudgeResult(
            matched=True,
            confidence=0.9,
            reasoning="close enough",
            provider="openai",
            model="gpt-test",
        )


def test_run_checks_calls_llm_judge_only_on_expected_answer_mismatch(monkeypatch) -> None:
    monkeypatch.setattr(cli_mod, "GoogleAiOverviewProvider", _FakeProvider)
    monkeypatch.setattr(cli_mod, "CitationHealthChecker", lambda: _FakeHealthChecker())

    judge = _FakeJudge()
    requests = [
        cli_mod.SearchRequest(
            question="q",
            expected_citations=[ExpectedCitation(domain="example.com")],
            expected_answer="different expected answer",
        )
    ]

    rows = asyncio.run(
        cli_mod._run_checks_async(
            requests,
            headless=True,
            profile=None,
            interactive=False,
            expand_answer=False,
            llm_judge_service=judge,
        )
    )

    assert judge.calls == 1
    assert rows[0].llm_judge is not None
    assert rows[0].llm_judge.matched is True


def test_run_checks_skips_llm_judge_when_answer_matches(monkeypatch) -> None:
    class _MatchingProvider(_FakeProvider):
        async def fetch(self, question: str) -> AiAnswer:
            return AiAnswer(
                provider="google",
                question=question,
                answer_text="exact expected",
                citations=(Citation(url="https://example.com", domain="example.com"),),
                raw_debug={},
            )

    monkeypatch.setattr(cli_mod, "GoogleAiOverviewProvider", _MatchingProvider)
    monkeypatch.setattr(cli_mod, "CitationHealthChecker", lambda: _FakeHealthChecker())

    judge = _FakeJudge()
    requests = [
        cli_mod.SearchRequest(
            question="q",
            expected_citations=[ExpectedCitation(domain="example.com")],
            expected_answer="exact expected",
        )
    ]

    rows = asyncio.run(
        cli_mod._run_checks_async(
            requests,
            headless=True,
            profile=None,
            interactive=False,
            expand_answer=False,
            llm_judge_service=judge,
        )
    )

    assert judge.calls == 0
    assert rows[0].llm_judge is None

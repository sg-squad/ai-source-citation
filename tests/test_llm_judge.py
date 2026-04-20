import json
from pathlib import Path

from ai_source_citation.llm_judge import LlmJudgeResult, LlmJudgeService


def _write_judge_files(tmp_path: Path) -> Path:
    prompt_path = tmp_path / "prompt.txt"
    schema_path = tmp_path / "schema.json"
    config_path = tmp_path / "judge.json"

    prompt_path.write_text(
        "Expected: {{expected_answer}}\nActual: {{actual_answer}}\nSchema: {{response_schema}}",
        encoding="utf-8",
    )
    schema_path.write_text(
        json.dumps({"matched": "boolean", "confidence": "number", "reasoning": "string"}),
        encoding="utf-8",
    )
    config_path.write_text(
        json.dumps(
            {
                "provider": "openai",
                "model": "gpt-test",
                "prompt_path": "prompt.txt",
                "response_schema_path": "schema.json",
            }
        ),
        encoding="utf-8",
    )
    return config_path


def test_judge_from_file_resolves_relative_paths(tmp_path: Path) -> None:
    config_path = _write_judge_files(tmp_path)
    service = LlmJudgeService.from_file(config_path)

    assert service.config.provider == "openai"
    assert service.config.model == "gpt-test"
    assert service.config.prompt_path.endswith("prompt.txt")
    assert service.config.response_schema_path.endswith("schema.json")


class _FakeJudgeService(LlmJudgeService):
    def __init__(self, config_path: Path, payload: dict[str, object]) -> None:
        super().__init__(LlmJudgeService.from_file(config_path).config)
        self._payload = payload

    async def _call_openai(self, prompt: str):  # type: ignore[override]
        assert "Expected:" in prompt
        assert "Actual:" in prompt
        return self._payload


def test_judge_parses_structured_response(tmp_path: Path) -> None:
    config_path = _write_judge_files(tmp_path)
    service = _FakeJudgeService(
        config_path,
        payload={"matched": True, "confidence": 0.87, "reasoning": "close numeric answer"},
    )

    result = __import__("asyncio").run(
        service.judge(expected_answer="95,456,000", actual_answer="approx 95.5 million")
    )

    assert isinstance(result, LlmJudgeResult)
    assert result.matched is True
    assert result.confidence == 0.87
    assert "close" in result.reasoning


def test_judge_clamps_invalid_confidence(tmp_path: Path) -> None:
    config_path = _write_judge_files(tmp_path)
    service = _FakeJudgeService(
        config_path,
        payload={"matched": False, "confidence": 2.5, "reasoning": "not equivalent"},
    )

    result = __import__("asyncio").run(service.judge(expected_answer="5.2%", actual_answer="7.0%"))

    assert result.matched is False
    assert result.confidence == 1.0

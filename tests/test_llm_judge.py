import json
from pathlib import Path

from ai_source_citation.llm_judge import LlmJudgeResult, LlmJudgeService


def _write_judge_files(
    tmp_path: Path,
    *,
    provider: str = "openai",
    project: str | None = None,
    location: str | None = None,
) -> Path:
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
                "provider": provider,
                "model": "gpt-test",
                "prompt_path": "prompt.txt",
                "response_schema_path": "schema.json",
                **({"project": project} if project is not None else {}),
                **({"location": location} if location is not None else {}),
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


def test_judge_from_file_optional_project_location(tmp_path: Path) -> None:
    config_path = _write_judge_files(
        tmp_path,
        provider="gemini",
        project="my-gcp-project",
        location="europe-west2",
    )
    service = LlmJudgeService.from_file(config_path)

    assert service.config.provider == "gemini"
    assert service.config.project == "my-gcp-project"
    assert service.config.location == "europe-west2"


def test_resolve_vertex_project_location_with_config_overrides(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "env-project")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-east4")

    config_path = _write_judge_files(
        tmp_path,
        provider="gemini",
        project="config-project",
        location="europe-west1",
    )
    service = LlmJudgeService.from_file(config_path)

    project, location = service._resolve_vertex_project_location("inferred-project")

    assert project == "config-project"
    assert location == "europe-west1"


def test_resolve_vertex_project_location_with_env_and_fallback(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("GOOGLE_CLOUD_PROJECT", raising=False)
    monkeypatch.delenv("GCP_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_LOCATION", raising=False)
    monkeypatch.delenv("GOOGLE_CLOUD_REGION", raising=False)
    monkeypatch.delenv("VERTEX_AI_LOCATION", raising=False)

    config_path = _write_judge_files(tmp_path, provider="gemini")
    service = LlmJudgeService.from_file(config_path)

    project, location = service._resolve_vertex_project_location("inferred-project")

    assert project == "inferred-project"
    assert location == "us-central1"

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast


JudgeProvider = Literal["openai", "gemini"]


@dataclass(frozen=True)
class LlmJudgeResult:
    matched: bool
    confidence: float
    reasoning: str
    provider: JudgeProvider
    model: str


@dataclass(frozen=True)
class LlmJudgeConfig:
    provider: JudgeProvider
    model: str
    prompt_path: str
    response_schema_path: str


class LlmJudgeService:
    def __init__(self, config: LlmJudgeConfig) -> None:
        self._config = config
        self._prompt_template = Path(config.prompt_path).read_text(encoding="utf-8")
        self._response_schema = json.loads(
            Path(config.response_schema_path).read_text(encoding="utf-8")
        )

    @property
    def config(self) -> LlmJudgeConfig:
        return self._config

    @staticmethod
    def from_file(path: str | Path) -> LlmJudgeService:
        config_path = Path(path)
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        base = config_path.parent
        prompt_path = (
            (base / payload["prompt_path"]).resolve()
            if not Path(payload["prompt_path"]).is_absolute()
            else Path(payload["prompt_path"])
        )
        schema_path = (
            (base / payload["response_schema_path"]).resolve()
            if not Path(payload["response_schema_path"]).is_absolute()
            else Path(payload["response_schema_path"])
        )

        config = LlmJudgeConfig(
            provider=payload["provider"],
            model=payload["model"],
            prompt_path=str(prompt_path),
            response_schema_path=str(schema_path),
        )
        return LlmJudgeService(config)

    def _build_prompt(self, expected_answer: str, actual_answer: str) -> str:
        schema_json = json.dumps(self._response_schema, indent=2)
        return (
            self._prompt_template.replace("{{expected_answer}}", expected_answer)
            .replace("{{actual_answer}}", actual_answer)
            .replace("{{response_schema}}", schema_json)
        )

    async def judge(self, *, expected_answer: str, actual_answer: str) -> LlmJudgeResult:
        prompt = self._build_prompt(expected_answer=expected_answer, actual_answer=actual_answer)

        if self._config.provider == "openai":
            payload = await self._call_openai(prompt)
        elif self._config.provider == "gemini":
            payload = await self._call_gemini(prompt)
        else:
            raise ValueError(f"Unsupported llm judge provider: {self._config.provider}")

        matched = bool(payload.get("matched", False))
        confidence_raw = payload.get("confidence", 0.0)
        try:
            confidence = float(confidence_raw)
        except (TypeError, ValueError):
            confidence = 0.0
        confidence = min(max(confidence, 0.0), 1.0)

        return LlmJudgeResult(
            matched=matched,
            confidence=confidence,
            reasoning=str(payload.get("reasoning", "")).strip(),
            provider=self._config.provider,
            model=self._config.model,
        )

    async def _call_openai(self, prompt: str) -> dict[str, Any]:
        try:
            from openai import AsyncOpenAI
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "OpenAI SDK not installed. Add 'openai' to dependencies to use --llm-judge with provider=openai."
            ) from exc

        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model=self._config.model,
            messages=[
                {
                    "role": "system",
                    "content": "Return only JSON matching the provided response_schema.",
                },
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
        )

        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("OpenAI judge returned empty content")
        return cast(dict[str, Any], json.loads(content))

    async def _call_gemini(self, prompt: str) -> dict[str, Any]:
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "Google GenAI SDK not installed. Add 'google-genai' to dependencies to use --llm-judge with provider=gemini."
            ) from exc

        client = genai.Client()
        response = client.models.generate_content(
            model=self._config.model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini judge returned empty content")
        return cast(dict[str, Any], json.loads(text))

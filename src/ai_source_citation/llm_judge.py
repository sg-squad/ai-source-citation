from __future__ import annotations

import json
import os
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
    project: str | None = None
    location: str | None = None


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
            project=payload.get("project"),
            location=payload.get("location"),
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

    def _resolve_vertex_project_location(
        self, inferred_project: str | None
    ) -> tuple[str | None, str]:
        project = (
            self._config.project
            or os.getenv("GOOGLE_CLOUD_PROJECT")
            or os.getenv("GCP_PROJECT")
            or inferred_project
        )
        location = (
            self._config.location
            or os.getenv("GOOGLE_CLOUD_LOCATION")
            or os.getenv("GOOGLE_CLOUD_REGION")
            or os.getenv("VERTEX_AI_LOCATION")
            or "us-central1"
        )
        return project, location

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

        gemini_api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        openai_api_key = os.getenv("OPENAI_API_KEY")

        if gemini_api_key or openai_api_key:
            # Keep existing API-key based behavior when API key env vars are present.
            client = genai.Client(api_key=gemini_api_key) if gemini_api_key else genai.Client()
        else:
            try:
                import google.auth
            except ImportError as exc:  # pragma: no cover
                raise RuntimeError(
                    "google-auth is required for Gemini ADC mode. Add 'google-auth' dependency."
                ) from exc

            try:
                credentials, inferred_project = google.auth.default(
                    scopes=["https://www.googleapis.com/auth/cloud-platform"]
                )
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    "Gemini ADC credentials are unavailable. Configure Application Default Credentials "
                    "(for example via GOOGLE_APPLICATION_CREDENTIALS or gcloud auth application-default login)."
                ) from exc

            project, location = self._resolve_vertex_project_location(inferred_project)
            if not project:
                raise RuntimeError(
                    "Gemini ADC mode requires a GCP project. Set config.project, GOOGLE_CLOUD_PROJECT, "
                    "GCP_PROJECT, or use ADC with an inferred project."
                )

            client = genai.Client(
                vertexai=True,
                project=project,
                location=location,
                credentials=credentials,
            )

        response = client.models.generate_content(
            model=self._config.model,
            contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json"),
        )

        text = getattr(response, "text", None)
        if not text:
            raise RuntimeError("Gemini judge returned empty content")
        return cast(dict[str, Any], json.loads(text))

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from openai import OpenAI, OpenAIError

from app.config import settings
from app.models import SuggestionPayload
from app.prompts import SYSTEM, USER_TEMPLATE

logger = logging.getLogger(__name__)


class LLMUnavailableError(RuntimeError):
    """Raised when the LLM cannot be reached or used."""


@runtime_checkable
class StructuredLLMProvider(Protocol):
    """Common protocol for structured LLM providers."""

    name: str

    def suggest_events(
        self, instruction: str, now_iso: str, timezone: str
    ) -> SuggestionPayload: ...


@dataclass(slots=True)
class _SuggestContext:
    instruction: str
    now_iso: str
    timezone: str


class OfflineLLMProvider:
    """Fallback provider used when credentials are missing."""

    def __init__(self, name: str = "offline") -> None:
        self.name = name

    def suggest_events(
        self, instruction: str, now_iso: str, timezone: str
    ) -> SuggestionPayload:
        logger.info(
            "LLM provider '%s' operating in offline mode", self.name
        )
        return SuggestionPayload(candidates=[])


class OpenAIProvider:
    """Structured generation provider backed by OpenAI Responses API."""

    name = "openai"

    def __init__(
        self,
        *,
        api_host: str,
        api_key: str,
        model: str,
        temperature: float,
        client: OpenAI | None = None,
        default_headers: dict[str, str] | None = None,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._client = client
        if self._client is None:
            try:
                self._client = OpenAI(
                    api_key=api_key,
                    base_url=api_host or None,
                    default_headers=default_headers,
                )
            except OpenAIError as exc:  # pragma: no cover - defensive logging
                logger.error("Failed to initialise OpenAI client: %s", exc)
                self._client = None

        if self._client is None:
            raise LLMUnavailableError("OpenAI client is not configured")

    def suggest_events(
        self, instruction: str, now_iso: str, timezone: str
    ) -> SuggestionPayload:
        ctx = _SuggestContext(instruction=instruction, now_iso=now_iso, timezone=timezone)
        user_prompt = USER_TEMPLATE.format(
            instruction=ctx.instruction, now=ctx.now_iso, timezone=ctx.timezone
        )

        try:
            response = self._client.responses.parse(
                model=self._model,
                temperature=self._temperature,
                max_output_tokens=1200,
                input=[
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                text_format=SuggestionPayload,
            )
        except OpenAIError as exc:  # pragma: no cover - network failure path
            logger.error("Structured generation failed: %s", exc)
            raise LLMUnavailableError(str(exc)) from exc

        if response.output is None or not getattr(response, "output_parsed", None):
            logger.warning("LLM returned empty structured payload: %s", response)
            return SuggestionPayload(candidates=[])

        payload: SuggestionPayload = response.output_parsed
        logger.debug("Received %d candidates from %s", len(payload.candidates), self.name)
        return payload


class OpenRouterProvider(OpenAIProvider):
    """OpenRouter provider using the OpenAI-compatible SDK."""

    name = "openrouter"

    def __init__(
        self,
        *,
        api_host: str,
        api_key: str,
        model: str,
        temperature: float,
    ) -> None:
        super().__init__(
            api_host=api_host,
            api_key=api_key,
            model=model,
            temperature=temperature,
            default_headers={"X-Title": "AI Calendar Assistant"},
        )


class LLMClient:
    """Wrapper that selects the correct LLM provider at runtime."""

    def __init__(self, provider: StructuredLLMProvider | None = None) -> None:
        self._provider = provider or self._build_provider()
        self._provider_name = getattr(self._provider, "name", "unknown")

    def suggest_events(
        self, instruction: str, now_iso: str, timezone: str
    ) -> SuggestionPayload:
        try:
            return self._provider.suggest_events(instruction, now_iso, timezone)
        except LLMUnavailableError as exc:
            logger.warning(
                "LLM provider '%s' unavailable: %s", self._provider_name, exc
            )
            return SuggestionPayload(candidates=[])

    # ----------------------------------------------------------------- internals
    def _build_provider(self) -> StructuredLLMProvider:
        provider_key = (settings.llm_provider or "openai").lower()
        if provider_key == "openai":
            api_key = settings.openai_api_key
            if not api_key:
                return OfflineLLMProvider("openai")
            try:
                return OpenAIProvider(
                    api_host=settings.openai_api_host,
                    api_key=api_key,
                    model=settings.openai_model,
                    temperature=settings.openai_temperature,
                )
            except LLMUnavailableError as exc:  # pragma: no cover - defensive
                logger.error("Failed to build OpenAI provider: %s", exc)
                return OfflineLLMProvider("openai")
        if provider_key == "openrouter":
            api_key = settings.openrouter_api_key or settings.openai_api_key
            if not api_key:
                return OfflineLLMProvider("openrouter")
            try:
                return OpenRouterProvider(
                    api_host=settings.openrouter_api_host,
                    api_key=api_key,
                    model=settings.openai_model,
                    temperature=settings.openai_temperature,
                )
            except LLMUnavailableError as exc:  # pragma: no cover - defensive
                logger.error("Failed to build OpenRouter provider: %s", exc)
                return OfflineLLMProvider("openrouter")

        logger.warning(
            "Unknown LLM provider '%s'; falling back to offline mode", provider_key
        )
        return OfflineLLMProvider(provider_key)


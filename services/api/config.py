from __future__ import annotations

import logging
import os

from pydantic import BaseModel, ConfigDict


class Settings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", 0.2))
    openai_api_host: str = os.getenv(
        "OPENAI_API_HOST", "https://api.openai.com/v1"
    )

    llm_provider: str = os.getenv("LLM_PROVIDER", "openai")
    openrouter_api_key: str = os.getenv("OPENROUTER_API_KEY", "")
    openrouter_api_host: str = os.getenv(
        "OPENROUTER_API_HOST", "https://openrouter.ai/api/v1"
    )

    project_timezone: str = os.getenv("PROJECT_TIMEZONE", "Europe/Riga")

    google_creds_json: str = os.getenv("GOOGLE_CREDS_JSON", "")
    google_token_json: str = os.getenv("GOOGLE_TOKEN_JSON", "")
    google_calendar_id: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    sqlite_db_path: str = os.getenv("SQLITE_DB_PATH", "calendar_assistant.db")

    def model_post_init(self, __context: dict[str, object]) -> None:
        logger = logging.getLogger(__name__)
        provider = (self.llm_provider or "openai").lower()
        if provider == "openai" and not self.openai_api_key:
            logger.warning(
                "OPENAI_API_KEY is not configured. LLM features will operate in offline mode."
            )
        if provider == "openrouter" and not (
            self.openrouter_api_key or self.openai_api_key
        ):
            logger.warning(
                "OpenRouter credentials are missing. LLM features will operate in offline mode."
            )


settings = Settings()
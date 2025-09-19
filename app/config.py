from __future__ import annotations
import os
from pydantic import BaseModel, field_validator

class Settings(BaseModel):
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    openai_temperature: float = float(os.getenv("OPENAI_TEMPERATURE", 0.2))

    project_timezone: str = os.getenv("PROJECT_TIMEZONE", "Europe/Riga")

    google_creds_json: str = os.getenv("GOOGLE_CREDS_JSON", "")
    google_token_json: str = os.getenv("GOOGLE_TOKEN_JSON", "")
    google_calendar_id: str = os.getenv("GOOGLE_CALENDAR_ID", "primary")

    google_client_id: str = os.getenv("GOOGLE_CLIENT_ID", "")
    google_client_secret: str = os.getenv("GOOGLE_CLIENT_SECRET", "")
    google_redirect_uri: str = os.getenv("GOOGLE_REDIRECT_URI", "")

    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    @field_validator("openai_api_key")
    @classmethod
    def _check_openai(cls, v: str) -> str:
        if not v:
            raise ValueError("OPENAI_API_KEY is required")
        return v

settings = Settings()
from __future__ import annotations
import json
import logging
from typing import Any, Dict
from app.config import settings
from app.prompts import SYSTEM, USER_TEMPLATE
from openai import OpenAI

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self) -> None:
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.temperature = settings.openai_temperature

    def suggest_events(self, instruction: str, now: str, timezone: str) -> Dict[str, Any]:
        user = USER_TEMPLATE.format(instruction=instruction, now=now, timezone=timezone)
        resp = self.client.chat.completions.create(
            model=self.model,
            temperature=self.temperature,
            response_format={"type": "json_object"},  # строгий JSON
            messages=[
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
        )
        content = resp.choices[0].message.content
        logger.info("Raw LLM JSON: %s", content)
        return json.loads(content)
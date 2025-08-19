from typing import Any, Dict
from openai import OpenAI

from .config import settings


class LLMClient:
    def __init__(self, api_key: str | None = None):
        self.client = OpenAI(api_key=api_key or settings.openai_api_key)

    def chat(self, *, model: str, messages: list[dict], temperature: float | None = None) -> str:
        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return completion.choices[0].message.content.strip()

    def parse(self, *, model: str, messages: list[dict], response_format: Any) -> Any:
        completion = self.client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_format,
        )
        return completion.choices[0].message.parsed 
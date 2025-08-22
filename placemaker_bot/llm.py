from typing import Any, Dict
from openai import OpenAI
import boto3
import json

from .config import settings


class LLMClient:
    def __init__(self, api_key: str | None = None):
        self.provider = getattr(settings, 'llm_provider', 'openai').lower()
        self.chat_model = getattr(settings, 'llm_chat_model', 'gpt-4.1-nano')
        self.parse_model = getattr(settings, 'llm_parse_model', 'gpt-4.1-nano')
        
        if self.provider == 'openai':
            self.client = OpenAI(api_key=api_key or settings.openai_api_key)
        elif self.provider == 'bedrock':
            # Initialize AWS Bedrock client
            self.bedrock_client = boto3.client(
                'bedrock-runtime',
                region_name=getattr(settings, 'aws_region', 'us-east-1'),
                aws_access_key_id=getattr(settings, 'aws_access_key_id', None),
                aws_secret_access_key=getattr(settings, 'aws_secret_access_key', None),
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def chat(self, *, model: str | None = None, messages: list[dict], temperature: float | None = None) -> str:
        model = model or self.chat_model
        if self.provider == 'openai':
            return self._openai_chat(model, messages, temperature)
        elif self.provider == 'bedrock':
            return self._bedrock_chat(model, messages, temperature)
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    def parse(self, *, model: str | None = None, messages: list[dict], response_format: Any) -> Any:
        model = model or self.parse_model
        if self.provider == 'openai':
            return self._openai_parse(model, messages, response_format)
        elif self.provider == 'bedrock':
            raw = self._bedrock_parse(model, messages, response_format)
            # Try to coerce into the provided Pydantic model class when possible
            try:
                # Pydantic v2: model_validate / model_validate_json
                if hasattr(response_format, 'model_validate'):
                    if isinstance(raw, str):
                        return response_format.model_validate_json(raw)
                    return response_format.model_validate(raw)
            except Exception:
                pass
            return raw
        else:
            raise ValueError(f"Unsupported LLM provider: {self.provider}")

    # --- OpenAI ---
    def _openai_chat(self, model: str, messages: list[dict], temperature: float | None = None) -> str:
        completion = self.client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return completion.choices[0].message.content.strip()

    def _openai_parse(self, model: str, messages: list[dict], response_format: Any) -> Any:
        completion = self.client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_format,
        )
        return completion.choices[0].message.parsed

    # --- Bedrock (Claude) ---
    def _bedrock_chat(self, model: str, messages: list[dict], temperature: float | None = None) -> str:
        claude_messages = self._convert_to_claude_format(messages)
        request_body: Dict[str, Any] = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": claude_messages,
        }
        if temperature is not None:
            request_body["temperature"] = float(temperature)
        response = self.bedrock_client.invoke_model(
            modelId=model,
            body=json.dumps(request_body)
        )
        response_body = json.loads(response.get('body').read())
        return response_body['content'][0]['text'].strip()

    def _bedrock_parse(self, model: str, messages: list[dict], response_format: Any) -> Any:
        # For Bedrock, parse is emulated by returning raw text; caller should expect dict or text.
        raw = self._bedrock_chat(model=model, messages=messages, temperature=0)
        # Attempt JSON load for convenience; otherwise return raw text
        try:
            cleaned = raw.strip()
            if cleaned.startswith('```json'):
                cleaned = cleaned[7:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            return json.loads(cleaned)
        except Exception:
            return raw

    def _convert_to_claude_format(self, messages: list[dict]) -> list[dict]:
        claude_messages: list[dict] = []
        for msg in messages:
            role = msg.get('role')
            content = msg.get('content', '')
            if role == 'system':
                # Prepend system instruction to first user message
                if claude_messages and claude_messages[0].get('role') == 'user':
                    claude_messages[0]['content'] = f"{content}\n\n{claude_messages[0]['content']}"
                else:
                    claude_messages.append({'role': 'user', 'content': content})
            else:
                claude_messages.append({'role': role, 'content': content})
        return claude_messages 
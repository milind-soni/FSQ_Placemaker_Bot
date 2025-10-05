from typing import Any
import json
from litellm import completion

from .config import settings


class LLMClient:
    """
    Unified LLM client using litellm
    
    Configure by setting the appropriate API key environment variable:
    - OpenAI: OPENAI_API_KEY
    - Anthropic: ANTHROPIC_API_KEY
    - Azure: AZURE_API_KEY
    - AWS Bedrock: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME
    - etc.
    
    See https://docs.litellm.ai/docs/providers for full provider list.
    """
    
    def __init__(self, api_key: str | None = None):
        self.chat_model = settings.llm_chat_model
        self.parse_model = settings.llm_parse_model
        self.api_key = api_key  # Optional override, litellm will use env vars by default
        
    def chat(
        self, 
        *, 
        model: str | None = None, 
        messages: list[dict], 
        temperature: float | None = None
    ) -> str:
        """
        Send a chat completion request.
        
        Args:
            model: Model name (e.g., 'gpt-4.1-nano', 'claude-4-5-sonnet')
            messages: List of message dicts with 'role' and 'content'
            temperature: Sampling temperature (0.0 to 2.0)
            
        Returns:
            The text response from the model
        """
        model = model or self.chat_model
        
        kwargs = {
            "model": model,
            "messages": messages,
        }
        
        if temperature is not None:
            kwargs["temperature"] = temperature
            
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        response = completion(**kwargs)
        return response.choices[0].message.content.strip()
    
    def parse(
        self, 
        *, 
        model: str | None = None, 
        messages: list[dict], 
        response_format: Any
    ) -> Any:
        """
        Send a chat completion request with structured output.
        
        Args:
            model: Model name
            messages: List of message dicts with 'role' and 'content'
            response_format: Pydantic model class for structured output
            
        Returns:
            Parsed response as an instance of the response_format class
        """
        model = model or self.parse_model
        
        # Convert Pydantic model to JSON schema for litellm
        if hasattr(response_format, 'model_json_schema'):
            # Pydantic v2
            schema = response_format.model_json_schema()
        elif hasattr(response_format, 'schema'):
            # Pydantic v1
            schema = response_format.schema()
        else:
            raise ValueError(f"response_format must be a Pydantic model, got {type(response_format)}")
        
        kwargs = {
            "model": model,
            "messages": messages,
            "response_format": {
                "type": "json_object",
                "schema": schema
            },
        }
        
        if self.api_key:
            kwargs["api_key"] = self.api_key
        
        try:
            response = completion(**kwargs)
            content = response.choices[0].message.content.strip()
            
            # Parse the JSON response
            try:
                data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                data = json.loads(content.strip())
            
            # Convert to Pydantic model
            if hasattr(response_format, 'model_validate'):
                # Pydantic v2
                return response_format.model_validate(data)
            else:
                # Pydantic v1
                return response_format.parse_obj(data)
                
        except Exception as e:
            # Fallback: try without strict JSON schema
            kwargs.pop("response_format", None)
            
            # Add instruction to return JSON
            last_message = messages[-1]
            if last_message.get('role') == 'user':
                messages[-1]['content'] = f"{last_message['content']}\n\nPlease respond with valid JSON matching this schema: {json.dumps(schema)}"
            
            response = completion(**kwargs)
            content = response.choices[0].message.content.strip()
            
            # Try to parse and validate
            try:
                if content.startswith('```json'):
                    content = content[7:]
                if content.endswith('```'):
                    content = content[:-3]
                data = json.loads(content.strip())
                
                if hasattr(response_format, 'model_validate'):
                    return response_format.model_validate(data)
                else:
                    return response_format.parse_obj(data)
            except Exception:
                raise ValueError(f"Failed to parse LLM response into {response_format.__name__}: {content}")

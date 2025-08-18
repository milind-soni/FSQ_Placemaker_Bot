"""
OpenAI API client for PlacePilot.
Provides structured interface to OpenAI APIs with error handling and retry logic.
"""

import asyncio
from typing import Dict, Any, Optional, List, Union
from datetime import datetime
import json

from openai import AsyncOpenAI
from openai.types.chat import ChatCompletion
from pydantic import BaseModel

from ..core.config import settings
from ..core.logging import get_logger, LoggerMixin
from ..core.exceptions import OpenAIAPIError

logger = get_logger(__name__)


class OpenAIClient(LoggerMixin):
    """Async OpenAI client with error handling and retries."""
    
    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.api.openai_api_key)
        self._default_model = "gpt-4.1-nano"
        self._max_retries = 3
        self._retry_delay = 1.0
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        response_format: Optional[BaseModel] = None,
        **kwargs
    ) -> Union[ChatCompletion, BaseModel]:
        """Create a chat completion with retry logic."""
        
        model = model or self._default_model
        
        request_data = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            **kwargs
        }
        
        if max_tokens:
            request_data["max_tokens"] = max_tokens
        
        if response_format:
            request_data["response_format"] = response_format
        
        # Log the request
        self.log_with_context(
            "debug",
            f"OpenAI API request",
            model=model,
            message_count=len(messages),
            temperature=temperature
        )
        
        for attempt in range(self._max_retries + 1):
            try:
                if response_format:
                    # Use structured output
                    completion = await self.client.beta.chat.completions.parse(**request_data)
                    
                    self.log_with_context(
                        "debug",
                        f"OpenAI API structured response received",
                        model=model,
                        attempt=attempt + 1
                    )
                    
                    return completion.choices[0].message.parsed
                else:
                    # Regular completion
                    completion = await self.client.chat.completions.create(**request_data)
                    
                    self.log_with_context(
                        "debug",
                        f"OpenAI API response received",
                        model=model,
                        attempt=attempt + 1,
                        usage=completion.usage.model_dump() if completion.usage else None
                    )
                    
                    return completion
                    
            except Exception as e:
                if attempt == self._max_retries:
                    self.logger.error(f"OpenAI API request failed after {self._max_retries + 1} attempts: {e}")
                    raise OpenAIAPIError(f"OpenAI API request failed: {e}")
                
                self.logger.warning(f"OpenAI API request attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(self._retry_delay * (2 ** attempt))  # Exponential backoff
    
    async def parse_search_query(
        self,
        user_input: str,
        current_params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Parse a natural language search query using GPT."""
        
        from ..models.pydantic_models import PlaceSearchParams
        
        current_params = current_params or {}
        
        system_prompt = """You are a helpful assistant that parses natural language search queries for places.
        Extract the core search keyword and any filters the user provides.
        Only include the essential food or place type in the query field.
        If the user indicates they want to see results now, set search_now to true."""
        
        user_prompt = f"""
        Parse this search query into structured parameters:
        Current parameters: {json.dumps(current_params)}
        User input: {user_input}
        
        Extract:
        - Core search keyword (e.g., 'burger' from 'I want a great burger joint')
        - Filters like open_now, radius, price range, etc.
        - Whether user wants to search now (words like 'search', 'show me', 'done', etc.)
        """
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            result = await self.chat_completion(
                messages=messages,
                model=self._default_model,
                temperature=0.3,
                response_format=PlaceSearchParams
            )
            
            return result.model_dump()
            
        except Exception as e:
            self.logger.error(f"Failed to parse search query: {e}")
            # Fallback to simple parsing
            return {
                "query": user_input.strip(),
                "search_now": any(word in user_input.lower() for word in ["search", "show", "done", "go"]),
                "explanation": f"Fallback parsing due to error: {e}"
            }
    
    async def parse_contact_info(self, user_input: str) -> Dict[str, Any]:
        """Parse contact information from user input."""
        
        from ..models.pydantic_models import ContactInfo
        
        system_prompt = """Parse contact information from user input.
        Extract phone, website, and email. If something isn't provided, use empty string.
        Validate that the input makes sense for contact information."""
        
        user_prompt = f"Parse contact info from: {user_input}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            result = await self.chat_completion(
                messages=messages,
                model=self._default_model,
                temperature=0.1,
                response_format=ContactInfo
            )
            
            return result.model_dump()
            
        except Exception as e:
            self.logger.error(f"Failed to parse contact info: {e}")
            return {
                "is_valid": False,
                "phone": "",
                "website": "",
                "email": "",
                "explanation": f"Parsing failed: {e}"
            }
    
    async def parse_hours_info(self, user_input: str) -> Dict[str, Any]:
        """Parse operating hours from user input."""
        
        system_prompt = """Parse operating hours from free text input.
        Normalize to a consistent format like "Mon-Fri 9:00 AM - 6:00 PM".
        If the input is ambiguous or invalid, set is_valid to false."""
        
        user_prompt = f"Parse and normalize these hours: {user_input}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        try:
            # For hours parsing, we'll use regular completion since we need flexible JSON
            completion = await self.chat_completion(
                messages=messages,
                model=self._default_model,
                temperature=0.1,
                max_tokens=200
            )
            
            response_text = completion.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                return json.loads(response_text)
            except json.JSONDecodeError:
                # If not valid JSON, return a fallback response
                return {
                    "is_valid": False,
                    "normalized_hours": "",
                    "explanation": "Could not parse hours format"
                }
                
        except Exception as e:
            self.logger.error(f"Failed to parse hours info: {e}")
            return {
                "is_valid": False,
                "normalized_hours": "",
                "explanation": f"Parsing failed: {e}"
            }
    
    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        context: Optional[Dict[str, Any]] = None,
        temperature: float = 0.7
    ) -> str:
        """Generate a conversational response."""
        
        try:
            completion = await self.chat_completion(
                messages=messages,
                temperature=temperature,
                max_tokens=500
            )
            
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            self.logger.error(f"Failed to generate response: {e}")
            return "I'm having trouble processing your request right now. Please try again."
    
    async def classify_intent(self, user_message: str, possible_intents: List[str]) -> str:
        """Classify user intent from a list of possibilities."""
        
        system_prompt = f"""Classify the user's message into one of these intents: {', '.join(possible_intents)}
        Respond with only the intent name, nothing else."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        try:
            completion = await self.chat_completion(
                messages=messages,
                temperature=0.1,
                max_tokens=50
            )
            
            intent = completion.choices[0].message.content.strip().lower()
            
            # Validate intent is in the list
            for possible in possible_intents:
                if possible.lower() in intent:
                    return possible
            
            # Default to first intent if no match
            return possible_intents[0]
            
        except Exception as e:
            self.logger.error(f"Failed to classify intent: {e}")
            return possible_intents[0]  # Default to first option
    
    async def check_health(self) -> bool:
        """Check if OpenAI API is healthy."""
        try:
            messages = [{"role": "user", "content": "Hello"}]
            await self.chat_completion(messages, max_tokens=5)
            return True
        except Exception as e:
            self.logger.error(f"OpenAI health check failed: {e}")
            return False


# Global OpenAI client instance
openai_client = OpenAIClient() 
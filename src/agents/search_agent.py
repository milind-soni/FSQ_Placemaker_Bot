"""
Search Agent for PlacePilot.
Handles location discovery and place searches using Foursquare API.
"""

from typing import Dict, Any, Optional, List
import json
import base64

from .base_agent import BaseAgent
from ..models.pydantic_models import (
    AgentRequest, AgentResponse, AgentType, ConversationState,
    PlaceSearchParams, Place, Location
)
from ..core.exceptions import SearchAgentError
from ..integrations.openai_client import openai_client
from ..integrations.foursquare_client import foursquare_client


class SearchAgent(BaseAgent):
    """
    Search agent that handles place discovery and location-based queries.
    Integrates with Foursquare API for comprehensive place data.
    """
    
    def __init__(self):
        super().__init__(AgentType.SEARCH, "SearchAgent")
        self.default_radius = 1000  # meters
        self.max_results = 20
        
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process search requests and return place results."""
        
        try:
            self.validate_request(request)
            session_id = self.start_session(request.conversation_id)
            
            self.log_with_context(
                "info",
                "Processing search request",
                user_id=request.user_id,
                conversation_id=request.conversation_id
            )
            
            # Extract user location from context
            user_location = self._extract_user_location(request)
            if not user_location:
                return self._request_location_response()
            
            # Parse search query using AI
            search_params = await self._parse_search_query(request)
            
            # Perform Foursquare search
            places = await self._search_places(user_location, search_params)
            
            # Format response
            if not places:
                return self._no_results_response(search_params)
            
            # Create rich response with places
            response = await self._create_search_response(places, search_params, user_location)
            
            self.log_with_context(
                "info",
                "Search completed successfully",
                user_id=request.user_id,
                results_count=len(places),
                query=search_params.get("query", "")
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Search agent error: {e}")
            return await self.handle_error(e, request)
        finally:
            self.end_session()
    
    async def can_handle(self, request: AgentRequest) -> bool:
        """Check if this agent can handle the request."""
        
        message = request.message.lower()
        context = request.context or {}
        
        # Check for search-related keywords
        search_keywords = [
            "find", "search", "show me", "where", "locate", "places",
            "near", "nearby", "around", "close"
        ]
        
        # Check for location-based context
        has_location = "latitude" in context and "longitude" in context
        
        # Can handle if search keywords present or user has location context
        return any(keyword in message for keyword in search_keywords) or has_location
    
    def _extract_user_location(self, request: AgentRequest) -> Optional[Location]:
        """Extract user location from request context."""
        
        context = request.context or {}
        
        lat = context.get("latitude")
        lng = context.get("longitude")
        
        if lat is not None and lng is not None:
            try:
                return Location(latitude=float(lat), longitude=float(lng))
            except (ValueError, TypeError) as e:
                self.logger.warning(f"Invalid location coordinates: {e}")
        
        return None
    
    async def _parse_search_query(self, request: AgentRequest) -> Dict[str, Any]:
        """Parse user's search query into structured parameters."""
        
        # Get current search parameters from context
        context = request.context or {}
        current_params = context.get("search_params", {})
        
        try:
            # Use OpenAI client to parse the query
            parsed_params = await openai_client.parse_search_query(
                user_input=request.message,
                current_params=current_params
            )
            
            self.log_with_context(
                "debug",
                "Search query parsed",
                query=parsed_params.get("query", ""),
                filters_count=len([k for k, v in parsed_params.items() if v is not None and k != "query"])
            )
            
            return parsed_params
            
        except Exception as e:
            self.logger.error(f"Failed to parse search query: {e}")
            
            # Fallback to simple parsing
            return {
                "query": request.message.strip(),
                "search_now": True,
                "explanation": f"Simple parsing used due to error: {e}"
            }
    
    async def _search_places(
        self, 
        location: Location, 
        search_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Perform place search using Foursquare API."""
        
        try:
            # Prepare search parameters
            search_kwargs = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "query": search_params.get("query"),
                "radius": search_params.get("radius", self.default_radius),
                "limit": search_params.get("limit", 5),
                "open_now": search_params.get("open_now"),
                "min_price": search_params.get("min_price"),
                "max_price": search_params.get("max_price"),
                "categories": search_params.get("fsq_category_ids")
            }
            
            # Remove None values
            search_kwargs = {k: v for k, v in search_kwargs.items() if v is not None}
            
            # Perform search
            response = await foursquare_client.search_places(**search_kwargs)
            places = response.get("results", [])
            
            # Enrich with photos
            if places:
                places = await foursquare_client.enrich_places_with_photos(places)
            
            return places
            
        except Exception as e:
            self.logger.error(f"Foursquare search failed: {e}")
            raise SearchAgentError(f"Place search failed: {e}")
    
    def _request_location_response(self) -> AgentResponse:
        """Create response requesting user location."""
        
        response_text = """📍 **Location Required**

To find places near you, I need to know your location. Please:

1. **Share your location** using the location button, or
2. **Tell me a specific area** like "restaurants in downtown Seattle"

Your location is only used to find relevant places and is not stored."""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.LOCATION.value,
                "location_required": True
            },
            actions=[
                {
                    "type": "request_location",
                    "text": "Share Location 📍"
                }
            ]
        )
    
    def _no_results_response(self, search_params: Dict[str, Any]) -> AgentResponse:
        """Create response when no places are found."""
        
        query = search_params.get("query", "places")
        
        response_text = f"""🔍 **No Results Found**

I couldn't find any {query} matching your criteria. 

**Try adjusting your search:**
• Expand the search radius
• Remove some filters
• Try different keywords
• Check the spelling

Would you like to try a different search?"""

        return self.create_response(
            response_text=response_text,
            confidence=0.8,
            context_updates={
                "conversation_state": ConversationState.REFINE.value,
                "last_search_params": search_params,
                "no_results": True
            }
        )
    
    async def _create_search_response(
        self, 
        places: List[Dict[str, Any]], 
        search_params: Dict[str, Any],
        user_location: Location
    ) -> AgentResponse:
        """Create rich response with search results."""
        
        # Generate dynamic header using AI
        header = await self._generate_results_header(search_params, len(places))
        
        # Format place results
        formatted_places = []
        for place in places[:self.max_results]:
            formatted_place = self._format_place_result(place)
            formatted_places.append(formatted_place)
        
        # Create text response
        response_lines = [header, ""]
        
        for i, place in enumerate(formatted_places, 1):
            place_text = self._format_place_text(place, i)
            response_lines.append(place_text)
            response_lines.append("")
        
        # Add refinement suggestion
        response_lines.append("💡 Want to refine your search? Just tell me what you're looking for!")
        
        response_text = "\n".join(response_lines)
        
        # Create web app data for list view
        webapp_data = self._create_webapp_data(formatted_places)
        
        return self.create_response(
            response_text=response_text,
            confidence=0.9,
            next_agent=AgentType.RECOMMENDATION,  # Suggest moving to recommendations
            context_updates={
                "conversation_state": ConversationState.REFINE.value,
                "search_results": formatted_places,
                "search_params": search_params,
                "results_count": len(places)
            },
            actions=[
                {
                    "type": "show_webapp",
                    "url": webapp_data["url"],
                    "text": "Open List View 📱"
                },
                {
                    "type": "suggest_refinement",
                    "text": "Refine Search 🔍"
                }
            ]
        )
    
    async def _generate_results_header(
        self, 
        search_params: Dict[str, Any], 
        results_count: int
    ) -> str:
        """Generate dynamic header for search results."""
        
        query = search_params.get("query", "places")
        
        system_prompt = """Generate a friendly, engaging one-line header for search results.
        Make it specific to the search query and conversational. Don't use emojis."""
        
        user_prompt = f"""
        Search query: {query}
        Number of results: {results_count}
        
        Create a catchy header that introduces the results naturally.
        """
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            completion = await openai_client.chat_completion(
                messages=messages,
                temperature=0.8,
                max_tokens=100
            )
            
            header = completion.choices[0].message.content.strip()
            return f"🎯 {header}"
            
        except Exception as e:
            self.logger.warning(f"Failed to generate header: {e}")
            return f"🎯 Found {results_count} {query} for you:"
    
    def _format_place_result(self, place: Dict[str, Any]) -> Dict[str, Any]:
        """Format a place result into standardized structure."""
        
        return {
            "fsq_place_id": place.get("fsq_place_id"),
            "name": place.get("name", "Unknown Place"),
            "distance": place.get("distance"),
            "rating": place.get("rating"),
            "price": place.get("price"),
            "hours": place.get("hours", {}),
            "image_url": place.get("image_url"),
            "categories": [cat.get("name", "") for cat in place.get("categories", [])]
        }
    
    def _format_place_text(self, place: Dict[str, Any], index: int) -> str:
        """Format place data into readable text."""
        
        name = place["name"]
        distance = place.get("distance")
        rating = place.get("rating")
        price = place.get("price")
        hours = place.get("hours", {})
        
        # Distance
        distance_str = f"{distance}m away" if distance else "Distance unknown"
        
        # Rating
        rating_str = f"{rating}/10 ⭐" if rating else "No rating"
        
        # Price
        price_str = "$" * int(price) if price else "Price unknown"
        
        # Open status
        open_now = hours.get("open_now")
        if open_now is True:
            status_str = "🟢 Open now"
        elif open_now is False:
            status_str = "🔴 Closed"
        else:
            status_str = "⚪ Hours unknown"
        
        return f"""**{index}. {name}**
📍 {distance_str} • ⭐ {rating_str} • 💰 {price_str}
{status_str}"""
    
    def _create_webapp_data(self, places: List[Dict[str, Any]]) -> Dict[str, str]:
        """Create data for the web app list view."""
        
        try:
            # Serialize places data
            places_json = json.dumps(places)
            places_b64 = base64.urlsafe_b64encode(places_json.encode()).decode()
            
            # Create webapp URL (using the existing webapp endpoint)
            webapp_url = f"http://localhost:8000/webapp/?data={places_b64}"
            
            return {
                "url": webapp_url,
                "data": places_b64
            }
            
        except Exception as e:
            self.logger.warning(f"Failed to create webapp data: {e}")
            return {
                "url": "http://localhost:8000/webapp/",
                "data": ""
            } 
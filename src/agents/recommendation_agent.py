"""
Recommendation Agent for PlacePilot.
Processes natural language queries for personalized place suggestions.
"""

from typing import Dict, Any, Optional, List
import json

from .base_agent import BaseAgent
from ..models.pydantic_models import (
    AgentRequest, AgentResponse, AgentType, ConversationState,
    Location
)
from ..core.exceptions import RecommendationAgentError
from ..integrations.openai_client import openai_client
from ..integrations.foursquare_client import foursquare_client


class RecommendationAgent(BaseAgent):
    """
    Recommendation agent that provides personalized place suggestions
    based on user preferences, context, and conversation history.
    """
    
    def __init__(self):
        super().__init__(AgentType.RECOMMENDATION, "RecommendationAgent")
        self.preference_categories = [
            "cuisine_type", "price_range", "ambiance", "group_size", 
            "occasion", "dietary_restrictions", "distance_preference"
        ]
        
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process recommendation requests with personalized suggestions."""
        
        try:
            self.validate_request(request)
            session_id = self.start_session(request.conversation_id)
            
            self.log_with_context(
                "info",
                "Processing recommendation request",
                user_id=request.user_id,
                conversation_id=request.conversation_id
            )
            
            # Extract user location
            user_location = self._extract_user_location(request)
            if not user_location:
                return self._request_location_response()
            
            # Analyze user preferences from message
            preferences = await self._analyze_user_preferences(request)
            
            # Get personalized recommendations
            recommendations = await self._get_recommendations(
                user_location, preferences, request
            )
            
            if not recommendations:
                return self._no_recommendations_response(preferences)
            
            # Create personalized response
            response = await self._create_recommendation_response(
                recommendations, preferences, request
            )
            
            self.log_with_context(
                "info",
                "Recommendations generated successfully",
                user_id=request.user_id,
                recommendations_count=len(recommendations),
                preferences_detected=len(preferences)
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Recommendation agent error: {e}")
            return await self.handle_error(e, request)
        finally:
            self.end_session()
    
    async def can_handle(self, request: AgentRequest) -> bool:
        """Check if this agent can handle the request."""
        
        message = request.message.lower()
        
        # Recommendation-specific keywords
        recommendation_keywords = [
            "recommend", "suggest", "best", "good", "great", "top",
            "craving", "want", "looking for", "in the mood for",
            "favorite", "popular", "highly rated", "what should i",
            "where should i", "help me find", "advice"
        ]
        
        # Preference-related keywords
        preference_keywords = [
            "cheap", "expensive", "fancy", "casual", "romantic",
            "family-friendly", "quiet", "lively", "vegetarian", "vegan",
            "gluten-free", "spicy", "authentic", "local"
        ]
        
        # Check for recommendation or preference keywords
        has_recommendation_intent = any(keyword in message for keyword in recommendation_keywords)
        has_preferences = any(keyword in message for keyword in preference_keywords)
        
        return has_recommendation_intent or has_preferences
    
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
    
    async def _analyze_user_preferences(self, request: AgentRequest) -> Dict[str, Any]:
        """Analyze user message to extract preferences and context."""
        
        system_prompt = """
        Analyze the user's message to extract their preferences for place recommendations.
        
        Extract information about:
        - cuisine_type: What type of food/place (e.g., "Italian", "coffee", "burger")
        - price_range: Budget preference ("cheap", "expensive", "mid-range", or 1-4 scale)
        - ambiance: Atmosphere preference ("casual", "formal", "romantic", "family-friendly")
        - occasion: Context ("date", "business meeting", "family dinner", "quick bite")
        - dietary_restrictions: Special requirements ("vegetarian", "vegan", "gluten-free")
        - group_size: Number of people ("solo", "couple", "group", "family")
        - distance_preference: How far willing to travel ("nearby", "walking distance", "any")
        - specific_requirements: Any other specific needs or wants
        
        Return JSON with extracted preferences. Use null for missing information.
        """
        
        user_prompt = f"""
        User message: "{request.message}"
        
        Context from conversation: {json.dumps(request.context or {}, indent=2)}
        
        Extract user preferences for personalized recommendations.
        """
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            completion = await openai_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=300
            )
            
            response_text = completion.choices[0].message.content.strip()
            
            # Try to parse as JSON
            try:
                preferences = json.loads(response_text)
            except json.JSONDecodeError:
                # If not valid JSON, create simple preferences
                preferences = {
                    "cuisine_type": self._extract_cuisine_from_text(request.message),
                    "general_query": request.message.strip()
                }
            
            # Filter out null values
            preferences = {k: v for k, v in preferences.items() if v is not None}
            
            self.log_with_context(
                "debug",
                "Preferences extracted",
                preferences_count=len(preferences),
                has_cuisine=bool(preferences.get("cuisine_type")),
                has_price_range=bool(preferences.get("price_range"))
            )
            
            return preferences
            
        except Exception as e:
            self.logger.warning(f"Preference analysis failed: {e}")
            return {
                "general_query": request.message.strip(),
                "error": f"Analysis failed: {e}"
            }
    
    def _extract_cuisine_from_text(self, text: str) -> Optional[str]:
        """Simple fallback to extract cuisine type from text."""
        
        text = text.lower()
        
        cuisines = {
            "pizza": "pizza", "burger": "burger", "sushi": "japanese",
            "coffee": "coffee", "italian": "italian", "chinese": "chinese",
            "mexican": "mexican", "thai": "thai", "indian": "indian",
            "french": "french", "american": "american", "breakfast": "breakfast"
        }
        
        for keyword, cuisine in cuisines.items():
            if keyword in text:
                return cuisine
        
        return None
    
    async def _get_recommendations(
        self, 
        location: Location, 
        preferences: Dict[str, Any],
        request: AgentRequest
    ) -> List[Dict[str, Any]]:
        """Get personalized recommendations based on preferences."""
        
        try:
            # Convert preferences to Foursquare search parameters
            search_params = self._preferences_to_search_params(preferences)
            
            # Perform search with preference-based parameters
            search_kwargs = {
                "latitude": location.latitude,
                "longitude": location.longitude,
                "limit": 8,  # Get more results for better recommendations
                **search_params
            }
            
            # Remove None values
            search_kwargs = {k: v for k, v in search_kwargs.items() if v is not None}
            
            self.log_with_context(
                "debug",
                "Searching for recommendations",
                search_params=search_params
            )
            
            # Get places from Foursquare
            response = await foursquare_client.search_places(**search_kwargs)
            places = response.get("results", [])
            
            if not places:
                return []
            
            # Enrich with photos
            places = await foursquare_client.enrich_places_with_photos(places)
            
            # Apply AI-based ranking for better recommendations
            ranked_places = await self._rank_recommendations(places, preferences, request)
            
            return ranked_places[:5]  # Return top 5 recommendations
            
        except Exception as e:
            self.logger.error(f"Failed to get recommendations: {e}")
            raise RecommendationAgentError(f"Recommendation generation failed: {e}")
    
    def _preferences_to_search_params(self, preferences: Dict[str, Any]) -> Dict[str, Any]:
        """Convert user preferences to Foursquare search parameters."""
        
        params = {}
        
        # Cuisine/query mapping
        cuisine_type = preferences.get("cuisine_type")
        general_query = preferences.get("general_query", "")
        
        if cuisine_type:
            params["query"] = cuisine_type
        elif general_query:
            # Extract searchable terms from general query
            params["query"] = self._extract_search_terms(general_query)
        
        # Price range mapping
        price_range = preferences.get("price_range")
        if price_range:
            if price_range in ["cheap", "budget", "inexpensive"]:
                params["max_price"] = 2
            elif price_range in ["expensive", "upscale", "fancy"]:
                params["min_price"] = 3
            elif price_range == "mid-range":
                params["min_price"] = 2
                params["max_price"] = 3
        
        # Distance preference
        distance_pref = preferences.get("distance_preference")
        if distance_pref in ["nearby", "close", "walking distance"]:
            params["radius"] = 500
        elif distance_pref in ["any", "anywhere"]:
            params["radius"] = 5000
        else:
            params["radius"] = 1000  # Default
        
        return params
    
    def _extract_search_terms(self, text: str) -> str:
        """Extract searchable terms from general query text."""
        
        # Simple keyword extraction - remove common words
        stop_words = {
            "i", "am", "looking", "for", "want", "need", "find", "me", "a", "an", "the",
            "good", "best", "great", "nice", "recommend", "suggest", "craving",
            "where", "can", "should", "would", "like", "to", "go", "eat"
        }
        
        words = text.lower().split()
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        return " ".join(keywords[:3])  # Use first 3 meaningful words
    
    async def _rank_recommendations(
        self, 
        places: List[Dict[str, Any]], 
        preferences: Dict[str, Any],
        request: AgentRequest
    ) -> List[Dict[str, Any]]:
        """Use AI to rank places based on user preferences."""
        
        try:
            # Create ranking prompt
            system_prompt = """
            You are a local recommendation expert. Rank the given places based on how well 
            they match the user's preferences. Consider factors like:
            - Relevance to preferences
            - Rating and popularity
            - Distance (closer is generally better)
            - Price match to budget preference
            
            Return the places in order of recommendation quality (best first).
            Just return a JSON array of place objects in the new order.
            """
            
            user_prompt = f"""
            User preferences: {json.dumps(preferences)}
            User message: "{request.message}"
            
            Places to rank:
            {json.dumps(places, indent=2)}
            
            Rank these places for the user, best matches first.
            """
            
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            completion = await openai_client.chat_completion(
                messages=messages,
                temperature=0.2,
                max_tokens=2000
            )
            
            response_text = completion.choices[0].message.content.strip()
            
            # Try to parse the ranked results
            try:
                ranked_places = json.loads(response_text)
                if isinstance(ranked_places, list) and len(ranked_places) > 0:
                    return ranked_places
            except json.JSONDecodeError:
                pass
            
            # Fallback to original order
            return places
            
        except Exception as e:
            self.logger.warning(f"AI ranking failed: {e}")
            
            # Simple fallback ranking by rating and distance
            return sorted(
                places, 
                key=lambda p: (
                    -(p.get("rating") or 0),  # Higher rating first
                    p.get("distance") or 9999  # Closer first
                )
            )
    
    async def _create_recommendation_response(
        self, 
        recommendations: List[Dict[str, Any]], 
        preferences: Dict[str, Any],
        request: AgentRequest
    ) -> AgentResponse:
        """Create personalized recommendation response."""
        
        # Generate personalized introduction
        intro = await self._generate_personalized_intro(preferences, request.message)
        
        # Format recommendations
        response_lines = [intro, ""]
        
        for i, place in enumerate(recommendations, 1):
            place_text = self._format_recommendation_text(place, i, preferences)
            response_lines.append(place_text)
            response_lines.append("")
        
        # Add follow-up suggestion
        response_lines.append(self._generate_followup_suggestion(preferences))
        
        response_text = "\n".join(response_lines)
        
        return self.create_response(
            response_text=response_text,
            confidence=0.95,
            context_updates={
                "conversation_state": ConversationState.REFINE.value,
                "recommendations": recommendations,
                "user_preferences": preferences,
                "recommendation_given": True
            },
            actions=[
                {
                    "type": "get_more_details",
                    "text": "Tell me more about any place 🏪"
                },
                {
                    "type": "refine_preferences", 
                    "text": "Different preferences 🔄"
                }
            ]
        )
    
    async def _generate_personalized_intro(
        self, 
        preferences: Dict[str, Any], 
        user_message: str
    ) -> str:
        """Generate personalized introduction to recommendations."""
        
        system_prompt = """
        Create a friendly, personalized introduction for restaurant/place recommendations.
        Reference the user's specific preferences or request. Keep it conversational and brief.
        Don't use emojis in the intro.
        """
        
        user_prompt = f"""
        User said: "{user_message}"
        Detected preferences: {json.dumps(preferences)}
        
        Create a warm introduction that acknowledges their request.
        """
        
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
            
            completion = await openai_client.chat_completion(
                messages=messages,
                temperature=0.7,
                max_tokens=100
            )
            
            intro = completion.choices[0].message.content.strip()
            return f"🎯 {intro}"
            
        except Exception as e:
            self.logger.warning(f"Failed to generate personalized intro: {e}")
            cuisine = preferences.get("cuisine_type", "places")
            return f"🎯 Here are my top recommendations for {cuisine}:"
    
    def _format_recommendation_text(
        self, 
        place: Dict[str, Any], 
        index: int, 
        preferences: Dict[str, Any]
    ) -> str:
        """Format recommendation with personalized reasoning."""
        
        name = place.get("name", "Unknown Place")
        distance = place.get("distance")
        rating = place.get("rating")
        price = place.get("price")
        categories = place.get("categories", [])
        
        # Distance
        distance_str = f"{distance}m away" if distance else "Distance unknown"
        
        # Rating with context
        if rating and rating >= 8:
            rating_str = f"⭐ {rating}/10 (Excellent!)"
        elif rating and rating >= 7:
            rating_str = f"⭐ {rating}/10 (Very good)"
        elif rating:
            rating_str = f"⭐ {rating}/10"
        else:
            rating_str = "⭐ Rating not available"
        
        # Price with context
        if price:
            price_symbols = "$" * int(price)
            price_context = self._get_price_context(price, preferences)
            price_str = f"💰 {price_symbols} {price_context}"
        else:
            price_str = "💰 Price not available"
        
        # Category info
        category_str = f"📍 {categories[0]}" if categories else ""
        
        # Why recommended (simple logic)
        reason = self._get_recommendation_reason(place, preferences)
        
        return f"""**{index}. {name}**
{rating_str} • {price_str} • {distance_str}
{category_str}
💡 *{reason}*"""
    
    def _get_price_context(self, price: int, preferences: Dict[str, Any]) -> str:
        """Get contextual price description."""
        
        price_pref = preferences.get("price_range", "").lower()
        
        if price == 1:
            return "(Budget-friendly)" if "cheap" in price_pref else "(Very affordable)"
        elif price == 2:
            return "(Good value)" if "cheap" in price_pref else "(Moderate)"
        elif price == 3:
            return "(Upscale)" if "expensive" in price_pref else "(Higher-end)"
        elif price == 4:
            return "(Fine dining)" if "expensive" in price_pref else "(Premium)"
        
        return ""
    
    def _get_recommendation_reason(
        self, 
        place: Dict[str, Any], 
        preferences: Dict[str, Any]
    ) -> str:
        """Generate simple reason for recommendation."""
        
        reasons = []
        
        # High rating
        if place.get("rating", 0) >= 8:
            reasons.append("highly rated")
        
        # Close distance  
        if place.get("distance", 9999) <= 500:
            reasons.append("nearby")
        
        # Price match
        price_pref = preferences.get("price_range", "").lower()
        place_price = place.get("price")
        if price_pref and place_price:
            if "cheap" in price_pref and place_price <= 2:
                reasons.append("budget-friendly")
            elif "expensive" in price_pref and place_price >= 3:
                reasons.append("upscale option")
        
        # Cuisine match
        cuisine_pref = preferences.get("cuisine_type")
        categories = [cat.lower() for cat in place.get("categories", [])]
        if cuisine_pref and any(cuisine_pref.lower() in cat for cat in categories):
            reasons.append("matches your taste")
        
        if not reasons:
            reasons.append("good option for you")
        
        return ", ".join(reasons[:2])  # Max 2 reasons
    
    def _generate_followup_suggestion(self, preferences: Dict[str, Any]) -> str:
        """Generate follow-up suggestion based on preferences."""
        
        suggestions = [
            "💬 Want more details about any of these places?",
            "🔄 Need different options? Just tell me what you'd prefer!",
            "📱 I can also show you these in an interactive map view."
        ]
        
        # Customize based on preferences
        if preferences.get("price_range"):
            suggestions.insert(0, "💰 Want options in a different price range?")
        
        if preferences.get("cuisine_type"):
            suggestions.insert(0, "🍽️ Interested in other types of cuisine?")
        
        return suggestions[0]  # Return the most relevant suggestion
    
    def _request_location_response(self) -> AgentResponse:
        """Create response requesting user location."""
        
        response_text = """📍 **Location Needed for Recommendations**

I'd love to give you personalized recommendations! Please share your location so I can find the best places near you.

Your location helps me suggest places that are:
• Actually accessible to you
• Highly rated in your area  
• Within reasonable distance

Your location is only used for recommendations and is not stored."""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.LOCATION.value,
                "recommendation_pending": True
            },
            actions=[
                {
                    "type": "request_location",
                    "text": "Share Location 📍"
                }
            ]
        )
    
    def _no_recommendations_response(self, preferences: Dict[str, Any]) -> AgentResponse:
        """Create response when no recommendations can be generated."""
        
        response_text = """🤔 **No Recommendations Found**

I couldn't find places that match your preferences in this area.

**Let's try something different:**
• Expand the search area
• Try different cuisine types
• Adjust your budget range
• Tell me more about what you're looking for

What would you like to adjust?"""

        return self.create_response(
            response_text=response_text,
            confidence=0.6,
            context_updates={
                "conversation_state": ConversationState.REFINE.value,
                "no_recommendations": True,
                "failed_preferences": preferences
            }
        ) 
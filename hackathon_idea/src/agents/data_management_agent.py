"""
Data Management Agent for PlacePilot.
Manages user contributions, place data validation, and database updates.
"""

from typing import Dict, Any, Optional, List
import json

from .base_agent import StatefulAgent
from ..models.pydantic_models import (
    AgentRequest, AgentResponse, AgentType, ConversationState,
    PlaceContribution, Location
)
from ..core.exceptions import DataManagementAgentError
from ..integrations.openai_client import openai_client


class DataManagementAgent(StatefulAgent):
    """
    Data management agent that handles user contributions to the places database.
    Manages the multi-step process of collecting and validating place information.
    """
    
    def __init__(self):
        super().__init__(AgentType.DATA_MANAGEMENT, "DataManagementAgent")
        self.contribution_steps = [
            "name", "category", "address", "contact", "hours", 
            "attributes", "photos", "confirm"
        ]
        
    async def process_request(self, request: AgentRequest) -> AgentResponse:
        """Process data management requests - contributions and updates."""
        
        try:
            self.validate_request(request)
            session_id = self.start_session(request.conversation_id)
            
            self.log_with_context(
                "info",
                "Processing data management request",
                user_id=request.user_id,
                conversation_id=request.conversation_id
            )
            
            # Get current conversation state
            current_state = self._get_conversation_state(request)
            
            # Route based on state
            if not current_state or current_state == ConversationState.LOCATION_CHOICE:
                # Starting contribution process
                return await self._start_contribution(request)
            elif current_state.value.startswith("contribute_"):
                # Continue contribution process
                return await self._continue_contribution(request, current_state)
            else:
                # Handle general data management requests
                return await self._handle_general_request(request)
                
        except Exception as e:
            self.logger.error(f"Data management agent error: {e}")
            return await self.handle_error(e, request)
        finally:
            self.end_session()
    
    async def can_handle(self, request: AgentRequest) -> bool:
        """Check if this agent can handle the request."""
        
        message = request.message.lower()
        context = request.context or {}
        current_state = context.get("conversation_state")
        
        # Handle contribution flow states
        if current_state and current_state.startswith("contribute_"):
            return True
        
        # Handle contribution-related keywords
        contribution_keywords = [
            "add", "contribute", "new place", "submit", "create",
            "register", "update", "edit", "modify", "report"
        ]
        
        return any(keyword in message for keyword in contribution_keywords)
    
    async def _start_contribution(self, request: AgentRequest) -> AgentResponse:
        """Start the place contribution process."""
        
        # Check if user has location
        user_location = await self._extract_user_location(request)
        if not user_location:
            return await self._request_location_for_contribution(request)
        
        # Initialize contribution data
        contribution_data = {
            "user_id": request.user_id,
            "location": {
                "latitude": user_location.latitude,
                "longitude": user_location.longitude
            },
            "step": "name",
            "data": {}
        }
        
        response_text = """📝 **Add a New Place**

Great! Let's add a new place to help others discover it.

I'll guide you through a few simple steps:

1. **Name** - What's the place called?
2. **Category** - What type of place is it?
3. **Address** - Where is it located?
4. **Contact** - Phone, website, email (optional)
5. **Hours** - When is it open?
6. **Features** - What amenities does it have?
7. **Photos** - Add some pictures (optional)

Let's start! **What's the name of the place?**"""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_NAME.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _continue_contribution(
        self, 
        request: AgentRequest, 
        current_state: ConversationState
    ) -> AgentResponse:
        """Continue the contribution process based on current state."""
        
        # Get contribution data from context
        context = request.context or {}
        contribution_data = context.get("contribution_data", {})
        
        if current_state == ConversationState.CONTRIBUTE_NAME:
            return await self._handle_name_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_CATEGORY:
            return await self._handle_category_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_ADDRESS:
            return await self._handle_address_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_CONTACT:
            return await self._handle_contact_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_HOURS:
            return await self._handle_hours_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_ATTRIBUTES:
            return await self._handle_attributes_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_PHOTOS:
            return await self._handle_photos_step(request, contribution_data)
        elif current_state == ConversationState.CONTRIBUTE_CONFIRM:
            return await self._handle_confirmation_step(request, contribution_data)
        else:
            return self._create_error_response("Unknown contribution state")
    
    async def _handle_name_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle place name input."""
        
        place_name = request.message.strip()
        
        if len(place_name) < 2:
            return self.create_response(
                response_text="Please enter a valid place name (at least 2 characters).",
                confidence=0.5,
                context_updates={"error": "Invalid name length"}
            )
        
        # Update contribution data
        contribution_data["data"]["name"] = place_name
        contribution_data["step"] = "category"
        
        response_text = f"""✅ **Name**: {place_name}

**What type of place is this?**

Common categories:
• 🍽️ Restaurant
• ☕ Coffee Shop  
• 🛍️ Retail Store
• 🏨 Hotel
• 💄 Beauty Salon
• 🏥 Healthcare
• 🎭 Entertainment
• 🔧 Service

Just type the category or choose from above!"""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_CATEGORY.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_category_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle place category input."""
        
        category = request.message.strip()
        
        # Clean up category (remove emojis, normalize)
        category = self._normalize_category(category)
        
        # Update contribution data
        contribution_data["data"]["category"] = category
        contribution_data["step"] = "address"
        
        response_text = f"""✅ **Category**: {category}

**What's the address of this place?**

Please provide the full address including:
• Street address
• City
• State/Province (if applicable)
• Country

Example: "123 Main Street, Seattle, WA, USA" """

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_ADDRESS.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_address_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle address input."""
        
        address = request.message.strip()
        
        if len(address) < 10:
            return self.create_response(
                response_text="Please provide a more complete address (at least 10 characters).",
                confidence=0.5
            )
        
        # Update contribution data
        contribution_data["data"]["address"] = address
        contribution_data["step"] = "contact"
        
        response_text = f"""✅ **Address**: {address}

**Contact Information** (Optional)

Please provide contact details if available:
• Phone number
• Website  
• Email address

Format: "Phone: +1234567890, Website: www.example.com, Email: info@example.com"

Or type **"skip"** to continue without contact info."""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_CONTACT.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_contact_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle contact information input."""
        
        user_input = request.message.strip().lower()
        
        if user_input == "skip":
            # Skip contact info
            contribution_data["step"] = "hours"
            return self._ask_for_hours(contribution_data)
        
        # Parse contact information using AI
        try:
            contact_info = await openai_client.parse_contact_info(request.message)
            
            if not contact_info["is_valid"]:
                return self.create_response(
                    response_text=f"""❌ {contact_info['explanation']}

Please try again with format: "Phone: +1234567890, Website: www.example.com, Email: info@example.com"

Or type **"skip"** to continue without contact info.""",
                    confidence=0.6
                )
            
            # Update contribution data
            contribution_data["data"]["contact"] = {
                "phone": contact_info.get("phone", ""),
                "website": contact_info.get("website", ""), 
                "email": contact_info.get("email", "")
            }
            contribution_data["step"] = "hours"
            
            # Show what was parsed
            contact_summary = []
            if contact_info.get("phone"):
                contact_summary.append(f"📞 {contact_info['phone']}")
            if contact_info.get("website"):
                contact_summary.append(f"🌐 {contact_info['website']}")
            if contact_info.get("email"):
                contact_summary.append(f"📧 {contact_info['email']}")
            
            response_text = f"""✅ **Contact Info**: {' • '.join(contact_summary)}

{self._get_hours_prompt()}"""
            
            return self.create_response(
                response_text=response_text,
                confidence=1.0,
                context_updates={
                    "conversation_state": ConversationState.CONTRIBUTE_HOURS.value,
                    "contribution_data": contribution_data
                }
            )
            
        except Exception as e:
            self.logger.error(f"Contact parsing failed: {e}")
            return self.create_response(
                response_text="Sorry, I couldn't parse the contact information. Please try again or type 'skip'.",
                confidence=0.5
            )
    
    async def _handle_hours_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle operating hours input."""
        
        user_input = request.message.strip().lower()
        
        if user_input in ["24/7", "24 hours", "always open"]:
            # 24/7 operation
            contribution_data["data"]["hours"] = "24/7"
            contribution_data["data"]["is_24_7"] = True
            contribution_data["step"] = "attributes"
            
            response_text = f"""✅ **Hours**: Open 24/7

{self._get_attributes_prompt()}"""
            
        else:
            # Parse custom hours using AI
            try:
                hours_info = await openai_client.parse_hours_info(request.message)
                
                if not hours_info["is_valid"]:
                    return self.create_response(
                        response_text=f"""❌ {hours_info['explanation']}

Please try again with format like:
• "Mon-Fri 9AM-6PM"
• "Monday to Saturday 10:00-22:00"
• "24/7" for always open""",
                        confidence=0.6
                    )
                
                # Update contribution data
                contribution_data["data"]["hours"] = hours_info["normalized_hours"]
                contribution_data["data"]["is_24_7"] = False
                contribution_data["step"] = "attributes"
                
                response_text = f"""✅ **Hours**: {hours_info['normalized_hours']}

{self._get_attributes_prompt()}"""
                
            except Exception as e:
                self.logger.error(f"Hours parsing failed: {e}")
                return self.create_response(
                    response_text="Sorry, I couldn't parse the hours. Please try again or use '24/7' for always open.",
                    confidence=0.5
                )
        
        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_ATTRIBUTES.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_attributes_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle place attributes/features input."""
        
        user_input = request.message.strip().lower()
        
        if user_input in ["done", "skip", "none"]:
            # No attributes to add
            contribution_data["step"] = "photos"
            return self._ask_for_photos(contribution_data)
        
        # Parse attributes from text
        attributes = self._parse_attributes(request.message)
        
        # Get existing attributes
        existing_attributes = contribution_data["data"].get("attributes", [])
        existing_attributes.extend(attributes)
        
        contribution_data["data"]["attributes"] = existing_attributes
        
        response_text = f"""✅ **Added features**: {', '.join(attributes)}

Current features: {', '.join(existing_attributes)}

**Add more features or type "done":**"""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_photos_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle photo uploads."""
        
        if request.message.lower().strip() in ["skip", "done", "no photos"]:
            # Skip photos, go to confirmation
            contribution_data["step"] = "confirm"
            return await self._show_confirmation(contribution_data)
        
        # For now, we'll simulate photo handling
        # In real implementation, this would handle Telegram photo uploads
        
        response_text = """📸 **Photos** (Optional)

Photos help others discover this place! You can upload:
• Storefront/entrance
• Interior view  
• Menu or signage
• Special features

**Send photos** or type **"skip"** to continue."""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_PHOTOS.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_confirmation_step(
        self, 
        request: AgentRequest, 
        contribution_data: Dict[str, Any]
    ) -> AgentResponse:
        """Handle final confirmation."""
        
        user_input = request.message.strip().lower()
        
        if user_input in ["yes", "confirm", "submit", "ok"]:
            # Save the contribution
            return await self._save_contribution(contribution_data)
        elif user_input in ["no", "cancel", "edit"]:
            # Cancel or allow editing
            return self.create_response(
                response_text="❌ Contribution cancelled. Type '/start' to begin again or tell me what you'd like to change.",
                confidence=1.0,
                context_updates={
                    "conversation_state": ConversationState.LOCATION_CHOICE.value,
                    "contribution_cancelled": True
                }
            )
        else:
            # Ask for clarification
            return self.create_response(
                response_text="Please confirm by typing 'yes' to submit or 'no' to cancel.",
                confidence=0.7
            )
    
    async def _save_contribution(self, contribution_data: Dict[str, Any]) -> AgentResponse:
        """Save the place contribution to database."""
        
        try:
            # Here you would save to your database
            # For now, we'll simulate success
            
            place_name = contribution_data["data"]["name"]
            
            self.log_with_context(
                "info",
                "Place contribution saved",
                user_id=contribution_data["user_id"],
                place_name=place_name
            )
            
            response_text = f"""🎉 **Contribution Successful!**

Thank you for adding **{place_name}** to our database!

Your contribution helps other users discover great places. It will be reviewed and made available soon.

**What's next?**
• Add another place
• Search for places nearby
• Get recommendations

Type '/start' for the main menu or tell me what you'd like to do!"""

            return self.create_response(
                response_text=response_text,
                confidence=1.0,
                context_updates={
                    "conversation_state": ConversationState.LOCATION_CHOICE.value,
                    "contribution_completed": True,
                    "last_contributed_place": place_name
                }
            )
            
        except Exception as e:
            self.logger.error(f"Failed to save contribution: {e}")
            return self.create_response(
                response_text="❌ Sorry, there was an error saving your contribution. Please try again later.",
                confidence=0.5,
                context_updates={
                    "contribution_error": str(e)
                }
            )
    
    async def _extract_user_location(self, request: AgentRequest) -> Optional[Location]:
        """Extract user location from saved profile or request context."""
        
        # First, try to get saved location from user profile
        try:
            from ..services.user_service import UserService
            user_service = UserService()
            
            saved_location = await user_service.get_user_location(request.user_id)
            if saved_location:
                self.logger.debug(f"Using saved location for user {request.user_id}")
                return Location(
                    latitude=saved_location["latitude"],
                    longitude=saved_location["longitude"]
                )
        except Exception as e:
            self.logger.warning(f"Failed to get saved location: {e}")
        
        # Fallback to context location (for when user just shared location)
        context = request.context or {}
        lat = context.get("latitude")
        lng = context.get("longitude")
        
        if lat is not None and lng is not None:
            try:
                self.logger.debug(f"Using context location for user {request.user_id}")
                return Location(latitude=float(lat), longitude=float(lng))
            except (ValueError, TypeError):
                return None
        
        return None
    
    async def _request_location_for_contribution(self, request: AgentRequest) -> AgentResponse:
        """Request location for place contribution."""
        
        # Check if user has saved location but it might need updating
        from ..services.user_service import UserService
        user_service = UserService()
        
        has_saved_location = await user_service.user_has_location(request.user_id)
        
        if has_saved_location:
            response_text = """📍 **Location Update Needed**

I need a more precise location to add the new place correctly. Please:

1. **Share your current location** for accurate placement, or
2. **Tell me the specific area** where the place is located

Your updated location will be saved for future contributions."""
        else:
            response_text = """📍 **Location Required**

To add a new place, I need to know where you are so I can associate the place with the correct location.

Please share your location or tell me the area where the place is located.

Your location will be saved securely for future contributions."""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.LOCATION.value,
                "contribution_pending": True,
                "has_saved_location": has_saved_location
            },
            actions=[
                {
                    "type": "request_location",
                    "text": "📍 Share Location" if not has_saved_location else "📍 Update Location"
                }
            ]
        )
    
    def _get_conversation_state(self, request: AgentRequest) -> Optional[ConversationState]:
        """Extract conversation state from request context."""
        
        context = request.context or {}
        state_value = context.get("conversation_state")
        
        if state_value:
            try:
                return ConversationState(state_value)
            except ValueError:
                return None
        
        return None
    
    def _normalize_category(self, category: str) -> str:
        """Normalize category input."""
        
        # Remove emojis and common prefixes
        category = category.replace("🍽️", "").replace("☕", "").replace("🛍️", "")
        category = category.replace("Restaurant", "").replace("Coffee Shop", "Coffee")
        category = category.strip()
        
        # Capitalize properly
        return category.title()
    
    def _get_hours_prompt(self) -> str:
        """Get the hours input prompt."""
        
        return """**Operating Hours**

When is this place open?

Examples:
• "Mon-Fri 9AM-6PM"
• "Monday to Saturday 10:00-22:00" 
• "Daily 8AM-10PM"
• "24/7" (always open)

Please enter the hours:"""
    
    def _get_attributes_prompt(self) -> str:
        """Get the attributes input prompt."""
        
        return """**Features & Amenities**

What features does this place have?

Common features:
• WiFi, Parking, Outdoor seating
• Accepts credit cards, Cash only
• Wheelchair accessible
• Pet-friendly, Family-friendly  
• Delivery, Takeout, Reservations

Type features separated by commas, or "skip" to continue:"""
    
    def _parse_attributes(self, text: str) -> List[str]:
        """Parse attributes from text input."""
        
        # Split by common separators
        attributes = []
        
        # Split by commas, semicolons, or 'and'
        parts = text.replace(';', ',').replace(' and ', ',').split(',')
        
        for part in parts:
            attr = part.strip()
            if len(attr) > 2:  # Minimum length check
                attributes.append(attr.title())
        
        return attributes
    
    def _ask_for_hours(self, contribution_data: Dict[str, Any]) -> AgentResponse:
        """Ask for operating hours."""
        
        return self.create_response(
            response_text=self._get_hours_prompt(),
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_HOURS.value,
                "contribution_data": contribution_data
            }
        )
    
    def _ask_for_photos(self, contribution_data: Dict[str, Any]) -> AgentResponse:
        """Ask for photos."""
        
        response_text = """📸 **Photos** (Optional)

Photos help others discover this place! You can upload:
• Storefront/entrance
• Interior view
• Menu or signage

**Send photos** or type **"skip"** to continue."""

        return self.create_response(
            response_text=response_text,
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_PHOTOS.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _show_confirmation(self, contribution_data: Dict[str, Any]) -> AgentResponse:
        """Show contribution summary for confirmation."""
        
        data = contribution_data["data"]
        
        # Build summary
        summary_lines = [
            "📋 **Place Summary**",
            "",
            f"**Name**: {data.get('name', 'N/A')}",
            f"**Category**: {data.get('category', 'N/A')}",
            f"**Address**: {data.get('address', 'N/A')}",
        ]
        
        # Contact info
        contact = data.get("contact", {})
        if any(contact.values()):
            contact_parts = []
            if contact.get("phone"):
                contact_parts.append(f"📞 {contact['phone']}")
            if contact.get("website"):
                contact_parts.append(f"🌐 {contact['website']}")
            if contact.get("email"):
                contact_parts.append(f"📧 {contact['email']}")
            summary_lines.append(f"**Contact**: {' • '.join(contact_parts)}")
        
        # Hours
        hours = data.get("hours", "N/A")
        summary_lines.append(f"**Hours**: {hours}")
        
        # Attributes
        attributes = data.get("attributes", [])
        if attributes:
            summary_lines.append(f"**Features**: {', '.join(attributes)}")
        
        summary_lines.extend([
            "",
            "✅ **Confirm submission?**",
            "",
            "Type **'yes'** to submit or **'no'** to cancel."
        ])
        
        return self.create_response(
            response_text="\n".join(summary_lines),
            confidence=1.0,
            context_updates={
                "conversation_state": ConversationState.CONTRIBUTE_CONFIRM.value,
                "contribution_data": contribution_data
            }
        )
    
    async def _handle_general_request(self, request: AgentRequest) -> AgentResponse:
        """Handle general data management requests."""
        
        message = request.message.lower()
        
        if any(word in message for word in ["add", "contribute", "new place"]):
            return await self._start_contribution(request)
        
        # Default response
        return self.create_response(
            response_text="I can help you add new places to our database. Just say 'add a new place' to get started!",
            confidence=0.8
        )
    
    def _create_error_response(self, error_msg: str) -> AgentResponse:
        """Create error response."""
        
        return self.create_response(
            response_text=f"❌ Error: {error_msg}\n\nPlease try again or type '/start' for the main menu.",
            confidence=0.5
        ) 
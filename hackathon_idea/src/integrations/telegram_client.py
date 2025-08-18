"""
Telegram Bot client for PlacePilot.
Integrates the agent system with Telegram Bot API using webhooks.
"""

import asyncio
import json
import concurrent.futures
from typing import Dict, Any, Optional, List
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.constants import ChatAction, ParseMode

from ..core.config import settings
from ..core.logging import get_logger, LoggerMixin
from ..core.exceptions import TelegramAPIError
from ..models.pydantic_models import AgentRequest, AgentResponse, AgentType, ConversationState
from ..agents import agent_registry
from ..services.user_service import UserService
from ..services.conversation_service import ConversationService

logger = get_logger(__name__)


class TelegramClient(LoggerMixin):
    """
    Telegram bot client that integrates with the PlacePilot agent system.
    Handles webhooks, user interactions, and agent coordination.
    """
    
    def __init__(self):
        self.application = None
        self.user_service = UserService()
        self.conversation_service = ConversationService()
        self.webapp_base_url = "https://your-domain.com"  # Will be configurable
        
    async def initialize(self) -> None:
        """Initialize the Telegram bot application."""
        
        try:
            # Create application
            self.application = (
                Application.builder()
                .token(settings.api.telegram_bot_token)
                .build()
            )
            
            # Register handlers
            self._register_handlers()
            
            # Initialize the application
            await self.application.initialize()
            
            self.logger.info("Telegram client initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize Telegram client: {e}")
            raise TelegramAPIError(f"Telegram initialization failed: {e}")
    
    def _register_handlers(self) -> None:
        """Register all Telegram bot handlers."""
        
        # Command handlers
        self.application.add_handler(CommandHandler("start", self._handle_start))
        self.application.add_handler(CommandHandler("help", self._handle_help))
        self.application.add_handler(CommandHandler("reset", self._handle_reset))
        
        # Message handlers
        self.application.add_handler(MessageHandler(filters.LOCATION, self._handle_location))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message))
        self.application.add_handler(MessageHandler(filters.PHOTO, self._handle_photo))
        
        # Callback query handlers
        self.application.add_handler(CallbackQueryHandler(self._handle_callback_query))
        
        # WebApp data handler
        self.application.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, self._handle_webapp_data))
        
        self.logger.info("Telegram handlers registered")
    
    async def _handle_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            
            self.log_with_context(
                "info", 
                "Start command received",
                user_id=user.id,
                chat_id=chat_id,
                username=user.username
            )
            
            # Ensure user exists in database
            await self.user_service.ensure_user_exists(
                telegram_id=user.id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                language_code=user.language_code
            )
            
            # Create agent request
            agent_request = AgentRequest(
                agent_type=AgentType.SUPERVISOR,
                message="/start",
                user_id=user.id,
                conversation_id=str(chat_id),
                context={}
            )
            
            # Process through agent system
            response = await self._process_agent_request(agent_request)
            
            # Send response to user
            await self._send_agent_response(update, context, response)
            
        except Exception as e:
            self.logger.error(f"Error handling start command: {e}")
            await update.message.reply_text(
                "Sorry, I encountered an error. Please try again or contact support."
            )
    
    async def _handle_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            
            # Create agent request
            agent_request = AgentRequest(
                agent_type=AgentType.SUPERVISOR,
                message="help",
                user_id=user.id,
                conversation_id=str(chat_id),
                context={}
            )
            
            # Process through agent system
            response = await self._process_agent_request(agent_request)
            
            # Send response to user
            await self._send_agent_response(update, context, response)
            
        except Exception as e:
            self.logger.error(f"Error handling help command: {e}")
            await update.message.reply_text(
                "I can help you find places, get recommendations, and add new locations to our database!"
            )
    
    async def _handle_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /reset command to clear conversation state."""
        
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            
            # Clear conversation state
            await self.conversation_service.reset_conversation(str(chat_id))
            
            await update.message.reply_text(
                "🔄 Conversation reset! You can start fresh. Type /start to begin.",
                reply_markup=ReplyKeyboardRemove()
            )
            
        except Exception as e:
            self.logger.error(f"Error handling reset command: {e}")
            await update.message.reply_text("Error resetting conversation. Please try again.")
    
    async def _handle_location(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle location sharing and save to user profile."""
        
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            location = update.message.location
            
            self.log_with_context(
                "info",
                "Location received",
                user_id=user.id,
                latitude=location.latitude,
                longitude=location.longitude
            )
            
            # Save location to user profile (persistent storage)
            from ..services.user_service import UserService
            user_service = UserService()
            
            saved_user = await user_service.update_user_location(
                user.id, location.latitude, location.longitude
            )
            
            if saved_user:
                self.log_with_context(
                    "info",
                    "Location saved to user profile",
                    user_id=user.id
                )
            
            # Get current conversation context
            conversation_context = await self.conversation_service.get_conversation_context(str(chat_id))
            
            # Add location to context
            conversation_context.update({
                "latitude": location.latitude,
                "longitude": location.longitude,
                "location_shared": True,
                "location_saved": saved_user is not None
            })
            
            # Create agent request
            agent_request = AgentRequest(
                agent_type=AgentType.SUPERVISOR,
                message="Location shared and saved",
                user_id=user.id,
                conversation_id=str(chat_id),
                context=conversation_context
            )
            
            # Process through agent system
            response = await self._process_agent_request(agent_request)
            
            # Update conversation context
            await self.conversation_service.update_conversation_context(
                str(chat_id), response.context_updates or {}
            )
            
            # Send response to user
            await self._send_agent_response(update, context, response)
            
        except Exception as e:
            self.logger.error(f"Error handling location: {e}")
            await update.message.reply_text("Error processing your location. Please try again.")
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages."""
        
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            message_text = update.message.text
            
            # Show typing indicator
            await context.bot.send_chat_action(chat_id=chat_id, action=ChatAction.TYPING)
            
            # Get current conversation context
            conversation_context = await self.conversation_service.get_conversation_context(str(chat_id))
            
            self.log_with_context(
                "info",
                "Message received",
                user_id=user.id,
                message_length=len(message_text),
                has_context=bool(conversation_context)
            )
            
            # Create agent request
            agent_request = AgentRequest(
                agent_type=AgentType.SUPERVISOR,
                message=message_text,
                user_id=user.id,
                conversation_id=str(chat_id),
                context=conversation_context
            )
            
            # Process through agent system
            response = await self._process_agent_request(agent_request)
            
            # Update conversation context
            if response.context_updates:
                await self.conversation_service.update_conversation_context(
                    str(chat_id), response.context_updates
                )
            
            # Send response to user
            await self._send_agent_response(update, context, response)
            
        except Exception as e:
            self.logger.error(f"Error handling message: {e}")
            await update.message.reply_text(
                "I'm having trouble processing your message right now. Please try again."
            )
    
    async def _handle_photo(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle photo uploads."""
        
        try:
            user = update.effective_user
            chat_id = update.effective_chat.id
            photo = update.message.photo[-1]  # Get highest resolution
            
            # Get conversation context to check if we're in contribution flow
            conversation_context = await self.conversation_service.get_conversation_context(str(chat_id))
            current_state = conversation_context.get("conversation_state")
            
            if current_state == ConversationState.CONTRIBUTE_PHOTOS.value:
                # Handle photo in contribution flow
                agent_request = AgentRequest(
                    agent_type=AgentType.DATA_MANAGEMENT,
                    message=f"Photo uploaded: {photo.file_id}",
                    user_id=user.id,
                    conversation_id=str(chat_id),
                    context=conversation_context
                )
                
                response = await self._process_agent_request(agent_request)
                
                # Update context
                if response.context_updates:
                    await self.conversation_service.update_conversation_context(
                        str(chat_id), response.context_updates
                    )
                
                await self._send_agent_response(update, context, response)
            else:
                # General photo handling
                await update.message.reply_text(
                    "📸 Photo received! If you're adding a new place, please start the process first with 'add a new place'."
                )
            
        except Exception as e:
            self.logger.error(f"Error handling photo: {e}")
            await update.message.reply_text("Error processing your photo. Please try again.")
    
    async def _handle_callback_query(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle inline keyboard button presses."""
        
        try:
            query = update.callback_query
            user = query.from_user
            chat_id = query.message.chat_id
            callback_data = query.data
            
            await query.answer()  # Acknowledge the callback
            
            # Get conversation context
            conversation_context = await self.conversation_service.get_conversation_context(str(chat_id))
            
            # Create agent request
            agent_request = AgentRequest(
                agent_type=AgentType.SUPERVISOR,
                message=f"Callback: {callback_data}",
                user_id=user.id,
                conversation_id=str(chat_id),
                context=conversation_context
            )
            
            response = await self._process_agent_request(agent_request)
            
            # Update context
            if response.context_updates:
                await self.conversation_service.update_conversation_context(
                    str(chat_id), response.context_updates
                )
            
            # Send response
            await self._send_agent_response(update, context, response, edit_message=True)
            
        except Exception as e:
            self.logger.error(f"Error handling callback query: {e}")
            await query.message.reply_text("Error processing your selection. Please try again.")
    
    async def _handle_webapp_data(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle data received from WebApp."""
        
        try:
            data = json.loads(update.effective_message.web_app_data.data)
            user = update.effective_user
            
            self.log_with_context(
                "info",
                "WebApp data received",
                user_id=user.id,
                data_keys=list(data.keys())
            )
            
            # Process WebApp data (e.g., place contributions)
            if data.get("type") == "place_contribution":
                await update.message.reply_text(
                    f"✅ Place contribution received!\n\n"
                    f"**{data.get('name', 'N/A')}** has been submitted for review.",
                    reply_markup=ReplyKeyboardRemove(),
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "📱 WebApp data received successfully!",
                    reply_markup=ReplyKeyboardRemove()
                )
            
        except json.JSONDecodeError:
            await update.message.reply_text(
                "❌ Error processing WebApp data. Please try again."
            )
        except Exception as e:
            self.logger.error(f"Error handling WebApp data: {e}")
            await update.message.reply_text(
                "❌ Error processing your submission. Please try again."
            )
    
    async def _process_agent_request(self, request: AgentRequest) -> AgentResponse:
        """Process request through the agent system."""
        
        # Get supervisor agent
        supervisor = agent_registry.get_agent(AgentType.SUPERVISOR)
        if not supervisor:
            raise TelegramAPIError("Supervisor agent not available")
        
        # Process request
        response = await supervisor.process_request(request)
        
        # Log agent interaction
        self.log_with_context(
            "debug",
            "Agent request processed",
            user_id=request.user_id,
            agent=response.agent_type.value,
            confidence=response.confidence
        )
        
        return response
    
    async def _send_agent_response(
        self, 
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE,
        response: AgentResponse,
        edit_message: bool = False
    ) -> None:
        """Send agent response to user with appropriate formatting."""
        
        try:
            # Prepare message text
            message_text = response.response
            
            # Prepare reply markup
            reply_markup = None
            
            # Handle actions
            if response.actions:
                reply_markup = await self._create_reply_markup(response.actions)
            
            # Send message
            if edit_message and update.callback_query:
                await update.callback_query.edit_message_text(
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                message = update.message or update.callback_query.message
                await message.reply_text(
                    text=message_text,
                    reply_markup=reply_markup,
                    parse_mode=ParseMode.MARKDOWN
                )
                
        except Exception as e:
            self.logger.error(f"Error sending agent response: {e}")
            # Fallback to simple text message
            message = update.message or update.callback_query.message
            await message.reply_text(
                "I processed your request but had trouble formatting the response. Please try again."
            )
    
    async def _create_reply_markup(self, actions: List[Dict[str, Any]]) -> Optional[Any]:
        """Create appropriate reply markup from agent actions."""
        
        try:
            keyboards = []
            inline_keyboards = []
            
            for action in actions:
                action_type = action.get("type")
                action_text = action.get("text", "Action")
                
                if action_type == "request_location":
                    # Location request button
                    keyboard_button = KeyboardButton(text=action_text, request_location=True)
                    keyboards.append([keyboard_button])
                
                elif action_type == "show_webapp":
                    # WebApp button (only if URL is provided and is HTTPS)
                    webapp_url = action.get("url")
                    if webapp_url and webapp_url.startswith('https://'):
                        webapp_button = InlineKeyboardButton(
                            text=action_text,
                            web_app=WebAppInfo(url=webapp_url)
                        )
                        inline_keyboards.append([webapp_button])
                    else:
                        # Skip WebApp button if no HTTPS URL available
                        self.logger.debug("Skipping WebApp button - no HTTPS URL provided")
                
                elif action_type in ["suggest_refinement", "get_more_details", "refine_preferences"]:
                    # Inline action buttons
                    callback_data = action.get("callback_data", action_type)
                    inline_button = InlineKeyboardButton(
                        text=action_text,
                        callback_data=callback_data
                    )
                    inline_keyboards.append([inline_button])
            
            # Return appropriate markup
            if keyboards and inline_keyboards:
                # If we have both, prioritize keyboard buttons and add inline as additional
                return ReplyKeyboardMarkup(keyboards, resize_keyboard=True)
            elif keyboards:
                return ReplyKeyboardMarkup(keyboards, resize_keyboard=True)
            elif inline_keyboards:
                return InlineKeyboardMarkup(inline_keyboards)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error creating reply markup: {e}")
            return None
    
    async def start_webhook(self, webhook_url: str, port: int = 8443) -> None:
        """Start the bot with webhook mode."""
        
        try:
            # Start the application
            await self.application.start()
            
            # Set webhook
            await self.application.bot.set_webhook(url=webhook_url)
            
            self.logger.info(f"Webhook set to {webhook_url}")
            
            # Start webhook server
            await self.application.run_webhook(
                listen="0.0.0.0",
                port=port,
                webhook_url=webhook_url
            )
            
        except Exception as e:
            self.logger.error(f"Error starting webhook: {e}")
            raise TelegramAPIError(f"Webhook setup failed: {e}")
    
    # Note: Polling is now handled directly in bot_main.py using self.application.run_polling()
    
    async def close(self) -> None:
        """Close the Telegram client."""
        
        if self.application:
            await self.application.stop()
            await self.application.shutdown()
            self.logger.info("Telegram client closed")


# Global Telegram client instance
telegram_client = TelegramClient() 
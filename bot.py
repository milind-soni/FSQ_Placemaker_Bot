#!/usr/bin/env python
import json
import logging
from telegram import (
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, WebAppInfo,
    InlineKeyboardButton, InlineKeyboardMarkup
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, 
    filters, ConversationHandler, CallbackQueryHandler
)
from openai import OpenAI
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv

load_dotenv()

OPENAI_KEY = os.environ.get("OPENAI_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")

print(OPENAI_KEY, TELEGRAM_BOT_TOKEN)

client = OpenAI(api_key=OPENAI_KEY)

class UserInputClassifier(BaseModel):
    is_valid: bool = Field(description="Checks if the overall user_input is correct or not")
    phone: str = Field(description="The phone number extracted from user input")
    website: str = Field(description="The wesbite extracted from user input")
    email: str = Field(description="The website extracted from user input")
    explation: str = Field(description="The explanation for the response that you provide")

# Conversation states
(LOCATION, NAME, CATEGORY, ADDRESS, CONTACT, HOURS, CUSTOM_HOURS,
 ATTRIBUTES, CHAIN_STATUS, PHOTOS, CONFIRM) = range(11)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


async def parse_contact_info_gpt(user_input: str) -> dict:
    """Use GPT-4o to parse user input into phone, website and email 
    """
    user_prompt = f"""
        You are a helpful assistant. The user is entering contact details (phone, website, email) in a single string. These details could be in any order, with any separators.

        1. Parse out "phone", "website", and "email" from the text. If something isn't provided, output an empty string for that field.
        2. If the input is incomplete or you can't identify the fields, you must set "is_valid" to false. The checks for input fields can be very basic

        User input: {user_input}
        """
    
    completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a parsing assistant."},
                {"role": "user", "content": user_prompt},
            ],
            response_format=UserInputClassifier
        )
    
    msg = completion.choices[0].message.parsed

    print("GPT parse message = ", msg)

    # Return the structured dict
    return {
        "is_valid": msg.is_valid,
        "phone": msg.phone,
        "website": msg.website,
        "email": msg.email
    }


async def parse_hours_info_gpt(user_input: str) -> dict:
    """Use GPT-4o to parse user input into normalized_hours string
    """
    user_prompt = f"""
        You are a helpful assistant. The user is entering custom operating hours in free text.
        Examples might be "Mon-Sat 9am to 6pm" or "M-F 10-2AM". 
        They can use different separators or day abbreviations.

        1. Read the user's text, parse out a consistent operating-hours format,
        e.g. "Mon-Sat 9:00 AM - 6:00 PM".
        2. If you cannot confidently parse or if the user's input is ambiguous, 
        respond with is_valid=false and include an explanation.
        3. Return only valid JSON:
        {{
            "is_valid": <true/false>,
            "normalized_hours": "<string or empty>",
            "explanation": "<string>"
        }}

        User input: {user_input}

        Return valid JSON only, with no extra keys or text outside the JSON. Don't start or end the json with ```json etc.
        """
    
    completion = client.beta.chat.completions.parse(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a parsing assistant."},
                {"role": "user", "content": user_prompt},
            ]
        )
    
    msg = json.loads(completion.choices[0].message.content)

    print(msg)

    return {
        "is_valid": msg["is_valid"],
        "normalized_hours": msg["normalized_hours"],
        "explanation": msg["explanation"]
    }
    




async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle the data received from the WebApp"""
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        await update.message.reply_html(
            text=f"New place added successfully!\n\n"
                 f"Name: {data.get('name', 'N/A')}\n"
                 f"Category: {data.get('category', 'N/A')}\n"
                 f"Address: {data.get('address', 'N/A')}",
            reply_markup=ReplyKeyboardRemove(),
        )
    except json.JSONDecodeError:
        await update.message.reply_text(
            "Sorry, there was an error processing the data.",
            reply_markup=ReplyKeyboardRemove(),
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Start the conversation and ask for location as 1st step."""
    keyboard = [
        [KeyboardButton("Share Location 📍", request_location=True)],
        # [KeyboardButton(
        #     text="Explore the foursquare location data",
        #     web_app=WebAppInfo(
        #         url="https://staging.fused.io/server/v1/realtime-shared/fsh_4a9CSIwYe2QZeDbsmExyIJ/run/file?dtype_out_raster=png&dtype_out_vector=csv"
        #     )
        # )]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Welcome to the Place Maker Bot!\n\n"
        "Please share your location to continue.",
        # "You can either:\n"
        # "1. Share your location to start adding a place\n"
        # "2. Explore the Foursquare Data on the Map",
        reply_markup=reply_markup
    )
    return LOCATION

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the location and then show the 2 options:
    1. Add a new place
    2. Explore the 4Sq data on map
    """
    user_location = update.message.location
    context.user_data['location'] = {
        'latitude': user_location.latitude,
        'longitude': user_location.longitude
    }

    # Show two options in a new keyboard
    keyboard = [
        [KeyboardButton("Add a new place")],
        [KeyboardButton(
            text="Explore the foursquare location data",
            web_app=WebAppInfo(
                url="https://staging.fused.io/server/v1/realtime-shared/fsh_4a9CSIwYe2QZeDbsmExyIJ/run/file?dtype_out_raster=png&dtype_out_vector=csv"
            )
        )]
    ]

    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Location received!\n"
        "What would you like to do next?\n\n"
        "1. Add a new place\n"
        "2. Explore the Foursquare Data on the Map",
        reply_markup=reply_markup
    )

    return LOCATION

async def location_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Captures the text choice in location_handler
    If user choose "Add a new place", move on to ask for the place name and same chain flow
    """
    user_text = update.message.text.strip().lower()
    if "add a new place" in user_text:
        # Next step -> ask name and continue the chain of questions
        await update.message.reply_text(
            "Great! Now, please enter the name of the place:",
            reply_markup=ReplyKeyboardRemove()
        )
        return NAME
    else:
        # error handling part here
        await update.message.reply_text(
            "Please select a valid option or use the menu buttons."
        )
        return LOCATION

async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save the name and ask for category."""
    context.user_data['name'] = update.message.text
    
    categories = [
        ["Restaurant 🍽️", "Shop 🛍️", "Hotel 🏨"],
        ["Bar 🍸", "Cafe ☕", "Entertainment 🎭"],
        ["Services 🔧", "Other 📌"]
    ]
    reply_markup = ReplyKeyboardMarkup(categories, resize_keyboard=True)
    
    await update.message.reply_text(
        "Please select or type the category:",
        reply_markup=reply_markup
    )
    return CATEGORY

async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save category and ask for address."""
    context.user_data['category'] = update.message.text
    
    await update.message.reply_text(
        "Please enter the address of the place:",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADDRESS

async def address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save address and ask for contact info."""
    context.user_data['address'] = update.message.text
    
    await update.message.reply_text(
        "Please enter contact information:\n"
        "Format: phone,website,email\n"
        "Example: +1234567890,www.example.com,contact@example.com\n"
        "(Type 'skip' to skip this step)",
        reply_markup=ReplyKeyboardRemove()
    )
    return CONTACT

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save contact info and ask for hours."""
    user_text = update.message.text.strip()

    if user_text.lower() == 'skip':
        keyboard = [
            [KeyboardButton("Open 24/7")],
            [KeyboardButton("Custom Hours")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please select the operating hours:",
            reply_markup=reply_markup
        )
        return HOURS
    
    result = await parse_contact_info_gpt(user_text)

    if not result["is_valid"]:
        await update.message.reply_text(
            f"Your contact info seems invalid or incomplete.\n"
            "Please try again. Format: phone,website,email\n"
            "(Type 'skip' to skip.)"
        )
        # Stay in the same CONTACT state
        return CONTACT
    
    else:
        # if valid – store the parsed data
        context.user_data["contact"] = {
            "phone": result["phone"],
            "website": result["website"],
            "email": result["email"]
        }

        keyboard = [
            [KeyboardButton("Open 24/7")],
            [KeyboardButton("Custom Hours")]
        ]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        
        await update.message.reply_text(
            "Please select the operating hours:",
            reply_markup=reply_markup
        )
        return HOURS


async def hours_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Save hours and ask about chain status."""
    user_choice = update.message.text.strip().lower()

    if "open 24/7" in user_choice:
        context.user_data["hours"] = "Open 24/7"
    
        keyboard = [
            [InlineKeyboardButton("Yes", callback_data="chain_yes"),
            InlineKeyboardButton("No", callback_data="chain_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Is this place part of a chain?",
            reply_markup=reply_markup
        )
        return CHAIN_STATUS
    
    elif "custom hours" in user_choice:
        # Move to CUSTOM_HOURS state
        await update.message.reply_text(
            "Please enter the operating hours in your own words. For example:\n"
            "\"Mon-Sat 9am to 6pm\" or \"M-F 10-2AM\"."
        )
        return CUSTOM_HOURS


async def custom_hours_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Validate the user's custom hours with 4o. If invalid,
    ask them to re-enter. If valid, move on to chain status.
    """
    user_text = update.message.text.strip()
    
    # Call GPT to validate
    result = await parse_hours_info_gpt(user_text)
    
    if not result["is_valid"]:
        await update.message.reply_text(
            f"Sorry, we couldn't parse those hours.\n"
            "Please try again, or type something like \"Mon-Fri 9am to 6pm\"."
        )
        return CUSTOM_HOURS
    else:
        # if all good
        context.user_data["hours"] = result["normalized_hours"]
        
        # Proceed to chain status
        keyboard = [
            [InlineKeyboardButton("Yes", callback_data="chain_yes"),
             InlineKeyboardButton("No", callback_data="chain_no")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "Is this place part of a chain?",
            reply_markup=reply_markup
        )
        return CHAIN_STATUS



async def chain_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle chain status response and move to attributes."""
    query = update.callback_query
    await query.answer()
    
    context.user_data['is_chain'] = query.data == "chain_yes"
    
    attributes = [
        ["ATM 🏧", "Reservations 📅"],
        ["Delivery 🚚", "Parking 🅿️"],
        ["Outdoor Seating 🪑", "Restroom 🚻"],
        ["Credit Cards 💳", "WiFi 📶"],
        ["Done ✅"]
    ]
    reply_markup = ReplyKeyboardMarkup(attributes, resize_keyboard=True)
    
    await query.message.reply_text(
        "Select all applicable attributes (press Done when finished):",
        reply_markup=reply_markup
    )
    return ATTRIBUTES

async def attributes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle attributes selection and ask for photos."""
    if update.message.text == "Done ✅":
        await update.message.reply_text(
            "Please send photos of the place (up to 3):\n"
            "1. Storefront/Entrance\n"
            "2. Interior\n"
            "3. Special features\n\n"
            "Send /skip if you don't have photos.",
            reply_markup=ReplyKeyboardRemove()
        )
        return PHOTOS
    
    if 'attributes' not in context.user_data:
        context.user_data['attributes'] = []
    context.user_data['attributes'].append(update.message.text)
    return ATTRIBUTES

async def photos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle photo uploads and move to confirmation."""
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []
    
    if update.message.photo:
        context.user_data['photos'].append(update.message.photo[-1].file_id)
        
        if len(context.user_data['photos']) >= 3:
            return await confirm_data(update, context)
        
        await update.message.reply_text(
            f"Photo {len(context.user_data['photos'])} received! "
            "Send another or type /done when finished."
        )
        return PHOTOS
    
    if update.message.text == "/skip" or update.message.text == "/done":
        return await confirm_data(update, context)
    
    return PHOTOS

async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Show all collected data and ask for confirmation."""
    data = context.user_data
    confirmation_text = (
        "📍 Place Summary:\n\n"
        f"Name: {data.get('name')}\n"
        f"Category: {data.get('category')}\n"
        f"Address: {data.get('address')}\n"
        f"Hours: {data.get('hours')}\n"
        f"Chain: {'Yes' if data.get('is_chain') else 'No'}\n"
        f"Attributes: {', '.join(data.get('attributes', []))}\n"
        f"Photos: {len(data.get('photos', []))} uploaded\n\n"
        "Is this information correct?"
    )
    
    keyboard = [
        [InlineKeyboardButton("Yes, Submit ✅", callback_data="confirm_yes"),
         InlineKeyboardButton("No, Edit ✏️", callback_data="confirm_no")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return CONFIRM

async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Process the final confirmation and save data."""
    query = update.callback_query
    await query.answer()
    
    if query.data == "confirm_yes":
        # Here you would typically save the data to your database
        await query.message.reply_text(
            "Perfect! Your place has been added successfully. 🎉\n"
            "Type /start to add another place.",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END
    else:
        await query.message.reply_text(
            "Okay, let's start over. Please type /start again",
            reply_markup=ReplyKeyboardRemove()
        )
        return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Set up conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [
                MessageHandler(filters.LOCATION, location_handler),
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data),
                MessageHandler(filters.TEXT & ~filters.COMMAND, location_choice_handler)
            ],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_handler)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, hours_handler)],
            CUSTOM_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_hours_handler)],
            CHAIN_STATUS: [CallbackQueryHandler(chain_status_handler)],
            ATTRIBUTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, attributes_handler)],
            PHOTOS: [
                MessageHandler(filters.PHOTO, photos_handler),
                CommandHandler("skip", photos_handler),
                CommandHandler("done", photos_handler)
            ],
            CONFIRM: [CallbackQueryHandler(handle_confirmation)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    
    application.add_handler(conv_handler)
    
    # Start the bot
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()

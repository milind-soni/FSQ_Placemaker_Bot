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

# Conversation states
(LOCATION, NAME, CATEGORY, ADDRESS, CONTACT, HOURS, 
 ATTRIBUTES, CHAIN_STATUS, PHOTOS, CONFIRM) = range(10)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

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
    """Start the conversation and ask for location."""
    keyboard = [
        [KeyboardButton("Share Location 📍", request_location=True)],
        [KeyboardButton(
            text="Explore the foursquare location data",
            web_app=WebAppInfo(
                url="https://staging.fused.io/server/v1/realtime-shared/fsh_4a9CSIwYe2QZeDbsmExyIJ/run/file?dtype_out_raster=png&dtype_out_vector=csv"
            )
        )]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "Welcome to the Place Maker Bot!\n\n"
        "You can either:\n"
        "1. Share your location to start adding a place\n"
        "2. Explore the Foursquare Data on the Map",
        reply_markup=reply_markup
    )
    return LOCATION

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the location and ask for place name."""
    user_location = update.message.location
    context.user_data['location'] = {
        'latitude': user_location.latitude,
        'longitude': user_location.longitude
    }
    
    await update.message.reply_text(
        "Great! Now, please enter the name of the place:",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME

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
    if update.message.text.lower() != 'skip':
        contact_info = update.message.text.split(',')
        context.user_data['contact'] = {
            'phone': contact_info[0] if len(contact_info) > 0 else '',
            'website': contact_info[1] if len(contact_info) > 1 else '',
            'email': contact_info[2] if len(contact_info) > 2 else ''
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
    context.user_data['hours'] = update.message.text
    
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
        # Return to start if they want to edit
        return await start(update, context)

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the conversation."""
    await update.message.reply_text(
        "Operation cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

def main() -> None:
    """Start the bot."""
    application = Application.builder().token("YourTokenHere").build()
    
    # Set up conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [
                MessageHandler(filters.LOCATION, location_handler),
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data)
            ],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            CATEGORY: [MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_handler)],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler)],
            HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, hours_handler)],
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

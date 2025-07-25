import json
import logging
from telegram import (
    KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, ContextTypes, MessageHandler, 
    filters, ConversationHandler
)
from telegram.constants import ChatAction
from openai import OpenAI
from pydantic import BaseModel, Field
import os
import requests
from dotenv import load_dotenv
import re
import base64

load_dotenv()

OPENAI_KEY = os.environ.get("OPENAI_KEY")
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
FOURSQUARE_API_KEY = os.environ.get("FOURSQUARE_API_KEY")

client = OpenAI(api_key=OPENAI_KEY)

# Conversation states
(LOCATION, LOCATION_CHOICE, QUERY, REFINE) = range(4)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Define a Pydantic model for GPT to parse search queries
class FoursquareSearchParams(BaseModel):
    query: str = Field(description="The core search keyword, e.g. 'burger', 'pizza', etc.")
    open_now: bool = Field(default=None, description="Whether to filter for places open now")
    radius: int = Field(default=None, description="Radius in meters (if specified)")
    limit: int = Field(default=None, description="Number of results to return")
    fsq_category_ids: str = Field(default=None, description="Foursquare category IDs, comma-separated if multiple")
    min_price: int = Field(default=None, description="Minimum price (1=most affordable, 4=most expensive)")
    max_price: int = Field(default=None, description="Maximum price (1=most affordable, 4=most expensive)")
    search_now: bool = Field(default=False, description="True if the user wants to trigger the search now, otherwise False.")
    explanation: str = Field(description="Explanation of how the query was parsed")

async def parse_search_query_gpt(user_input: str, current_params: dict = None) -> dict:
    """Use GPT-4o to parse a natural language search query into Foursquare API parameters."""
    current_params = current_params or {}
    user_prompt = f"""
        You are a helpful assistant. The user is searching for places using natural language. 
        Your job is to extract only the core search keyword (e.g., 'burger' from 'I'm looking for a great burger joint near me!').
        Do not include words like 'place', 'joint', 'restaurant', 'shop', etc. Only the essential food or place type.
        Also, parse any additional filters the user provides (open now, radius, min_price, max_price, etc). If a field is not mentioned, leave it as null.
        min_price and max_price are integers from 1 (most affordable) to 4 (most expensive).
        Here are the current search parameters (if any):
        {json.dumps(current_params)}
        Merge any new information from the user with these existing parameters. If the user provides a new value for a field, overwrite the old one.
        
        If the user message indicates they want to see the results now (e.g., 'search now', 'show me the results', 'that's it', 'done', etc.), set 'search_now' to true. Otherwise, set it to false.
        
        User input: {user_input}
    """
    completion = client.beta.chat.completions.parse(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
        response_format=FoursquareSearchParams
    )
    msg = completion.choices[0].message.parsed
    return msg

async def suggest_next_filters(params: dict) -> str:
    """Use GPT to generate a natural, human-like follow-up prompt for more filters."""
    missing = []
    if not params.get("radius"):
        missing.append("distance")
    if not params.get("open_now"):
        missing.append("open now")
    if not params.get("min_price"):
        missing.append("minimum price")
    if not params.get("max_price"):
        missing.append("maximum price")
    # Add more suggestions as needed
    if not missing:
        return "You can add more preferences, or just ask me to search now!"
    # Compose a prompt for GPT
    user_context = []
    for k, v in params.items():
        if v is not None and v != "":
            user_context.append(f"{k}: {v}")
    gpt_prompt = f"""
        You are a friendly assistant helping a user search for places. The user has already set these filters: {', '.join(user_context) if user_context else 'none yet'}.
        The following filters are still missing: {', '.join(missing)}.
        In a natural, conversational way, ask the user if they want to specify any of these missing filters. Do not use a robotic or templated tone. Make it sound like a real human would ask in a chat.
        Keep it short and friendly. Don't use any emojis.
    """
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=1,
        messages=[
            {"role": "system", "content": "You are a helpful, friendly assistant."},
            {"role": "user", "content": gpt_prompt},
        ]
    )
    return completion.choices[0].message.content.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [
        [KeyboardButton("Share Location 📍", request_location=True)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Welcome to the Conversational Place Search Bot!\n\nPlease share your location to continue.",
        reply_markup=reply_markup
    )
    return LOCATION

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_location = update.message.location
    context.user_data['location'] = {
        'latitude': user_location.latitude,
        'longitude': user_location.longitude
    }
    context.user_data['search_params'] = {}
    
    # Show menu with webapp option
    keyboard = [
        [KeyboardButton("Search Foursquare data")],
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
        "What would you like to do?\n\n"
        "1. Search Foursquare data\n"
        "2. Explore the Foursquare Data on the Map",
        reply_markup=reply_markup
    )
    return LOCATION_CHOICE

async def query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_query = update.message.text.strip()
    
    # Show typing indicator while processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    current_params = context.user_data.get('search_params', {})
    gpt_result = await parse_search_query_gpt(user_query, current_params)
    # Merge/overwrite params
    params = current_params.copy()
    for k, v in gpt_result.model_dump().items():
        if v is not None and v != "":
            params[k] = v
    context.user_data['search_params'] = params
    # Print current filters to console for debugging
    print("Current search filters:", params)
    # On first query, immediately show results
    return await do_foursquare_search(update, context, ask_refine=True)

async def gpt_suggest_refine_prompt(params: dict) -> str:
    """Use GPT to generate a dynamic, conversational prompt suggesting missing filters."""
    missing = []
    if not params.get("radius"):
        missing.append("distance")
    if not params.get("open_now"):
        missing.append("open now")
    if not params.get("min_price"):
        missing.append("minimum price")
    if not params.get("max_price"):
        missing.append("maximum price")
    # Add more suggestions as needed
    user_context = []
    for k, v in params.items():
        if v is not None and v != "":
            user_context.append(f"{k}: {v}")
    gpt_prompt = f"""
        You are a friendly assistant helping a user search for places. The user has already set these filters: {', '.join(user_context) if user_context else 'none yet'}.
        The following filters are still missing: {', '.join(missing)}.
        In a natural, conversational way, suggest to the user that they can add any of these missing filters to narrow down the results, or say 'no' to finish. Do not use a robotic or templated tone. Make it sound like a real human would ask in a chat. Keep it short and friendly. Don't use any emojis.
    """
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=1,
        messages=[
            {"role": "system", "content": "You are a helpful, friendly assistant."},
            {"role": "user", "content": gpt_prompt},
        ]
    )
    return completion.choices[0].message.content.strip()

async def gpt_generate_results_header(params: dict) -> str:
    """Use GPT to generate a dynamic, conversational header for search results based on the query and filters."""
    query = params.get("query", None)
    user_context = []
    for k, v in params.items():
        if v is not None and v != "" and k != "query":
            user_context.append(f"{k}: {v}")
    gpt_prompt = f"""
        You are a friendly assistant helping a user search for places. The user is about to see a list of results for their search. 
        The main search keyword is: {query if query else 'unknown'}.
        The user has set these filters: {', '.join(user_context) if user_context else 'none'}.
        Write a single, catchy, human-like one-liner to introduce the results. 
        Make it specific to the query if possible (e.g., 'Here are some top burger spots you might want to check out', 'Let your pizza journey begin—these delicious destinations await', 'Looking for the best coffee in town? Start with these places').
        If the query is missing, use a generic but still friendly intro. Do not use emojis. Keep it short and engaging.
    """
    completion = client.chat.completions.create(
        model="gpt-4o",
        temperature=1,
        messages=[
            {"role": "system", "content": "You are a helpful, friendly assistant."},
            {"role": "user", "content": gpt_prompt},
        ]
    )
    return completion.choices[0].message.content.strip()

async def do_foursquare_search(update: Update, context: ContextTypes.DEFAULT_TYPE, ask_refine=False) -> int:
    # Show typing indicator while searching
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    search_params = context.user_data.get("search_params", {})
    lat = context.user_data['location']['latitude']
    lng = context.user_data['location']['longitude']
    base_url = "https://places-api.foursquare.com/places/search"
    params = {
        "ll": f"{lat},{lng}",
        "fields": "fsq_place_id,name,distance,hours,price,rating"
    }
    if search_params.get("query"):
        params["query"] = search_params["query"]
    if search_params.get("limit"):
        params["limit"] = search_params["limit"]
    else:
        params["limit"] = 5
    if search_params.get("open_now"):
        params["open_now"] = "true"
    if search_params.get("radius"):
        params["radius"] = search_params["radius"]
    if search_params.get("fsq_category_ids"):
        params["fsq_category_ids"] = search_params["fsq_category_ids"]
    if search_params.get("min_price"):
        params["min_price"] = search_params["min_price"]
    if search_params.get("max_price"):
        params["max_price"] = search_params["max_price"]
    headers = {
        "accept": "application/json",
        "X-Places-Api-Version": "2025-02-05",
        "Authorization": f"Bearer {FOURSQUARE_API_KEY}"
    }
    try:
        resp = requests.get(base_url, params=params, headers=headers)
        data = resp.json()

        print("="*50)
        print(f"params = {params}")
        print("="*50)
        from pprint import pprint
        pprint(data)
        print("="*50)
        results = data.get("results", [])

        # --- Fetch images for each place ---
        # Show typing indicator while fetching images
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        
        photo_headers = {
            "accept": "application/json",
            "Authorization": f"Bearer {FOURSQUARE_API_KEY}",
        }
        for place in results:
            fsq_id = place.get("fsq_place_id")
            if not fsq_id:
                place["image_url"] = None
                continue
            photo_url = f"https://api.foursquare.com/v3/places/{fsq_id}/photos?limit=5"
            try:
                photo_resp = requests.get(photo_url, headers=photo_headers)
                photo_data = photo_resp.json()
                if isinstance(photo_data, list) and len(photo_data) > 0:
                    photo = photo_data[0]
                    prefix = photo.get("prefix", "")
                    suffix = photo.get("suffix", "")
                    width = photo.get("width", 300)
                    height = photo.get("height", 225)
                    # Target size
                    target_w = 300
                    target_h = int((target_w / width) * height) if width and height else 225
                    image_url = f"{prefix}{target_w}x{target_h}{suffix}"
                    place["image_url"] = image_url
                else:
                    place["image_url"] = None
            except Exception as e:
                place["image_url"] = None
        # --- End fetch images ---

        if not results:
            await update.message.reply_text("No places found with your filters. Type a new query or /start to try again.")
            return QUERY
        else:
            # Show typing indicator while generating results header
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            
            # Generate a dynamic, conversational header for the results
            header = await gpt_generate_results_header(search_params)
            lines = []
            for place in results:
                name = place.get("name", "Unknown")
                dist = place.get("distance", "N/A")
                # Rating: out of 10, show as X/10 ⭐
                rating = place.get("rating", None)
                if rating is not None and rating != "":
                    rating_str = f"{rating}/10 ⭐"
                else:
                    rating_str = "N/A"
                # Pricing: 1-4, show as $ in bold
                price = place.get("price", None)
                if price is not None and price != "":
                    try:
                        price_int = int(price)
                        price_str = f"<b>{'$' * price_int}</b>"
                    except Exception:
                        price_str = "N/A"
                else:
                    price_str = "N/A"
                # Open now/closed
                open_now = place.get("hours", {}).get("open_now", None)
                if open_now is True:
                    open_str = "<b>Open Now</b>"
                elif open_now is False:
                    open_str = "<b>Currently Closed!</b>"
                else:
                    open_str = "N/A"
                # Format the message for each place
                place_msg = (
                    f"<b>{name}</b>\n"
                    f"Rating: {rating_str}\n"
                    f"Pricing: {price_str}\n"
                    f"Status: {open_str}\n"
                    f"Distance: {dist}m away"
                )
                lines.append(place_msg)
            reply = header + "\n\n" + "\n\n".join(lines)
            await update.message.reply_text(reply, parse_mode="HTML")

            # --- Add Open List View Button ---
            # Serialize and encode the results (now with image_url)
            places_json = json.dumps(results)
            places_b64 = base64.urlsafe_b64encode(places_json.encode()).decode()
            webapp_url = f"http://192.168.1.44:8000/?data={places_b64}"
            keyboard = [[InlineKeyboardButton("Open List View", url=webapp_url)]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Want to see these results in a beautiful list view? Tap below!",
                reply_markup=reply_markup
            )
            # --- End Open List View Button ---

            if ask_refine:
                # Show typing indicator while generating refine prompt
                await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
                
                refine_prompt = await gpt_suggest_refine_prompt(search_params)
                await update.message.reply_text(refine_prompt)
                return REFINE
            else:
                return QUERY
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")
        return QUERY

async def gpt_refine_intent(user_message: str) -> bool:
    """Use GPT to determine if the user wants to end the search (True) or refine further (False)."""
    prompt = f"""
    The user is interacting with a place search assistant. They just saw a list of results and were prompted to add more filters or say 'no' to finish. 
    Classify the user's message as either:
    - 'end' (if they want to stop, are satisfied, or say things like 'no', 'that's all', 'I'm done', 'stop', etc.)
    - 'refine' (if they want to add more filters, change the search, or anything else)
    Only reply with 'end' or 'refine'.
    
    User message: {user_message}
    """
    completion = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that classifies user intent."},
            {"role": "user", "content": prompt},
        ]
    )
    result = completion.choices[0].message.content.strip().lower()
    return result == 'end'

async def refine_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()
    
    # Show typing indicator while processing
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    if await gpt_refine_intent(user_text):
        await update.message.reply_text("Okay! If you want to start a new search, just type your query or /start.")
        return ConversationHandler.END
    else:
        # Treat any other input as a new filter
        return await query_handler(update, context)

async def location_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the user's choice after location is shared."""
    user_text = update.message.text.strip().lower()
    
    if "search foursquare data" in user_text:
        await update.message.reply_text(
            "Great! What are you looking for? (e.g. 'I'm craving sushi', 'Find a burger', etc.)",
            reply_markup=ReplyKeyboardRemove()
        )
        return QUERY
    else:
        # Handle other cases or invalid input
        await update.message.reply_text(
            "Please select a valid option from the menu."
        )
        return LOCATION_CHOICE

def main() -> None:
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [MessageHandler(filters.LOCATION, location_handler)],
            LOCATION_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_choice_handler)],
            QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, query_handler)],
            REFINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, refine_handler)],
        },
        fallbacks=[CommandHandler("start", start)]
    )
    application.add_handler(conv_handler)
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main() 
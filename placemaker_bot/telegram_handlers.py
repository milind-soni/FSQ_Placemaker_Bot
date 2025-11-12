import base64
import json
from typing import Dict, Any

from telegram import (
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    WebAppInfo,
)
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ChatAction

from .logging import build_log_extra, ensure_request_id, set_new_request_id
from .logging import setup_logging
from .llm import LLMClient
from .models import FoursquareSearchParams, UserInputClassifier, AddressParseResult
from .foursquare import FoursquareClient
from .utils import discover_external_base_url

from pathlib import Path

logger = setup_logging()
llm = LLMClient()
fsq = FoursquareClient()

# Load category mapping (human-readable -> category ID)
_FSQ_CATEGORIES_DOCS_URL = "https://docs.foursquare.com/data-products/docs/categories"
_CATEGORIES_JSON_PATH = Path(__file__).parent / "assets" / "personalization-apis-movement-sdk-categories.json"
try:
    with open(_CATEGORIES_JSON_PATH, "r", encoding="utf-8") as _f:
        _CATEGORY_NAME_TO_ID: Dict[str, str] = json.load(_f)
except Exception:
    _CATEGORY_NAME_TO_ID = {}
_CATEGORY_KEY_LOWER_TO_ID: Dict[str, str] = {k.strip().lower(): v for k, v in _CATEGORY_NAME_TO_ID.items()}
_CATEGORY_VALID_NAMES: list[str] = list(_CATEGORY_NAME_TO_ID.keys())

_ATTRIBUTES_KEYBOARD_LAYOUT: tuple[tuple[str, ...], ...] = (
    ("ATM 🏧", "Reservations 📅"),
    ("Delivery 🚚", "Parking 🅿️"),
    ("Outdoor Seating 🪑", "Restroom 🚻"),
    ("Credit Cards 💳", "WiFi 📶"),
    ("Done ✅",),
)


def _build_attributes_keyboard() -> ReplyKeyboardMarkup:
    """Return a keyboard markup for selecting place attributes."""
    return ReplyKeyboardMarkup(
        [list(row) for row in _ATTRIBUTES_KEYBOARD_LAYOUT],
        resize_keyboard=True,
    )


(
    LOCATION,
    LOCATION_CHOICE,
    QUERY,
    REFINE,
    NAME,
    CATEGORY,
    ADDRESS,
    COORDINATES,
    COORDINATES_MANUAL,
    CONTACT,
    HOURS,
    CUSTOM_HOURS,
    ATTRIBUTES,
    CHAIN_STATUS,
    CHAIN_DETAILS,
    PRIVATE_PLACE,
    PHOTOS,
    CONFIRM,
) = range(18)


def _is_valid_categories(value: str) -> bool:
    # Allow comma-separated FSQ category IDs (alphanumeric tokens)
    tokens = [t.strip() for t in str(value).split(',') if t.strip()]
    return len(tokens) > 0 and all(t.isalnum() for t in tokens)


def _sanitize_suggest_params(raw: Dict[str, Any]) -> Dict[str, Any]:
    allowed_keys = {
        'name', 'categories', 'address', 'locality', 'region', 'postcode', 'country_code',
        'latitude', 'longitude', 'parentId', 'isPrivatePlace', 'tel', 'website',
        'email', 'facebookUrl', 'instagram', 'twitter', 'hours', 'attributes', 'dry_run'
    }
    params: Dict[str, Any] = {k: v for k, v in raw.items() if k in allowed_keys}

    # Drop empty values
    params = {k: v for k, v in params.items() if v not in (None, "", [])}

    # Categories must be FSQ category IDs (alphanumeric)
    if 'categories' in params and not _is_valid_categories(params['categories']):
        params.pop('categories', None)

    # Convert boolean to lowercase string for isPrivatePlace and dry_run
    if isinstance(params.get('isPrivatePlace'), bool):
        params['isPrivatePlace'] = 'true' if params['isPrivatePlace'] else 'false'
    if isinstance(params.get('dry_run'), bool):
        params['dry_run'] = 'true' if params['dry_run'] else 'false'

    # Latitude/Longitude ensure basic types
    if 'latitude' in params:
        try:
            params['latitude'] = float(params['latitude'])
        except Exception:
            params.pop('latitude', None)
    if 'longitude' in params:
        try:
            params['longitude'] = float(params['longitude'])
        except Exception:
            params.pop('longitude', None)

    # Hours: strip whitespace and trailing semicolons
    if 'hours' in params:
        params['hours'] = str(params['hours']).strip().strip(';')

    return params


async def parse_search_query_gpt(user_input: str, current_params: dict | None = None) -> Any:
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
    parsed = llm.parse(
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
        response_format=FoursquareSearchParams,
    )
    return parsed


async def suggest_next_filters(params: dict) -> str:
    missing: list[str] = []
    if not params.get("radius"):
        missing.append("distance")
    if not params.get("open_now"):
        missing.append("open now")
    if not params.get("min_price"):
        missing.append("minimum price")
    if not params.get("max_price"):
        missing.append("maximum price")
    user_context: list[str] = []
    for k, v in params.items():
        if v is not None and v != "":
            user_context.append(f"{k}: {v}")
    gpt_prompt = f"""
        You are a friendly assistant helping a user search for places. The user has already set these filters: {', '.join(user_context) if user_context else 'none yet'}.
        The following filters are still missing: {', '.join(missing)}.
        In a natural, conversational way, ask the user if they want to specify any of these missing filters. Do not use a robotic or templated tone. Make it sound like a real human would ask in a chat.
        Keep it short and friendly. Don't use any emojis.
    """
    return llm.chat(
        temperature=1,
        messages=[
            {"role": "system", "content": "You are a helpful, friendly assistant."},
            {"role": "user", "content": gpt_prompt},
        ],
    )


async def parse_contact_info_gpt(user_input: str) -> Dict[str, Any]:
    user_prompt = f"""
        You are a helpful assistant. The user is entering contact details and social links in free text.
        Parse any of these fields you can find: phone, website, email, facebookUrl, instagram, twitter.
        If a field isn't provided, return an empty string for it.
        Set is_valid=false only if the content is clearly unrelated to contact/social information.

        User input: {user_input}
        """
    parsed = llm.parse(
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
        response_format=UserInputClassifier,
    )
    return {
        "is_valid": parsed.is_valid,
        "phone": parsed.phone,
        "website": parsed.website,
        "email": parsed.email,
        "facebookUrl": getattr(parsed, "facebookUrl", ""),
        "instagram": getattr(parsed, "instagram", ""),
        "twitter": getattr(parsed, "twitter", ""),
    }


async def parse_hours_info_gpt(user_input: str) -> Dict[str, Any]:
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
    response = llm.chat(
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
    )
    msg = json.loads(response)
    return {
        "is_valid": msg["is_valid"],
        "normalized_hours": msg["normalized_hours"],
        "explanation": msg["explanation"],
    }


async def parse_hours_to_api_gpt(user_input: str) -> Dict[str, Any]:
    user_prompt = f"""
        Convert the following operating hours into the Foursquare Places API hours string.
        Format: a semicolon-separated list of entries: day,start,end or day,start,end,label.
        Days: 1=Monday ... 7=Sunday. Times: HHMM 24-hour format. Prefix + if end time goes past midnight.
        Examples:
        - 24/7: 1,0000,2400;2,0000,2400;3,0000,2400;4,0000,2400;5,0000,2400;6,0000,2400;7,0000,2400

        Input: {user_input}

        Return valid JSON only with keys: {{"is_valid": <bool>, "hours": "<string or empty>", "explanation": "<string>"}}
    """
    response = llm.chat(
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
    )
    msg = json.loads(response)
    return {"is_valid": msg["is_valid"], "hours": msg["hours"], "explanation": msg["explanation"]}


async def parse_address_info_gpt(user_input: str) -> AddressParseResult:
    user_prompt = f"""
        You are parsing a place address from free text. Extract the following fields when possible:
        - address (street address)
        - locality (city)
        - region (state or province)
        - postcode (postal/zip code)
        - country_code (2-letter code like US, IN. You can extract the country code from the input if it is present.)
        If you are unsure, leave the field empty. Set is_valid=false only if the input clearly isn't an address.
        The country_code is also a mandatory field. If you are unable to extract the country code, set is_valid=false.

        Input: {user_input}
    """
    parsed = llm.parse(
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
        response_format=AddressParseResult,
    )
    return parsed


async def gpt_suggest_refine_prompt(params: dict) -> str:
    missing: list[str] = []
    if not params.get("radius"):
        missing.append("distance")
    if not params.get("open_now"):
        missing.append("open now")
    if not params.get("min_price"):
        missing.append("minimum price")
    if not params.get("max_price"):
        missing.append("maximum price")
    user_context: list[str] = []
    for k, v in params.items():
        if v is not None and v != "" and k != "query":
            user_context.append(f"{k}: {v}")
    gpt_prompt = f"""
        You are a friendly assistant helping a user search for places. The user has already set these filters: {', '.join(user_context) if user_context else 'none yet'}.
        The following filters are still missing: {', '.join(missing)}.
        In a natural, conversational way, suggest to the user that they can add any of these missing filters to narrow down the results, or say 'no' to finish. Do not use a robotic or templated tone. Make it sound like a real human would ask in a chat. Keep it short and friendly. Don't use any emojis.
    """
    return llm.chat(
        temperature=1,
        messages=[
            {"role": "system", "content": "You are a helpful, friendly assistant."},
            {"role": "user", "content": gpt_prompt},
        ],
    )


async def gpt_generate_results_header(params: dict) -> str:
    query = params.get("query", None)
    user_context: list[str] = []
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
    return llm.chat(
        temperature=1,
        messages=[
            {"role": "system", "content": "You are a helpful, friendly assistant."},
            {"role": "user", "content": gpt_prompt},
        ],
    )


# --- Category parsing helpers ---
async def parse_categories_gpt(user_input: str, valid_names: list[str]) -> list[str]:
    prompt = f"""
    Extract category-like terms from the user's message.
    - Output a comma-separated list of short category names or phrases present or clearly implied by the user input.
    - Keep names concise (1-3 words). Use only what the user said; do not invent unseen categories.
    - Normalize by removing emojis and extraneous punctuation.
    - Split combined phrases like 'bars and cafes' into 'bar, cafe'.
    - If nothing category-like is present, return an empty string.

    Reply with CSV only and no extra text.

    User input: {user_input}
    """
    raw = llm.chat(
        temperature=0,
        messages=[
            {"role": "system", "content": "You extract concise keywords and output CSV only."},
            {"role": "user", "content": prompt},
        ],
    )
    tokens = [t.strip().strip('"\'') for t in raw.split(',') if t.strip()]
    # Deduplicate while preserving order
    seen: set[str] = set()
    out: list[str] = []
    for t in tokens:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
    return out


# --- Coordinates parsing helper ---
async def parse_coordinates_gpt(user_input: str) -> Dict[str, Any]:
    user_prompt = f"""
        Extract latitude and longitude from the input. The user will provide comma-separated values.
        Return strict JSON with keys: {{"is_valid": <bool>, "latitude": <float or null>, "longitude": <float or null>, "explanation": "<string>"}}.
        - Accept variations like spaces or labels (e.g., "lat: 12.34, lng: 56.78").
        - Validate ranges (lat: -90..90, lng: -180..180). If out of range, set is_valid=false.

        Input: {user_input}
    """
    response = llm.chat(
        messages=[
            {"role": "system", "content": "You are a parsing assistant."},
            {"role": "user", "content": user_prompt},
        ],
    )
    try:
        msg = json.loads(response)
    except Exception:
        msg = {"is_valid": False, "latitude": None, "longitude": None, "explanation": "Failed to parse"}
    return msg


async def do_foursquare_search(update: Update, context: ContextTypes.DEFAULT_TYPE, ask_refine: bool = False) -> int:
    ensure_request_id(update, context)
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    location = context.user_data.get("location")
    if not isinstance(location, dict):
        logger.warning(
            "foursquare search attempted without location",
            extra=build_log_extra(update, context, module_name="search", operation="do_foursquare_search"),
        )
        await update.message.reply_text("Please share your location first by sending /start.")
        return LOCATION

    try:
        lat = float(location.get("latitude"))
        lng = float(location.get("longitude"))
    except (TypeError, ValueError):
        logger.warning(
            "invalid location stored for user",
            extra=build_log_extra(update, context, module_name="search", operation="do_foursquare_search", location=location),
        )
        await update.message.reply_text("Your location looks invalid. Please share it again with /start.")
        return LOCATION

    search_params: dict = context.user_data.get("search_params", {})
    fields = "fsq_place_id,name,distance,hours,price,rating"

    request_params: Dict[str, Any] = {}
    if search_params.get("query"):
        request_params["query"] = search_params["query"]
    request_params["limit"] = search_params.get("limit") or 5
    if search_params.get("open_now"):
        request_params["open_now"] = "true"
    if search_params.get("radius"):
        request_params["radius"] = search_params["radius"]
    if search_params.get("fsq_category_ids"):
        request_params["fsq_category_ids"] = search_params["fsq_category_ids"]
    if search_params.get("min_price"):
        request_params["min_price"] = search_params["min_price"]
    if search_params.get("max_price"):
        request_params["max_price"] = search_params["max_price"]

    logger.info(
        "foursquare search request",
        extra=build_log_extra(
            update,
            context,
            module_name="search",
            operation="do_foursquare_search",
            request_params=request_params,
            coordinates={"latitude": lat, "longitude": lng},
        ),
    )

    try:
        data = fsq.search(ll=f"{lat},{lng}", fields=fields, params=request_params)
        results = data.get("results", [])
        logger.info(
            "foursquare search response",
            extra=build_log_extra(
                update,
                context,
                module_name="search",
                operation="do_foursquare_search",
                results_count=len(results),
            ),
        )
        # Log a concise preview of results
        try:
            preview = []
            for p in results[:10]:
                preview.append({
                    "id": p.get("fsq_place_id"),
                    "name": p.get("name"),
                    "distance": p.get("distance"),
                    "rating": p.get("rating"),
                    "price": p.get("price"),
                    "open_now": (p.get("hours", {}).get("open_now") if isinstance(p.get("hours"), dict) else None),
                })
            logger.info(
                "foursquare search results preview",
                extra=build_log_extra(
                    update,
                    context,
                    module_name="search",
                    operation="do_foursquare_search",
                    results_preview=preview,
                ),
            )
        except Exception:
            logger.info(
                "foursquare search results preview",
                extra=build_log_extra(update, context, module_name="search", operation="do_foursquare_search"),
            )

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

        for place in results:
            fsq_id = place.get("fsq_place_id")
            if not fsq_id:
                place["image_url"] = None
                continue
            try:
                photo_list = fsq.photos(fsq_id)
                try:
                    photos_count = len(photo_list) if isinstance(photo_list, list) else 0
                    logger.info(
                        "fsq photos fetched",
                        extra=build_log_extra(
                            update,
                            context,
                            module_name="search",
                            operation="do_foursquare_search",
                            fsq_id=fsq_id,
                            photos_count=photos_count,
                        ),
                    )
                except Exception:
                    logger.info(
                        "fsq photos fetched",
                        extra=build_log_extra(
                            update,
                            context,
                            module_name="search",
                            operation="do_foursquare_search",
                            fsq_id=fsq_id,
                        ),
                    )
                if isinstance(photo_list, list) and len(photo_list) > 0:
                    photo = photo_list[0]
                    prefix = photo.get("prefix", "")
                    suffix = photo.get("suffix", "")
                    width = photo.get("width", 300)
                    height = photo.get("height", 225)
                    target_w = 300
                    target_h = int((target_w / width) * height) if width and height else 225
                    image_url = f"{prefix}{target_w}x{target_h}{suffix}"
                    place["image_url"] = image_url
                else:
                    place["image_url"] = None
            except Exception:
                try:
                    logger.info(
                        "fsq photos fetch failed",
                        extra=build_log_extra(
                            update,
                            context,
                            module_name="search",
                            operation="do_foursquare_search",
                            fsq_id=fsq_id,
                        ),
                    )
                except Exception:
                    pass
                place["image_url"] = None

        if not results:
            await update.message.reply_text("No places found with your filters. Type a new query or /start to try again.")
            return QUERY

        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        header = await gpt_generate_results_header(search_params)
        lines: list[str] = []
        for place in results:
            name = place.get("name", "Unknown")
            dist = place.get("distance", "N/A")
            rating = place.get("rating", None)
            if rating is not None and rating != "":
                rating_str = f"{rating}/10 ⭐"
            else:
                rating_str = "N/A"
            price = place.get("price", None)
            if price is not None and price != "":
                try:
                    price_int = int(price)
                    price_str = f"<b>{'$' * price_int}</b>"
                except Exception:
                    price_str = "N/A"
            else:
                price_str = "N/A"
            open_now = place.get("hours", {}).get("open_now", None)
            if open_now is True:
                open_str = "<b>Open Now</b>"
            elif open_now is False:
                open_str = "<b>Currently Closed!</b>"
            else:
                open_str = "N/A"
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

        places_json = json.dumps(results)
        places_b64 = base64.urlsafe_b64encode(places_json.encode()).decode()
        external_base = discover_external_base_url(max_wait_seconds=1)
        webapp_url = f"{external_base}/?data={places_b64}"
        keyboard = [[InlineKeyboardButton("Open List View", url=webapp_url)]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "Want to see these results in a beautiful list view? Tap below!",
            reply_markup=reply_markup,
        )

        if ask_refine:
            await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
            refine_prompt = await gpt_suggest_refine_prompt(search_params)
            await update.message.reply_text(refine_prompt)
            return REFINE
        return QUERY
    except Exception as e:
        logger.error(
            "foursquare search failed",
            extra=build_log_extra(update, context, module_name="search", operation="do_foursquare_search"),
            exc_info=True,
        )
        await update.message.reply_text(f"Error: {e}")
        return QUERY


async def gpt_refine_intent(user_message: str) -> bool:
    prompt = f"""
    The user is interacting with a place search assistant. They just saw a list of results and were prompted to add more filters or say 'no' to finish. 
    Classify the user's message as either:
    - 'end' (if they want to stop, are satisfied, or say things like 'no', 'that's all', 'I'm done', 'stop', etc.)
    - 'refine' (if they want to add more filters, change the search, or anything else)
    Only reply with 'end' or 'refine'.
    
    User message: {user_message}
    """
    result = llm.chat(
        messages=[
            {"role": "system", "content": "You are a helpful assistant that classifies user intent."},
            {"role": "user", "content": prompt},
        ],
    ).lower()
    return result == "end"


async def web_app_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        data = json.loads(update.effective_message.web_app_data.data)
        await update.message.reply_html(
            text=(
                f"New place added successfully!\n\n"
                f"Name: {data.get('name', 'N/A')}\n"
                f"Category: {data.get('category', 'N/A')}\n"
                f"Address: {data.get('address', 'N/A')}"
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
        logger.info(
            "webapp data processed",
            extra=build_log_extra(update, context, module_name="webapp", operation="web_app_data", fields_present=list(data.keys())),
        )
    except json.JSONDecodeError:
        await update.message.reply_text(
            "Sorry, there was an error processing the data.",
            reply_markup=ReplyKeyboardRemove(),
        )


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    set_new_request_id(update, context)
    logger.info("/start received", extra=build_log_extra(update, context, module_name="conversation", operation="start"))
    keyboard = [[KeyboardButton("Share Location 📍", request_location=True)]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Welcome to the Conversational Place Search Bot!\n\nPlease share your location to continue.",
        reply_markup=reply_markup,
    )
    return LOCATION


async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ensure_request_id(update, context)
    user_location = update.message.location
    context.user_data['location'] = {
        'latitude': user_location.latitude,
        'longitude': user_location.longitude,
    }
    context.user_data['search_params'] = {}
    logger.info(
        "location received",
        extra=build_log_extra(update, context, module_name="conversation", operation="location_handler", latitude=user_location.latitude, longitude=user_location.longitude),
    )

    # Build map URL with user's lat/lon parameters
    from urllib.parse import urlencode
    map_params = {
        'lat': user_location.latitude,
        'lon': user_location.longitude,
        'dtype_out_raster': 'png',
        'dtype_out_vector': 'html'
    }
    map_url = f"https://staging.fused.io/server/v1/realtime-shared/fsh_gUEEDC5FXKza2P19Kpizm/run/file?{urlencode(map_params)}"

    keyboard = [
        [KeyboardButton("Search Foursquare data")],
        [KeyboardButton("Add a new place")],
        [KeyboardButton(
            text="Explore the foursquare location data",
            web_app=WebAppInfo(
                url=map_url,
            ),
        )],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "Location received!\n"
        "What would you like to do?\n\n"
        "1. Search Foursquare data\n"
        "2. Add a new place\n"
        "3. Explore the Foursquare Data on the Map",
        reply_markup=reply_markup,
    )
    return LOCATION_CHOICE


async def query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ensure_request_id(update, context)
    user_query = update.message.text.strip()
    logger.info("query received", extra=build_log_extra(update, context, module_name="search", operation="query_handler", user_query=user_query))
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    current_params = context.user_data.get('search_params', {})
    gpt_result = await parse_search_query_gpt(user_query, current_params)
    # Log GPT parsed output for debugging
    try:
        logger.info("gpt parsed search params", extra=build_log_extra(update, context, module_name="search", operation="query_handler", gpt_parsed=gpt_result.model_dump()))
    except Exception:
        logger.info("gpt parsed search params", extra=build_log_extra(update, context, module_name="search", operation="query_handler"))
    params = current_params.copy()
    for k, v in gpt_result.model_dump().items():
        if v is not None and v != "":
            params[k] = v
    context.user_data['search_params'] = params
    logger.info("search params updated", extra=build_log_extra(update, context, module_name="search", operation="query_handler", params=params))
    return await do_foursquare_search(update, context, ask_refine=True)


async def refine_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ensure_request_id(update, context)
    user_text = update.message.text.strip()
    try:
        logger.info(
            "refine raw received",
            extra=build_log_extra(update, context, module_name="search", operation="refine_handler", raw=user_text),
        )
    except Exception:
        logger.info("refine raw received", extra=build_log_extra(update, context, module_name="search", operation="refine_handler"))
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)

    if await gpt_refine_intent(user_text):
        logger.info("refine done", extra=build_log_extra(update, context, module_name="search", operation="refine_handler", decision="end"))
        await update.message.reply_text("Okay! If you want to start a new search, just type your query or /start.")
        return ConversationHandler.END
    else:
        logger.info("refine continue", extra=build_log_extra(update, context, module_name="search", operation="refine_handler", decision="refine"))
        return await query_handler(update, context)


async def location_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    ensure_request_id(update, context)
    user_text = update.message.text.strip().lower()
    logger.info("location menu choice", extra=build_log_extra(update, context, module_name="conversation", operation="location_choice_handler", choice=user_text))

    if "search foursquare data" in user_text:
        await update.message.reply_text(
            "Great! What are you looking for? (e.g. 'I'm craving sushi', 'Find a burger', etc.)",
            reply_markup=ReplyKeyboardRemove(),
        )
        return QUERY
    elif "add a new place" in user_text:
        await update.message.reply_text(
            "Great! First, what's the place called?",
            reply_markup=ReplyKeyboardRemove(),
        )
        return NAME
    else:
        await update.message.reply_text("Please select a valid option from the menu.")
        return LOCATION_CHOICE


async def name_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text.strip()
    try:
        logger.info(
            "name received",
            extra=build_log_extra(update, context, module_name="new_place", operation="name_handler", name=context.user_data['name']),
        )
    except Exception:
        logger.info("name received", extra=build_log_extra(update, context, module_name="new_place", operation="name_handler"))
    prompt = (
        "Now, add one or more categories this place fits in (comma-separated). "
        "Use natural names like 'Arcade, Aquarium'. You can /skip if unsure.\n\n"
        f"If you need help, refer to valid categories here: <a href=\"{_FSQ_CATEGORIES_DOCS_URL}\">link</a>"
    )
    await update.message.reply_text(
        prompt,
        reply_markup=ReplyKeyboardRemove(),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    return CATEGORY


async def category_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip()
    try:
        logger.info(
            "category raw received",
            extra=build_log_extra(update, context, module_name="new_place", operation="category_handler", raw=text),
        )
    except Exception:
        logger.info("category raw received", extra=build_log_extra(update, context, module_name="new_place", operation="category_handler"))
    if text.lower().startswith("/skip") or text.lower() == "skip":
        context.user_data['categories_ids'] = ""
        context.user_data['categories_names'] = []
        await update.message.reply_text(
            "What's the address? Please paste the full address, including the country code.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ADDRESS

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    # Parse categories via GPT to normalized names from the allowed list
    try:
        parsed_names = await parse_categories_gpt(text, _CATEGORY_VALID_NAMES)
        try:
            logger.info(
                "gpt parsed categories",
                extra=build_log_extra(update, context, module_name="new_place", operation="category_handler", gpt_parsed=parsed_names),
            )
        except Exception:
            logger.info("gpt parsed categories", extra=build_log_extra(update, context, module_name="new_place", operation="category_handler"))
    except Exception:
        parsed_names = [t.strip() for t in text.split(',') if t.strip()]

    # Validate against mapping (case-insensitive)
    unknown: list[str] = []
    mapped_ids: list[str] = []
    accepted_names: list[str] = []
    for name in parsed_names:
        key = name.strip().lower()
        if key in _CATEGORY_KEY_LOWER_TO_ID:
            mapped_ids.append(_CATEGORY_KEY_LOWER_TO_ID[key])
            # Use canonical display name from the file for summary
            accepted_names.append(next(k for k in _CATEGORY_NAME_TO_ID.keys() if k.lower() == key))
        else:
            unknown.append(name)

    try:
        logger.info(
            "category mapping result",
            extra=build_log_extra(update, context, module_name="new_place", operation="category_handler", mapped_ids=mapped_ids, accepted_names=accepted_names, unknown=unknown),
        )
    except Exception:
        logger.info("category mapping result", extra=build_log_extra(update, context, module_name="new_place", operation="category_handler"))

    if unknown or not mapped_ids:
        msg_parts = []
        if unknown:
            msg_parts.append("I couldn't find these categories: " + ", ".join(unknown))
        msg_parts.append(f"Refer to this <a href=\"{_FSQ_CATEGORIES_DOCS_URL}\">link</a> for valid categories.")
        await update.message.reply_text(
            "\n".join(msg_parts),
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return CATEGORY

    context.user_data['categories_ids'] = ",".join(mapped_ids)
    context.user_data['categories_names'] = accepted_names

    await update.message.reply_text(
        "What's the address? Please paste the full address, including the country code.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ADDRESS


async def address_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()
    try:
        logger.info(
            "address raw received",
            extra=build_log_extra(update, context, module_name="new_place", operation="address_handler", raw=user_text),
        )
    except Exception:
        logger.info("address raw received", extra=build_log_extra(update, context, module_name="new_place", operation="address_handler"))
    lowered = user_text.lower()
    if not user_text or lowered.startswith("/skip") or lowered == "skip":
        await update.message.reply_text(
            "An address is required to add a new place. Please provide the full address, including the country code.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ADDRESS

    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    parsed = await parse_address_info_gpt(user_text)
    # Log GPT parsed output
    try:
        logger.info("gpt parsed address", extra=build_log_extra(update, context, module_name="new_place", operation="address_handler", gpt_parsed=parsed.model_dump()))
    except Exception:
        logger.info("gpt parsed address", extra=build_log_extra(update, context, module_name="new_place", operation="address_handler"))
    if not parsed.is_valid:
        await update.message.reply_text(
            "Hmm, that didn't look like a valid address. Please try again with the full address, including the country code.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ADDRESS
    context.user_data['address_fields'] = {
        'address': parsed.address,
        'locality': parsed.locality,
        'region': parsed.region,
        'postcode': parsed.postcode,
        'country_code': parsed.country_code,
    }
    try:
        logger.info(
            "address structured stored",
            extra=build_log_extra(update, context, module_name="new_place", operation="address_handler", address_fields=context.user_data['address_fields']),
        )
    except Exception:
        logger.info("address structured stored", extra=build_log_extra(update, context, module_name="new_place", operation="address_handler"))
    # Ask for coordinates preference
    keyboard = [
        [KeyboardButton("Use my current location")],
        [KeyboardButton("Enter coordinates")],
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        "We also need the coordinates. Share your current location or enter latitude,longitude manually.",
        reply_markup=reply_markup,
    )
    return COORDINATES


async def coordinates_choice_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    try:
        logger.info(
            "coordinates choice received",
            extra=build_log_extra(update, context, module_name="new_place", operation="coordinates_choice_handler", choice=text),
        )
    except Exception:
        logger.info("coordinates choice received", extra=build_log_extra(update, context, module_name="new_place", operation="coordinates_choice_handler"))

    if text in {"use my current location", "use my location"}:
        location = context.user_data.get('location', {})
        if not isinstance(location, dict) or location.get('latitude') is None or location.get('longitude') is None:
            await update.message.reply_text(
                "I couldn't find your location. Please enter the coordinates manually (latitude,longitude).",
                reply_markup=ReplyKeyboardRemove(),
            )
            return COORDINATES_MANUAL
        context.user_data['coordinates_source'] = 'current'
        context.user_data['coordinates'] = {
            'latitude': location.get('latitude'),
            'longitude': location.get('longitude'),
        }
        await update.message.reply_text(
            "Any contact or social links? Send anything (phone, website, email, Instagram...) or /skip.",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CONTACT
    if text in {"enter coordinates", "enter coordinate", "enter"}:
        await update.message.reply_text(
            "Please enter latitude,longitude (e.g., 12.9716,77.5946).",
            reply_markup=ReplyKeyboardRemove(),
        )
        return COORDINATES_MANUAL
    if text in {"skip", "/skip"}:
        await update.message.reply_text(
            "Coordinates are required. Please share your current location or enter latitude,longitude manually.",
            reply_markup=ReplyKeyboardMarkup(
                [
                    [KeyboardButton("Use my current location")],
                    [KeyboardButton("Enter coordinates")],
                ],
                resize_keyboard=True,
            ),
        )
        return COORDINATES

    await update.message.reply_text("Please choose one of the options to provide coordinates.")
    return COORDINATES


async def coordinates_manual_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()
    try:
        logger.info(
            "coordinates raw received",
            extra=build_log_extra(update, context, module_name="new_place", operation="coordinates_manual_handler", raw=user_text),
        )
    except Exception:
        logger.info("coordinates raw received", extra=build_log_extra(update, context, module_name="new_place", operation="coordinates_manual_handler"))
    if user_text.lower() in {"/skip", "skip"}:
        choice_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("Use my current location")],
                [KeyboardButton("Enter coordinates")],
            ],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            "Coordinates are required. Share your current location or enter latitude,longitude manually.",
            reply_markup=choice_keyboard,
        )
        return COORDINATES
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    parsed = await parse_coordinates_gpt(user_text)
    try:
        logger.info(
            "gpt parsed coordinates",
            extra=build_log_extra(update, context, module_name="new_place", operation="coordinates_manual_handler", gpt_parsed=parsed),
        )
    except Exception:
        logger.info("gpt parsed coordinates", extra=build_log_extra(update, context, module_name="new_place", operation="coordinates_manual_handler"))

    is_valid = bool(parsed.get("is_valid"))
    lat = parsed.get("latitude")
    lng = parsed.get("longitude")
    if not is_valid or lat is None or lng is None:
        choice_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("Use my current location")],
                [KeyboardButton("Enter coordinates")],
            ],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            "Couldn't parse coordinates. Choose an option below or try entering them again as latitude,longitude (e.g., 12.9716,77.5946).",
            reply_markup=choice_keyboard,
        )
        return COORDINATES
    try:
        lat_f = float(lat)
        lng_f = float(lng)
        if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lng_f <= 180.0):
            raise ValueError("out of range")
    except Exception:
        choice_keyboard = ReplyKeyboardMarkup(
            [
                [KeyboardButton("Use my current location")],
                [KeyboardButton("Enter coordinates")],
            ],
            resize_keyboard=True,
        )
        await update.message.reply_text(
            "Coordinates out of range. Choose an option below or try entering them again.",
            reply_markup=choice_keyboard,
        )
        return COORDINATES

    context.user_data['coordinates_source'] = 'manual'
    context.user_data['coordinates'] = {'latitude': lat_f, 'longitude': lng_f}
    await update.message.reply_text(
        "Any contact or social links? Send anything (phone, website, email, Instagram...) or /skip.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return CONTACT


async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()
    try:
        logger.info(
            "contact raw received",
            extra=build_log_extra(update, context, module_name="new_place", operation="contact_handler", raw=user_text),
        )
    except Exception:
        logger.info("contact raw received", extra=build_log_extra(update, context, module_name="new_place", operation="contact_handler"))
    if user_text.lower() in {"skip", "/skip"}:
        context.user_data["contact"] = {}
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        result = await parse_contact_info_gpt(user_text)
        # Log GPT parsed output
        try:
            logger.info("gpt parsed contact", extra=build_log_extra(update, context, module_name="new_place", operation="contact_handler", gpt_parsed=result))
        except Exception:
            logger.info("gpt parsed contact", extra=build_log_extra(update, context, module_name="new_place", operation="contact_handler"))
        if not result["is_valid"]:
            await update.message.reply_text(
                "Couldn't parse that. Try again or /skip."
            )
            return CONTACT
        context.user_data["contact"] = {
            "phone": result.get("phone", ""),
            "website": result.get("website", ""),
            "email": result.get("email", ""),
            "facebookUrl": result.get("facebookUrl", ""),
            "instagram": result.get("instagram", ""),
            "twitter": result.get("twitter", ""),
        }
        try:
            logger.info(
                "contact structured stored",
                extra=build_log_extra(update, context, module_name="new_place", operation="contact_handler", contact=context.user_data["contact"]),
            )
        except Exception:
            logger.info("contact structured stored", extra=build_log_extra(update, context, module_name="new_place", operation="contact_handler"))
    keyboard = [[KeyboardButton("Open 24/7")], [KeyboardButton("Custom Hours")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("What are the hours?", reply_markup=reply_markup)
    return HOURS


async def hours_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_choice = update.message.text.strip().lower()
    try:
        logger.info(
            "hours choice received",
            extra=build_log_extra(update, context, module_name="new_place", operation="hours_handler", choice=user_choice),
        )
    except Exception:
        logger.info("hours choice received", extra=build_log_extra(update, context, module_name="new_place", operation="hours_handler"))
    if user_choice.startswith("/skip") or user_choice == "skip":
        context.user_data["hours_api"] = ""
        # Skip chains, go directly to attributes
        reply_markup = _build_attributes_keyboard()
        await update.message.reply_text(
            "Pick any attributes (tap Done when finished).",
            reply_markup=reply_markup,
        )
        return ATTRIBUTES
    if "open 24/7" in user_choice:
        hours_247 = ";".join([f"{day},0000,2400" for day in range(1, 8)])
        context.user_data["hours_api"] = hours_247
        reply_markup = _build_attributes_keyboard()
        await update.message.reply_text(
            "Pick any attributes (tap Done when finished).",
            reply_markup=reply_markup,
        )
        return ATTRIBUTES
    elif "custom hours" in user_choice:
        await update.message.reply_text(
            "Type the hours in your own words (e.g. Mon-Fri 9am-6pm).",
            reply_markup=ReplyKeyboardRemove(),
        )
        return CUSTOM_HOURS


async def custom_hours_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_text = update.message.text.strip()
    try:
        logger.info(
            "custom hours raw received",
            extra=build_log_extra(update, context, module_name="new_place", operation="custom_hours_handler", raw=user_text),
        )
    except Exception:
        logger.info("custom hours raw received", extra=build_log_extra(update, context, module_name="new_place", operation="custom_hours_handler"))
    if user_text.lower() in {"/skip", "skip"}:
        context.user_data["hours_api"] = ""
    else:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
        parsed = await parse_hours_to_api_gpt(user_text)
        # Log GPT parsed output
        try:
            logger.info("gpt parsed hours", extra=build_log_extra(update, context, module_name="new_place", operation="custom_hours_handler", gpt_parsed=parsed))
        except Exception:
            logger.info("gpt parsed hours", extra=build_log_extra(update, context, module_name="new_place", operation="custom_hours_handler"))
        if not parsed["is_valid"] or not parsed["hours"]:
            await update.message.reply_text(
                "Couldn't parse those hours. Try again, or /skip."
            )
            return CUSTOM_HOURS
        context.user_data["hours_api"] = parsed["hours"]
    # Skip chains, go directly to attributes
    reply_markup = _build_attributes_keyboard()
    await update.message.reply_text("Pick any attributes (tap Done when finished).", reply_markup=reply_markup)
    return ATTRIBUTES 


async def chain_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Deprecated: chains flow is skipped
    query = update.callback_query
    await query.answer()
    reply_markup = _build_attributes_keyboard()
    await query.message.reply_text(
        "Pick any attributes (tap Done when finished).",
        reply_markup=reply_markup,
    )
    return ATTRIBUTES


async def chain_details_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # Deprecated: chains flow is skipped
    reply_markup = _build_attributes_keyboard()
    await update.message.reply_text(
        "Pick any attributes (tap Done when finished).",
        reply_markup=reply_markup,
    )
    return ATTRIBUTES


_ATTR_MAP = {
    "ATM 🏧": "atm",
    "Reservations 📅": "reservation",
    "Delivery 🚚": "offers_delivery",
    "Parking 🅿️": "parking",
    "Outdoor Seating 🪑": "outdoor_seating",
    "Restroom 🚻": "restroom",
    "Credit Cards 💳": "credit_cards",
    "WiFi 📶": "wifi",
}


async def attributes_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.message.text == "Done ✅":
        tokens = []
        for label in context.user_data.get('attributes', []):
            mapped = _ATTR_MAP.get(label)
            if mapped:
                tokens.append(mapped)
        context.user_data['attributes_tokens'] = tokens
        try:
            logger.info(
                "attributes finalized",
                extra=build_log_extra(update, context, module_name="new_place", operation="attributes_handler", attributes_tokens=tokens),
            )
        except Exception:
            logger.info("attributes finalized", extra=build_log_extra(update, context, module_name="new_place", operation="attributes_handler"))
        keyboard = [[KeyboardButton("Yes"), KeyboardButton("No")]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text("Is it a private place? (Yes/No) or /skip", reply_markup=reply_markup)
        return PRIVATE_PLACE

    if 'attributes' not in context.user_data:
        context.user_data['attributes'] = []
    context.user_data['attributes'].append(update.message.text)
    try:
        logger.info(
            "attribute selected",
            extra=build_log_extra(update, context, module_name="new_place", operation="attributes_handler", selected_label=update.message.text),
        )
    except Exception:
        logger.info("attribute selected", extra=build_log_extra(update, context, module_name="new_place", operation="attributes_handler"))
    return ATTRIBUTES


async def private_place_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    text = update.message.text.strip().lower()
    try:
        logger.info(
            "private place input",
            extra=build_log_extra(update, context, module_name="new_place", operation="private_place_handler", raw=text),
        )
    except Exception:
        logger.info("private place input", extra=build_log_extra(update, context, module_name="new_place", operation="private_place_handler"))
    if text in {"/skip", "skip"}:
        context.user_data['is_private'] = None
    elif text in {"yes", "y"}:
        context.user_data['is_private'] = True
    elif text in {"no", "n"}:
        context.user_data['is_private'] = False
    else:
        await update.message.reply_text("Please reply Yes, No, or /skip.")
        return PRIVATE_PLACE
    return await confirm_data(update, context)


async def photos_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if 'photos' not in context.user_data:
        context.user_data['photos'] = []

    if update.message.photo:
        context.user_data['photos'].append(update.message.photo[-1].file_id)
        try:
            logger.info(
                "photo received",
                extra=build_log_extra(update, context, module_name="new_place", operation="photos_handler", count=len(context.user_data['photos'])),
            )
        except Exception:
            logger.info("photo received", extra=build_log_extra(update, context, module_name="new_place", operation="photos_handler"))
        if len(context.user_data['photos']) >= 3:
            return await confirm_data(update, context)
        await update.message.reply_text(
            f"Photo {len(context.user_data['photos'])} received! "
            "Send another or type /done when finished."
        )
        return PHOTOS

    if update.message.text == "/skip" or update.message.text == "/done":
        try:
            logger.info(
                "photos stage skipped or done",
                extra=build_log_extra(update, context, module_name="new_place", operation="photos_handler"),
            )
        except Exception:
            logger.info("photos stage skipped or done", extra=build_log_extra(update, context, module_name="new_place", operation="photos_handler"))
        return await confirm_data(update, context)

    return PHOTOS


async def confirm_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    data = context.user_data
    address_fields = data.get('address_fields', {})
    contact = data.get('contact', {})
    attributes_tokens = data.get('attributes_tokens', [])

    try:
        logger.info(
            "confirm summary generated",
            extra=build_log_extra(update, context, module_name="new_place", operation="confirm_data", name=data.get('name', ''), categories=data.get('categories_names', []), has_hours=bool(data.get('hours_api')), is_private=data.get('is_private')),
        )
    except Exception:
        logger.info("confirm summary generated", extra=build_log_extra(update, context, module_name="new_place", operation="confirm_data"))

    lines = [
        "📍 Place Summary:",
        f"Name: {data.get('name', '')}",
    ]
    if data.get('categories_names'):
        lines.append("Categories: " + ", ".join(data.get('categories_names')))
    if address_fields:
        lines.append(
            f"Address: {address_fields.get('address', '')}, {address_fields.get('locality', '')} {address_fields.get('region', '')} {address_fields.get('postcode', '')} {address_fields.get('country_code', '')}".strip()
        )
    if contact:
        c_bits = [
            contact.get('phone', ''),
            contact.get('website', ''),
            contact.get('email', ''),
            contact.get('instagram', ''),
            contact.get('facebookUrl', ''),
            contact.get('twitter', ''),
        ]
        lines.append("Contact: " + ", ".join([b for b in c_bits if b]))
    if data.get('hours_api'):
        lines.append("Hours: set")
    if attributes_tokens:
        lines.append("Attributes: " + ", ".join(attributes_tokens))
    if data.get('is_private') is not None:
        lines.append("Private: Yes" if data.get('is_private') else "Private: No")

    confirmation_text = "\n".join(lines + ["", "Is this information correct?"])
    keyboard = [[InlineKeyboardButton("Yes, Submit ✅", callback_data="confirm_yes"), InlineKeyboardButton("No, Edit ✏️", callback_data="confirm_no")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(confirmation_text, reply_markup=reply_markup)
    return CONFIRM


async def handle_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "confirm_yes":
        # Build params for suggest endpoint
        data = context.user_data
        address_fields = data.get('address_fields', {})
        contact = data.get('contact', {})

        params: Dict[str, Any] = {}
        params['name'] = data.get('name', '')
        if data.get('categories_ids'):
            params['categories'] = data.get('categories_ids')
        if address_fields:
            for key in ['address', 'locality', 'region', 'postcode', 'country_code']:
                if address_fields.get(key):
                    params[key] = address_fields.get(key)
        # Coordinates: only include if user opted in
        coords_src = data.get('coordinates_source')
        if coords_src == 'manual' and isinstance(data.get('coordinates'), dict):
            params['latitude'] = data['coordinates'].get('latitude')
            params['longitude'] = data['coordinates'].get('longitude')
        elif coords_src == 'current':
            lat = context.user_data.get('location', {}).get('latitude')
            lng = context.user_data.get('location', {}).get('longitude')
            if lat is not None and lng is not None:
                params['latitude'] = lat
                params['longitude'] = lng
        if data.get('is_private') is not None:
            params['isPrivatePlace'] = data.get('is_private')
        if contact:
            if contact.get('phone'):
                params['tel'] = contact.get('phone')
            if contact.get('website'):
                params['website'] = contact.get('website')
            if contact.get('email'):
                params['email'] = contact.get('email')
            if contact.get('facebookUrl'):
                params['facebookUrl'] = contact.get('facebookUrl')
            if contact.get('instagram'):
                params['instagram'] = contact.get('instagram')
            if contact.get('twitter'):
                params['twitter'] = contact.get('twitter')
        if data.get('hours_api'):
            params['hours'] = data.get('hours_api')
        if data.get('attributes_tokens'):
            params['attributes'] = ",".join(data.get('attributes_tokens'))
        params['dry_run'] = False

        safe_params = _sanitize_suggest_params(params)
        logger.info("suggest params (sanitized)", extra=build_log_extra(update, context, module_name="new_place", operation="handle_confirmation", suggest_params=safe_params))

        try:
            await context.bot.send_chat_action(chat_id=query.message.chat.id, action=ChatAction.TYPING)
            resp = fsq.suggest_place(safe_params)
            try:
                logger.info(
                    "suggest place success",
                    extra=build_log_extra(update, context, module_name="new_place", operation="handle_confirmation", response=resp),
                )
            except Exception:
                logger.info("suggest place success", extra=build_log_extra(update, context, module_name="new_place", operation="handle_confirmation"))
            await query.message.reply_text(
                "Your request for a new place has been accepted successfully!\n\nStart a new conversation by typing\n/start",
                reply_markup=ReplyKeyboardRemove(),
            )
        except Exception as e:
            # Try to log server response if available
            response_text = ""
            try:
                import requests
                if isinstance(e, requests.HTTPError) and e.response is not None:
                    response_text = e.response.text
            except Exception:
                pass
            logger.error(
                "suggest place failed",
                extra=build_log_extra(update, context, module_name="new_place", operation="handle_confirmation", error=str(e), response_text=response_text),
                exc_info=True,
            )
            msg = "Your request for a new place could not be processed. Please try again later."
            await query.message.reply_text(
                msg,
                reply_markup=ReplyKeyboardRemove(),
            )
        return ConversationHandler.END
    else:
        try:
            logger.info(
                "confirmation denied by user",
                extra=build_log_extra(update, context, module_name="new_place", operation="handle_confirmation"),
            )
        except Exception:
            logger.info("confirmation denied by user", extra=build_log_extra(update, context, module_name="new_place", operation="handle_confirmation"))
        await query.message.reply_text(
            "Okay, let's start over. Please type /start again",
            reply_markup=ReplyKeyboardRemove(),
        )
        return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        logger.info(
            "conversation cancelled by user",
            extra=build_log_extra(update, context, module_name="conversation", operation="cancel"),
        )
    except Exception:
        logger.info("conversation cancelled by user", extra=build_log_extra(update, context, module_name="conversation", operation="cancel"))
    await update.message.reply_text(
        "Operation cancelled. Type /start to begin again.",
        reply_markup=ReplyKeyboardRemove(),
    )
    return ConversationHandler.END 
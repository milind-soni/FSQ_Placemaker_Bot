import asyncio
import threading

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
)

from .config import settings
from .logging import setup_logging
from .telegram_handlers import (
    start,
    web_app_data,
    location_handler,
    location_choice_handler,
    query_handler,
    refine_handler,
    name_handler,
    category_handler,
    address_handler,
    coordinates_choice_handler,
    coordinates_manual_handler,
    contact_handler,
    hours_handler,
    custom_hours_handler,
    # chain_status_handler,  # removed from flow
    # chain_details_handler, # removed from flow
    attributes_handler,
    private_place_handler,
    photos_handler,
    handle_confirmation,
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
    CHAIN_STATUS,
    CHAIN_DETAILS,
    ATTRIBUTES,
    PRIVATE_PLACE,
    PHOTOS,
    CONFIRM,
    cancel,
)
from .utils import discover_external_base_url
from .web_server import create_app


logger = setup_logging()


class ConfigurationError(RuntimeError):
    """Raised when critical configuration is missing."""


def run_flask_app(flask_app) -> None:
    """
    Start the Flask webhook server inside a dedicated daemon thread.

    The main thread remains free to continue running the asyncio event loop
    that powers the Telegram application.
    """
    flask_app.run(host="0.0.0.0", port=settings.webapp_port, debug=False)


def _validate_required_settings() -> None:
    missing: list[str] = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if missing:
        raise ConfigurationError(
            "Missing required environment variables: " + ", ".join(sorted(missing))
        )


def _build_conversation_handler() -> ConversationHandler:
    skip_cmd = filters.Regex(r"^/skip$")

    return ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            LOCATION: [
                MessageHandler(filters.LOCATION, location_handler),
                MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data),
            ],
            LOCATION_CHOICE: [MessageHandler(filters.TEXT & ~filters.COMMAND, location_choice_handler)],
            QUERY: [MessageHandler(filters.TEXT & ~filters.COMMAND, query_handler)],
            REFINE: [MessageHandler(filters.TEXT & ~filters.COMMAND, refine_handler)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, name_handler)],
            CATEGORY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, category_handler),
                MessageHandler(skip_cmd, category_handler),
            ],
            ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, address_handler),
                MessageHandler(skip_cmd, address_handler),
            ],
            COORDINATES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, coordinates_choice_handler),
                MessageHandler(skip_cmd, coordinates_choice_handler),
            ],
            COORDINATES_MANUAL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, coordinates_manual_handler),
                MessageHandler(skip_cmd, coordinates_manual_handler),
            ],
            CONTACT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, contact_handler),
                MessageHandler(skip_cmd, contact_handler),
            ],
            HOURS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, hours_handler),
                MessageHandler(skip_cmd, hours_handler),
            ],
            CUSTOM_HOURS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, custom_hours_handler),
                MessageHandler(skip_cmd, custom_hours_handler),
            ],
            # CHAIN_STATUS: [CallbackQueryHandler(chain_status_handler)],  # removed
            # CHAIN_DETAILS: [
            #     MessageHandler(filters.TEXT & ~filters.COMMAND, chain_details_handler),
            #     MessageHandler(skip_cmd, chain_details_handler),
            # ],
            ATTRIBUTES: [MessageHandler(filters.TEXT & ~filters.COMMAND, attributes_handler)],
            PRIVATE_PLACE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, private_place_handler),
                MessageHandler(skip_cmd, private_place_handler),
            ],
            PHOTOS: [
                MessageHandler(filters.PHOTO, photos_handler),
                CommandHandler("skip", photos_handler),
                CommandHandler("done", photos_handler),
            ],
            CONFIRM: [CallbackQueryHandler(handle_confirmation)],
        },
        fallbacks=[CommandHandler("start", start), CommandHandler("cancel", cancel)],
    )


def main() -> None:
    """
    Bootstrap the Placemaker Telegram bot.

    Depending on configuration, the bot runs either in webhook mode (Flask +
    ngrok) or in long-polling mode for local development.
    """
    try:
        _validate_required_settings()
    except ConfigurationError as exc:
        logger.error("Configuration error: %s", exc)
        raise SystemExit(1) from exc

    application = Application.builder().token(settings.telegram_bot_token).build()
    application.add_handler(_build_conversation_handler())

    if settings.use_webhook:
        logger.info("Starting in webhook mode")
        event_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(event_loop)

        flask_app = create_app(application, application.bot, event_loop)
        flask_thread = threading.Thread(target=run_flask_app, args=(flask_app,), daemon=True)
        flask_thread.start()

        event_loop.run_until_complete(application.initialize())
        event_loop.run_until_complete(application.start())

        if settings.auto_set_webhook:
            external_base = discover_external_base_url()
            if external_base.startswith("https://"):
                webhook_url = f"{external_base}{settings.webhook_path}"
                event_loop.run_until_complete(application.bot.set_webhook(url=webhook_url))
                logger.info(f"Webhook set to: {webhook_url}")
            else:
                logger.warning("Could not discover a public https URL; skipping webhook auto-registration.")
        else:
            webhook_url = f"https://{settings.webapp_domain}{settings.webhook_path}"
            event_loop.run_until_complete(application.bot.set_webhook(url=webhook_url))
            logger.info(f"Webhook set to: {webhook_url}")

        try:
            event_loop.run_forever()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            event_loop.run_until_complete(application.bot.delete_webhook())
            event_loop.run_until_complete(application.stop())
            event_loop.run_until_complete(application.shutdown())
            event_loop.close()
    else:
        logger.info("Starting in polling mode")
        application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main() 
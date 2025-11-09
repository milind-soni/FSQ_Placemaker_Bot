import asyncio
import json

from flask import Flask, jsonify, request, send_from_directory
from telegram import Update

from .config import settings
from .logging import setup_logging


logger = setup_logging()


def create_app(application, bot, loop) -> Flask:
    """
    Build a Flask application that forwards webhook payloads to the Telegram bot.

    Args:
        application: The configured `python-telegram-bot` application instance.
        bot: The Telegram bot used to deserialize incoming updates.
        loop: The asyncio event loop responsible for processing updates.

    Returns:
        A configured Flask application instance.
    """
    app = Flask(__name__)

    @app.route('/health')
    def health_check():
        return jsonify({"status": "healthy", "service": "placemaker-bot"})

    @app.route('/')
    def serve_webapp():
        return send_from_directory('webapp', 'index.html')

    @app.route('/<path:filename>')
    def serve_static(filename):
        return send_from_directory('webapp', filename)

    @app.route(settings.webhook_path, methods=['POST'])
    def webhook():
        try:
            payload = request.get_data(cache=False, as_text=True)
            update = Update.de_json(json.loads(payload), bot)
        except json.JSONDecodeError:
            logger.error(
                "Webhook payload was not valid JSON",
                extra={"service": settings.service_name, "env": settings.app_env},
                exc_info=True,
            )
            return jsonify({"error": "invalid json payload"}), 400
        except Exception:
            logger.error(
                "Failed to deserialize webhook payload",
                extra={"service": settings.service_name, "env": settings.app_env},
                exc_info=True,
            )
            return jsonify({"error": "processing failed"}), 500

        logger.info(
            "Webhook update received",
            extra={
                "service": settings.service_name,
                "env": settings.app_env,
                "update_id": getattr(update, "update_id", None),
            },
        )

        try:
            asyncio.run_coroutine_threadsafe(application.process_update(update), loop)
            logger.info(
                "Webhook update scheduled",
                extra={
                    "service": settings.service_name,
                    "env": settings.app_env,
                    "update_id": getattr(update, "update_id", None),
                },
            )
            return jsonify({"status": "ok"})
        except Exception:
            logger.error(
                "Error scheduling webhook update",
                extra={"service": settings.service_name, "env": settings.app_env},
                exc_info=True,
            )
            return jsonify({"error": "processing failed"}), 500

    return app 
from flask import Flask, request, jsonify, send_from_directory
import json
import asyncio
from telegram import Update

from .config import settings
from .logging import setup_logging


def create_app(application, bot, loop) -> Flask:
    logger = setup_logging()
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
            json_string = request.get_data().decode('utf-8')
            logger.info("webhook received", extra={"service": settings.service_name, "env": settings.app_env})
            update = Update.de_json(json.loads(json_string), bot)
            asyncio.run_coroutine_threadsafe(
                application.process_update(update),
                loop
            )
            logger.info("webhook update scheduled", extra={"service": settings.service_name, "env": settings.app_env})
            return jsonify({"status": "ok"})
        except Exception:
            logger.error("Error processing webhook", extra={"service": settings.service_name, "env": settings.app_env}, exc_info=True)
            return jsonify({"error": "processing failed"}), 500

    return app 
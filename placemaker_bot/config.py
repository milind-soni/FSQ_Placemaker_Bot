import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env
load_dotenv()


def _bool(value: str, default: bool = False) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    foursquare_api_key: str = os.environ.get("FOURSQUARE_API_KEY", "")

    webapp_domain: str = os.environ.get("WEBAPP_DOMAIN", "localhost")
    webapp_port: int = int(os.environ.get("WEBAPP_PORT", "8000"))

    use_webhook: bool = _bool(os.environ.get("USE_WEBHOOK", "false"))
    webhook_path: str = os.environ.get("WEBHOOK_PATH", "/webhook")
    ngrok_api_base: str = os.environ.get("NGROK_API_BASE", "http://ngrok:4040")
    auto_set_webhook: bool = _bool(os.environ.get("AUTO_SET_WEBHOOK", "true"))

    # Logging
    app_env: str = os.environ.get("APP_ENV", "dev")
    service_name: str = os.environ.get("SERVICE_NAME", "conversation_bot")
    log_level: str = os.environ.get("LOG_LEVEL", "INFO").upper()
    log_to_file: bool = _bool(os.environ.get("LOG_TO_FILE", "false"))
    log_file: str = os.environ.get("LOG_FILE", "logs/placemaker_bot.log")
    log_rotate_when: str = os.environ.get("LOG_ROTATE_WHEN", "midnight")
    log_rotate_interval: int = int(os.environ.get("LOG_ROTATE_INTERVAL", "1"))
    log_backup_count: int = int(os.environ.get("LOG_BACKUP_COUNT", "7"))

    # LLM configuration (using litellm)
    # Set the appropriate API key environment variable for your provider:
    # - OpenAI: OPENAI_API_KEY
    # - Anthropic: ANTHROPIC_API_KEY  
    # - Azure: AZURE_API_KEY
    # - AWS Bedrock: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION_NAME
    # See https://docs.litellm.ai/docs/providers for full list
    llm_chat_model: str = os.environ.get("LLM_CHAT_MODEL", "gpt-4.1-nano")
    llm_parse_model: str = os.environ.get("LLM_PARSE_MODEL", "gpt-4.1-nano")


settings = Settings()
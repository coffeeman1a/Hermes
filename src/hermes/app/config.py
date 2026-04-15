import os
import logging
import sys
from hermes.models.app_config import Config
from dotenv import load_dotenv

def load_config() -> Config:
    # email
    load_dotenv()
    imap_host = os.getenv("IMAP_HOST")
    email_login = os.getenv("EMAIL_LOGIN")
    email_password = os.getenv("EMAIL_PASSWORD")
    whitelist = str_to_bool(os.getenv("WHITELIST"))
    emails = os.getenv("WHITELIST_EMAILS")
    if emails:
        whitelist_emails = [e.strip() for e in emails.split(",") if e.strip()]
    else:
        whitelist_emails = []

    # tg
    tg_api = os.getenv("TG_API")
    tg_token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    # app
    poll_interval = os.getenv("POLL_INTERVAL", "300")
    log_level = os.getenv("LOG_LEVEL")

    missing = []
    if not tg_api:
        missing.append("TG_API")
    if not tg_token:
        missing.append("TG_TOKEN")
    if not chat_id:
        missing.append("CHAT_ID")
    if not imap_host:
        missing.append("IMAP_HOST")
    if not email_login:
        missing.append("EMAIL_LOGIN")
    if not email_password:
        missing.append("EMAIL_PASSWORD")
    if whitelist and len(whitelist_emails) == 0:
        missing.append("WHITELIST_EMAILS")
    
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    return Config(
        tg_api=tg_api,
        tg_token=tg_token,
        chat_id=chat_id,
        imap_host=imap_host,
        email_login=email_login,
        email_password=email_password,
        poll_interval=int(poll_interval),
        whitelist=whitelist,
        log_level=log_level,
        whitelist_emails=whitelist_emails,
    )

def str_to_bool(value: str) -> bool:
    if not value:
        return False
    return value.lower() == "true"

def setup_logging(log_level: str) -> None:
    level = getattr(logging, log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
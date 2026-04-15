import time
import logging
from hermes.app.config import load_config, setup_logging
from  hermes.app.imap_client import ImapClient
from hermes.app.tg_client import TGClient

logger = logging.getLogger(__name__)

def main() -> None:

    config = load_config()
    setup_logging(config.log_level)
    logger.info("App started")
    
    imap_client = ImapClient(
        server=config.imap_host,
        user=config.email_login,
        password=config.email_password,
        whitelist=config.whitelist,
        whitelist_emails=config.whitelist_emails
    )

    tg_client = TGClient(
        api=config.tg_api,
        token=config.tg_token,
        chat_id=config.chat_id
    )

    logger.info("Clients initialized successfully")
    run(imap_client, tg_client, config.poll_interval)

def run(imap_client: ImapClient, tg_client: TGClient, poll_interval: int) -> None:
    while True:
        try:  
            inbox = imap_client.read_mail()
            logger.info("Fetched %s emails", len(inbox))

            for mail in inbox:
                try:
                    tg_client.send_message(mail)
                    logger.info("Forwarded email from=%s subject=%s", mail.sender, mail.subject)
                    time.sleep(10)
                except Exception:
                    logger.exception("Failed to forward email to Telegram")
        except Exception:
            logger.exception("Failed during polling iteration")

        time.sleep(poll_interval)
    

if __name__ == "__main__":
    main()

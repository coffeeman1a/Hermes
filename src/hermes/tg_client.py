import datetime
import re
import requests
import logging
from models.email_message import EmailMessage

logger = logging.getLogger(__name__)

class TGClient:
    def __init__(self, api: str, token: str, chat_id: str):
        self.api = api
        self.token = token
        self.chat_id = chat_id

    def send_message(self, email_message: EmailMessage) -> None:
        text = self.format_alert(
            sender=email_message.sender,
            subject=email_message.subject,
            received_at=email_message.received_at,
            text=email_message.text,
        )

        response = requests.post(
            f"{self.api}/bot{self.token}/sendMessage",
            json={
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
            },
            timeout=5,
        )

        if response.ok:
            logger.info("Telegram message sent successfully, status=%s", response.status_code)
        else:
            logger.error(
                "Telegram API error, status=%s, response=%s",
                response.status_code,
                response.text,
            )


    @staticmethod
    def escape_md(text: str) -> str:
        # Telegram MarkdownV2 требует экранирования
        #return re.sub(r'([_*~`>#+=|{}])', r'\\\1', text) # Markdown
        return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', text) # MarkdownV2
    
    @staticmethod
    def format_alert(
        sender: str,
        subject: str,
        received_at: datetime.datetime,
        text: str,
    ) -> str:
        sender = TGClient.escape_md(sender)
        subject = TGClient.escape_md(subject)
        text = TGClient.escape_md(text[:1000])
        quoted = "\n".join([f"> {line}" for line in text.splitlines()])
        time_str = received_at.strftime("%Y-%m-%d %H:%M:%S")
        time_str = TGClient.escape_md(time_str)

        return (
            "🚨 *INCIDENT ALERT*\n\n"
            f"📨 *From:* {sender}\n"
            f"📝 *Subject:* {subject}\n"
            f"🕒 *Time:* {time_str}\n\n"
            f"📄 *Details:*\n{quoted}"
        )
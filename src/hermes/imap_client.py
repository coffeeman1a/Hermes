import datetime
import imaplib
import email
import logging
from email.message import Message
from email.utils import parseaddr, parsedate_to_datetime
from bs4 import BeautifulSoup
from models.email_message import EmailMessage
from email.header import decode_header

logger = logging.getLogger(__name__)

class ImapClient:
    def __init__(self, server: str, user: str, password: str, whitelist: bool, whitelist_emails: list[str]=[]):
        self.mail = imaplib.IMAP4_SSL(server) # создаём клиент
        self.mail.login(user, password)
        self.whitelist = whitelist
        self.whitelist_emails = whitelist_emails

    @staticmethod
    def decode_mime_header(value: str) -> str:
        if not value:
            return ""

        parts = decode_header(value)
        decoded = ""

        for part, encoding in parts:
            if isinstance(part, bytes):
                decoded += part.decode(encoding or "utf-8", errors="ignore")
            else:
                decoded += part

        return decoded

    def read_mail(self) -> list[EmailMessage]:
        inbox_emails = []
        # смотрим входящие
        self.mail.select("inbox")
        status, messages = self.mail.search(None, 'UNSEEN')
        if status != "OK":
            logger.error("IMAP search failed")

        for num in messages[0].split():
            status, data = self.mail.fetch(num, '(RFC822)')

            if status != "OK":
                logger.error("IMAP fetch failed")
                continue

            msg = email.message_from_bytes(data[0][1])
            name, email_addr = parseaddr(msg.get("From"))

            if self.whitelist and email_addr not in self.whitelist_emails:
                logger.debug("Sender is not in whitelist, skipping")
                continue

            subject = ImapClient.decode_mime_header(msg.get("Subject"))
            date_raw = msg.get("Date")

            try:
                received_at = parsedate_to_datetime(date_raw)
            except Exception:
                received_at = datetime.now()

            text = ImapClient.parse_message(msg)
            
            inbox_emails.append(
                EmailMessage(
                    sender=email_addr,
                    subject=subject,
                    text=text,
                    received_at=received_at,
                )
            )

            logger.debug("Succesfully parsed an email")

        logger.info("Succesfully parsed %s emails", len(inbox_emails))
        return inbox_emails

    def close(self):
        try:
            self.mail.close()
        except Exception as e:
            logger.error("Error closing IMAP connection: %s", e)
        self.mail.logout()

    @staticmethod
    def html_to_text(html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        return soup.get_text(separator="\n", strip=True)

    @staticmethod
    def parse_message(msg: Message) -> str:
        # проверяем тип сообщения
        if msg.is_multipart():
            # чекаем части по отдельности
            for part in msg.walk():
                # игнорим всё кроме text/plain
                if "multipart" in part.get_content_type():
                    continue

                if part.get_content_type() == "text/plain":
                    return part.get_payload(decode=True).decode(errors="ignore")

        else:
            if msg.get_content_type() == "text/plain":
                return msg.get_payload(decode=True).decode(errors="ignore")

            elif msg.get_content_type() == "text/html":
                charset = msg.get_content_charset() or "utf-8"
                html = msg.get_payload(decode=True).decode(charset, errors="ignore")
                return ImapClient.html_to_text(html)

        return ""
    

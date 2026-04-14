from dataclasses import dataclass

@dataclass
class Config:
    tg_api: str
    tg_token: str
    chat_id: str
    imap_host: str
    email_login: str
    email_password: str
    whitelist: bool
    whitelist_emails: list[str]
    log_level: str
    poll_interval: int = 300 # default
from dataclasses import dataclass
import  datetime

@dataclass
class EmailMessage:
    sender: str
    subject: str
    text: str
    received_at: datetime.datetime
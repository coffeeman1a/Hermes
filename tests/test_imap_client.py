import datetime
from email.message import EmailMessage as PyEmailMessage
from email.header import Header
from unittest.mock import Mock, patch

import pytest

from hermes.app.imap_client import ImapClient


@pytest.fixture
def mock_imap():
    with patch("hermes.app.imap_client.imaplib.IMAP4_SSL") as mock_cls:
        mail = Mock()
        mock_cls.return_value = mail
        mail.login.return_value = ("OK", [b"Logged in"])
        yield mail


@pytest.fixture
def client(mock_imap):
    return ImapClient(
        server="imap.example.com",
        user="user@example.com",
        password="secret",
        whitelist=False,
        whitelist_emails=[],
    )


def build_email_bytes(
    from_addr: str = "Alert <alert@example.com>",
    subject: str = "Test subject",
    body: str = "Hello world",
    content_type: str = "plain",
    date: str = "Mon, 15 Apr 2026 10:00:00 +0000",
):
    msg = PyEmailMessage()
    msg["From"] = from_addr
    msg["Subject"] = subject
    msg["Date"] = date

    if content_type == "plain":
        msg.set_content(body)
    elif content_type == "html":
        msg.add_alternative(body, subtype="html")
    else:
        raise ValueError("Unsupported content_type")

    return msg.as_bytes()


def test_init_logs_in(mock_imap):
    ImapClient(
        server="imap.example.com",
        user="user@example.com",
        password="secret",
        whitelist=False,
        whitelist_emails=[],
    )

    mock_imap.login.assert_called_once_with("user@example.com", "secret")


def test_decode_mime_header_plain():
    assert ImapClient.decode_mime_header("Hello") == "Hello"


def test_decode_mime_header_empty():
    assert ImapClient.decode_mime_header("") == ""
    assert ImapClient.decode_mime_header(None) == ""


def test_decode_mime_header_encoded():
    subject = str(Header("Привет", "utf-8"))
    decoded = ImapClient.decode_mime_header(subject)
    assert decoded == "Привет"


def test_html_to_text():
    html = "<html><body><h1>Alert</h1><p>Error happened</p></body></html>"
    result = ImapClient.html_to_text(html)

    assert "Alert" in result
    assert "Error happened" in result


def test_parse_message_plain_text():
    msg = PyEmailMessage()
    msg.set_content("plain text body")

    result = ImapClient.parse_message(msg)

    assert "plain text body" in result


def test_parse_message_html():
    msg = PyEmailMessage()
    msg.set_content("<b>fallback</b>", subtype="html")

    result = ImapClient.parse_message(msg)

    assert "fallback" in result


def test_parse_message_multipart_prefers_text_plain():
    msg = PyEmailMessage()
    msg.set_content("plain version")
    msg.add_alternative("<b>html version</b>", subtype="html")

    result = ImapClient.parse_message(msg)

    assert "plain version" in result


def test_parse_message_unknown_returns_empty():
    msg = PyEmailMessage()
    msg.set_type("application/octet-stream")
    msg.set_payload(b"binary-data")

    result = ImapClient.parse_message(msg)

    assert result == ""


def test_read_mail_returns_parsed_emails(client, mock_imap):
    raw_email = build_email_bytes()

    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = ("OK", [b"1 2"])
    mock_imap.fetch.side_effect = [
        ("OK", [(b"1", raw_email)]),
        ("OK", [(b"2", raw_email)]),
    ]

    emails = client.read_mail()

    assert len(emails) == 2
    assert emails[0].sender == "alert@example.com"
    assert emails[0].subject == "Test subject"
    assert "Hello world" in emails[0].text
    assert isinstance(emails[0].received_at, datetime.datetime)


def test_read_mail_skips_non_whitelisted_sender(mock_imap):
    client = ImapClient(
        server="imap.example.com",
        user="user@example.com",
        password="secret",
        whitelist=True,
        whitelist_emails=["allowed@example.com"],
    )

    raw_email = build_email_bytes(from_addr="Bad Guy <bad@example.com>")

    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = ("OK", [b"1"])
    mock_imap.fetch.return_value = ("OK", [(b"1", raw_email)])

    emails = client.read_mail()

    assert emails == []


def test_read_mail_continues_if_fetch_failed(client, mock_imap):
    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = ("OK", [b"1 2"])
    mock_imap.fetch.side_effect = [
        ("NO", []),
        ("OK", [(b"2", build_email_bytes())]),
    ]

    emails = client.read_mail()

    assert len(emails) == 1
    assert emails[0].sender == "alert@example.com"


def test_read_mail_uses_current_time_when_date_invalid(client, mock_imap):
    raw_email = build_email_bytes(date="not-a-real-date")

    mock_imap.select.return_value = ("OK", [b""])
    mock_imap.search.return_value = ("OK", [b"1"])
    mock_imap.fetch.return_value = ("OK", [(b"1", raw_email)])

    with patch("hermes.app.imap_client.datetime.datetime") as mock_datetime:
        fake_now = datetime.datetime(2026, 4, 15, 12, 0, 0)
        mock_datetime.now.return_value = fake_now

        emails = client.read_mail()

    assert len(emails) == 1
    assert emails[0].received_at == fake_now


def test_close_calls_close_and_logout(client, mock_imap):
    client.close()

    mock_imap.close.assert_called_once()
    mock_imap.logout.assert_called_once()


def test_close_logs_error_and_still_logs_out(client, mock_imap):
    mock_imap.close.side_effect = Exception("close failed")

    client.close()

    mock_imap.logout.assert_called_once()
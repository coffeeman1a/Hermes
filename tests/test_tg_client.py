import datetime
from unittest.mock import Mock, patch

import requests

from hermes.app.tg_client import TGClient
from hermes.models.email_message import EmailMessage


def make_email_message(
    sender: str = "alert@example.com",
    subject: str = "Disk usage > 90%!",
    text: str = "Filesystem /dev/sda1 is almost full.",
    received_at: datetime.datetime | None = None,
) -> EmailMessage:
    return EmailMessage(
        sender=sender,
        subject=subject,
        text=text,
        received_at=received_at or datetime.datetime(2026, 4, 15, 12, 30, 45),
    )


def test_init_sets_attributes():
    client = TGClient(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )

    assert client.api == "https://api.telegram.org"
    assert client.token == "token123"
    assert client.chat_id == "999"


def test_escape_md_escapes_markdown_v2_chars():
    text = r"_*[]()~`>#+-=|{}.!"
    escaped = TGClient.escape_md(text)

    assert escaped == r"\_\*\[\]\(\)\~\`\>\#\+\-\=\|\{\}\.\!"


def test_escape_md_leaves_plain_text_unchanged():
    text = "simple text 123 ABC"
    escaped = TGClient.escape_md(text)

    assert escaped == "simple text 123 ABC"


def test_format_alert_formats_message():
    received_at = datetime.datetime(2026, 4, 15, 12, 30, 45)

    result = TGClient.format_alert(
        sender="alert@example.com",
        subject="Disk usage > 90%!",
        received_at=received_at,
        text="Line 1\nLine 2",
    )

    assert "🚨 *INCIDENT ALERT* 🚨" in result
    assert "📨 *From:* alert@example\\.com" in result
    assert "📝 *Subject:* Disk usage \\> 90%\\!" in result
    assert "🕒 *Time:* 2026\\-04\\-15 12:30:45" in result
    assert "📄 *Details:*" in result
    assert "> Line 1" in result
    assert "> Line 2" in result


def test_format_alert_truncates_text_to_1000_chars():
    long_text = "a" * 1200
    received_at = datetime.datetime(2026, 4, 15, 12, 30, 45)

    result = TGClient.format_alert(
        sender="alert@example.com",
        subject="Test",
        received_at=received_at,
        text=long_text,
    )

    details_part = result.split("📄 *Details:*\n", 1)[1]
    quoted_lines = details_part.splitlines()
    joined = "\n".join(line.removeprefix("> ") for line in quoted_lines)

    assert len(joined) == 1000


def test_format_alert_escapes_details_text():
    received_at = datetime.datetime(2026, 4, 15, 12, 30, 45)

    result = TGClient.format_alert(
        sender="alert@example.com",
        subject="Test",
        received_at=received_at,
        text="error_code=500! [disk_full]",
    )

    assert "> error\\_code\\=500\\! \\[disk\\_full\\]" in result


@patch("hermes.app.tg_client.requests.post")
def test_send_message_success_first_try(mock_post):
    mock_response = Mock()
    mock_response.ok = True
    mock_response.status_code = 200
    mock_response.text = "ok"
    mock_post.return_value = mock_response

    client = TGClient(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )
    email_message = make_email_message()

    with patch("hermes.app.tg_client.time.sleep") as mock_sleep:
        client.send_message(email_message)

    mock_post.assert_called_once()
    mock_sleep.assert_not_called()

    call_args = mock_post.call_args
    assert call_args.args[0] == "https://api.telegram.org/bottoken123/sendMessage"
    assert call_args.kwargs["timeout"] == 5
    assert call_args.kwargs["json"]["chat_id"] == "999"
    assert call_args.kwargs["json"]["parse_mode"] == "MarkdownV2"
    assert "🚨 *INCIDENT ALERT* 🚨" in call_args.kwargs["json"]["text"]


@patch("hermes.app.tg_client.requests.post")
def test_send_message_retries_and_succeeds_on_third_try(mock_post):
    first_response = Mock()
    first_response.ok = False
    first_response.status_code = 500
    first_response.text = "server error"

    second_response = Mock()
    second_response.ok = False
    second_response.status_code = 502
    second_response.text = "bad gateway"

    third_response = Mock()
    third_response.ok = True
    third_response.status_code = 200
    third_response.text = "ok"

    mock_post.side_effect = [first_response, second_response, third_response]

    client = TGClient(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )
    email_message = make_email_message()

    with patch("hermes.app.tg_client.time.sleep") as mock_sleep:
        client.send_message(email_message)

    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2
    mock_sleep.assert_any_call(2)


@patch("hermes.app.tg_client.requests.post")
def test_send_message_retries_on_request_exception_and_then_succeeds(mock_post):
    success_response = Mock()
    success_response.ok = True
    success_response.status_code = 200
    success_response.text = "ok"

    mock_post.side_effect = [
        requests.RequestException("network error"),
        requests.RequestException("timeout"),
        success_response,
    ]

    client = TGClient(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )
    email_message = make_email_message()

    with patch("hermes.app.tg_client.time.sleep") as mock_sleep:
        client.send_message(email_message)

    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2


@patch("hermes.app.tg_client.requests.post")
def test_send_message_fails_after_three_api_errors(mock_post):
    response = Mock()
    response.ok = False
    response.status_code = 500
    response.text = "server error"
    mock_post.side_effect = [response, response, response]

    client = TGClient(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )
    email_message = make_email_message()

    with patch("hermes.app.tg_client.time.sleep") as mock_sleep:
        client.send_message(email_message)

    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2


@patch("hermes.app.tg_client.requests.post")
def test_send_message_fails_after_three_request_exceptions(mock_post):
    mock_post.side_effect = [
        requests.RequestException("network error"),
        requests.RequestException("timeout"),
        requests.RequestException("dns failure"),
    ]

    client = TGClient(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )
    email_message = make_email_message()

    with patch("hermes.app.tg_client.time.sleep") as mock_sleep:
        client.send_message(email_message)

    assert mock_post.call_count == 3
    assert mock_sleep.call_count == 2
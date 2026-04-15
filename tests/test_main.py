from types import SimpleNamespace
from unittest.mock import Mock, call, patch

import pytest

from hermes.app.main import main, run


def test_main_initializes_clients_and_calls_run():
    fake_config = SimpleNamespace(
        log_level="INFO",
        imap_host="imap.example.com",
        email_login="user@example.com",
        email_password="secret",
        whitelist=True,
        whitelist_emails=["alert@example.com"],
        tg_api="https://api.telegram.org",
        tg_token="token123",
        chat_id="999",
        poll_interval=300,
    )

    with patch("hermes.app.main.load_config", return_value=fake_config) as mock_load_config, \
         patch("hermes.app.main.setup_logging") as mock_setup_logging, \
         patch("hermes.app.main.ImapClient") as mock_imap_cls, \
         patch("hermes.app.main.TGClient") as mock_tg_cls, \
         patch("hermes.app.main.run") as mock_run:

        imap_instance = Mock()
        tg_instance = Mock()
        mock_imap_cls.return_value = imap_instance
        mock_tg_cls.return_value = tg_instance

        main()

    mock_load_config.assert_called_once()
    mock_setup_logging.assert_called_once_with("INFO")

    mock_imap_cls.assert_called_once_with(
        server="imap.example.com",
        user="user@example.com",
        password="secret",
        whitelist=True,
        whitelist_emails=["alert@example.com"],
    )

    mock_tg_cls.assert_called_once_with(
        api="https://api.telegram.org",
        token="token123",
        chat_id="999",
    )

    mock_run.assert_called_once_with(imap_instance, tg_instance, 300)


def test_run_reads_mail_and_sends_all_messages():
    imap_client = Mock()
    tg_client = Mock()

    mail1 = SimpleNamespace(sender="a@example.com", subject="subj1")
    mail2 = SimpleNamespace(sender="b@example.com", subject="subj2")

    imap_client.read_mail.side_effect = [
        [mail1, mail2],
        KeyboardInterrupt("stop loop"),
    ]

    with patch("hermes.app.main.time.sleep") as mock_sleep:
        with pytest.raises(KeyboardInterrupt):
            run(imap_client, tg_client, poll_interval=60)

    assert tg_client.send_message.call_args_list == [call(mail1), call(mail2)]
    assert mock_sleep.call_args_list == [call(10), call(10), call(60)]


def test_run_continues_when_send_message_fails():
    imap_client = Mock()
    tg_client = Mock()

    mail1 = SimpleNamespace(sender="a@example.com", subject="subj1")
    mail2 = SimpleNamespace(sender="b@example.com", subject="subj2")

    imap_client.read_mail.side_effect = [
        [mail1, mail2],
        KeyboardInterrupt("stop loop"),
    ]
    tg_client.send_message.side_effect = [Exception("tg failed"), None]

    with patch("hermes.app.main.time.sleep") as mock_sleep:
        with pytest.raises(KeyboardInterrupt):
            run(imap_client, tg_client, poll_interval=60)

    assert tg_client.send_message.call_count == 2
    tg_client.send_message.assert_any_call(mail1)
    tg_client.send_message.assert_any_call(mail2)

    # sleep(10) only happens after successful send
    assert mock_sleep.call_args_list == [call(10), call(60)]


def test_run_continues_when_read_mail_fails():
    imap_client = Mock()
    tg_client = Mock()

    imap_client.read_mail.side_effect = [
        Exception("imap failed"),
        KeyboardInterrupt("stop loop"),
    ]

    with patch("hermes.app.main.time.sleep") as mock_sleep:
        with pytest.raises(KeyboardInterrupt):
            run(imap_client, tg_client, poll_interval=30)

    tg_client.send_message.assert_not_called()
    assert mock_sleep.call_args_list == [call(30)]


def test_run_sleeps_after_each_iteration_even_when_inbox_empty():
    imap_client = Mock()
    tg_client = Mock()

    imap_client.read_mail.side_effect = [
        [],
        KeyboardInterrupt("stop loop"),
    ]

    with patch("hermes.app.main.time.sleep") as mock_sleep:
        with pytest.raises(KeyboardInterrupt):
            run(imap_client, tg_client, poll_interval=45)

    tg_client.send_message.assert_not_called()
    assert mock_sleep.call_args_list == [call(45)]


def test_run_sleeps_between_successful_messages_and_after_iteration():
    imap_client = Mock()
    tg_client = Mock()

    mail1 = SimpleNamespace(sender="a@example.com", subject="subj1")

    def fake_sleep(seconds):
        if seconds == 15:
            raise KeyboardInterrupt("stop after first iteration")

    imap_client.read_mail.return_value = [mail1]

    with patch("hermes.app.main.time.sleep", side_effect=fake_sleep) as mock_sleep:
        with pytest.raises(KeyboardInterrupt):
            run(imap_client, tg_client, poll_interval=15)

    tg_client.send_message.assert_called_once_with(mail1)
    assert mock_sleep.call_args_list == [call(10), call(15)]
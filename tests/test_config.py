import logging
from unittest.mock import patch

import pytest

from hermes.app.config import load_config, str_to_bool, setup_logging


def test_str_to_bool_true():
    assert str_to_bool("true") is True
    assert str_to_bool("TRUE") is True


def test_str_to_bool_false():
    assert str_to_bool("false") is False


def test_str_to_bool_rejects_partial_true():
    assert str_to_bool("tru") is False
    assert str_to_bool("t") is False


def test_load_config_success(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("EMAIL_LOGIN", "user@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("WHITELIST", "true")
    monkeypatch.setenv("WHITELIST_EMAILS", "a@example.com, b@example.com")
    monkeypatch.setenv("TG_API", "https://api.telegram.org")
    monkeypatch.setenv("TG_TOKEN", "token123")
    monkeypatch.setenv("CHAT_ID", "123456")
    monkeypatch.setenv("POLL_INTERVAL", "600")
    monkeypatch.setenv("LOG_LEVEL", "debug")

    config = load_config()

    assert config.imap_host == "imap.example.com"
    assert config.email_login == "user@example.com"
    assert config.email_password == "secret"
    assert config.whitelist is True
    assert config.whitelist_emails == ["a@example.com", "b@example.com"]
    assert config.tg_api == "https://api.telegram.org"
    assert config.tg_token == "token123"
    assert config.chat_id == "123456"
    assert config.poll_interval == 600
    assert config.log_level == "debug"


def test_load_config_uses_default_poll_interval(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("EMAIL_LOGIN", "user@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("WHITELIST", "false")
    monkeypatch.delenv("WHITELIST_EMAILS", raising=False)
    monkeypatch.setenv("TG_API", "https://api.telegram.org")
    monkeypatch.setenv("TG_TOKEN", "token123")
    monkeypatch.setenv("CHAT_ID", "123456")
    monkeypatch.delenv("POLL_INTERVAL", raising=False)
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    config = load_config()

    assert config.poll_interval == 300
    assert config.whitelist is False
    assert config.whitelist_emails == []


def test_load_config_parses_whitelist_emails_with_spaces(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("EMAIL_LOGIN", "user@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("WHITELIST", "true")
    monkeypatch.setenv("WHITELIST_EMAILS", " a@example.com , , b@example.com  , ")
    monkeypatch.setenv("TG_API", "https://api.telegram.org")
    monkeypatch.setenv("TG_TOKEN", "token123")
    monkeypatch.setenv("CHAT_ID", "123456")
    monkeypatch.setenv("POLL_INTERVAL", "300")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    config = load_config()

    assert config.whitelist_emails == ["a@example.com", "b@example.com"]


def test_load_config_raises_when_required_vars_missing(monkeypatch):
    monkeypatch.delenv("IMAP_HOST", raising=False)
    monkeypatch.delenv("EMAIL_LOGIN", raising=False)
    monkeypatch.delenv("EMAIL_PASSWORD", raising=False)
    monkeypatch.delenv("WHITELIST", raising=False)
    monkeypatch.delenv("WHITELIST_EMAILS", raising=False)
    monkeypatch.delenv("TG_API", raising=False)
    monkeypatch.delenv("TG_TOKEN", raising=False)
    monkeypatch.delenv("CHAT_ID", raising=False)
    monkeypatch.delenv("POLL_INTERVAL", raising=False)
    monkeypatch.delenv("LOG_LEVEL", raising=False)

    with pytest.raises(ValueError) as exc:
        load_config()

    message = str(exc.value)
    assert "TG_API" in message
    assert "TG_TOKEN" in message
    assert "CHAT_ID" in message
    assert "IMAP_HOST" in message
    assert "EMAIL_LOGIN" in message
    assert "EMAIL_PASSWORD" in message


def test_load_config_raises_when_whitelist_enabled_but_no_emails(monkeypatch):
    monkeypatch.setenv("IMAP_HOST", "imap.example.com")
    monkeypatch.setenv("EMAIL_LOGIN", "user@example.com")
    monkeypatch.setenv("EMAIL_PASSWORD", "secret")
    monkeypatch.setenv("WHITELIST", "true")
    monkeypatch.delenv("WHITELIST_EMAILS", raising=False)
    monkeypatch.setenv("TG_API", "https://api.telegram.org")
    monkeypatch.setenv("TG_TOKEN", "token123")
    monkeypatch.setenv("CHAT_ID", "123456")
    monkeypatch.setenv("POLL_INTERVAL", "300")
    monkeypatch.setenv("LOG_LEVEL", "INFO")

    with pytest.raises(ValueError) as exc:
        load_config()

    assert "WHITELIST_EMAILS" in str(exc.value)


def test_setup_logging_uses_requested_level():
    with patch("hermes.app.config.logging.basicConfig") as mock_basic_config:
        setup_logging("debug")

    kwargs = mock_basic_config.call_args.kwargs
    assert kwargs["level"] == logging.DEBUG
    assert "%(asctime)s %(levelname)s [%(name)s] %(message)s" == kwargs["format"]


def test_setup_logging_falls_back_to_info_for_unknown_level():
    with patch("hermes.app.config.logging.basicConfig") as mock_basic_config:
        setup_logging("not_a_real_level")

    kwargs = mock_basic_config.call_args.kwargs
    assert kwargs["level"] == logging.INFO
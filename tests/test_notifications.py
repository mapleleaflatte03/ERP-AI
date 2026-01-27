from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.notifications import send_email, send_telegram_message


@pytest.mark.asyncio
async def test_send_email_success():
    with patch("src.notifications.config") as mock_config:
        mock_config.SMTP_HOST = "localhost"
        mock_config.SMTP_PORT = 1025
        mock_config.SMTP_USER = ""
        mock_config.SMTP_PASSWORD = ""
        mock_config.SMTP_FROM_EMAIL = "test@example.com"

        with patch("src.notifications.smtplib.SMTP") as mock_smtp:
            mock_server = MagicMock()
            mock_smtp.return_value.__enter__.return_value = mock_server

            result = await send_email("user@example.com", "Subject", "Body")

            assert result is True
            mock_server.send_message.assert_called_once()


@pytest.mark.asyncio
async def test_send_email_no_config():
    with patch("src.notifications.config") as mock_config:
        mock_config.SMTP_HOST = ""

        result = await send_email("user@example.com", "Subject", "Body")
        assert result is False


@pytest.mark.asyncio
async def test_send_telegram_success():
    with patch("src.notifications.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = "123:ABC"

        with patch("src.notifications.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_client.post.return_value.status_code = 200

            result = await send_telegram_message("12345", "Message")

            assert result is True
            mock_client.post.assert_called_once()


@pytest.mark.asyncio
async def test_send_telegram_no_config():
    with patch("src.notifications.config") as mock_config:
        mock_config.TELEGRAM_BOT_TOKEN = ""

        result = await send_telegram_message("12345", "Message")
        assert result is False

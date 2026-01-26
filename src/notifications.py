import asyncio
import logging
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from src.core import config

logger = logging.getLogger(__name__)


async def send_email(to_email: str, subject: str, body: str) -> bool:
    """Send email notification asynchronously"""
    if not config.SMTP_HOST:
        logger.warning("SMTP not configured, skipping email")
        return False

    def _send():
        try:
            msg = EmailMessage()
            msg.set_content(body)
            msg["Subject"] = subject
            msg["From"] = config.SMTP_FROM_EMAIL
            msg["To"] = to_email

            if config.SMTP_PORT == 465:
                context = ssl.create_default_context()
                with smtplib.SMTP_SSL(config.SMTP_HOST, config.SMTP_PORT, context=context) as server:
                    if config.SMTP_USER:
                        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT) as server:
                    if config.SMTP_PORT == 587:
                        server.starttls()
                    if config.SMTP_USER:
                        server.login(config.SMTP_USER, config.SMTP_PASSWORD)
                    server.send_message(msg)
            logger.info(f"Email sent to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    return await asyncio.to_thread(_send)


async def send_telegram_message(chat_id: str, message: str) -> bool:
    """Send Telegram notification via Bot API"""
    if not config.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram Bot Token not configured, skipping telegram")
        return False

    try:
        url = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage"
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Removed parse_mode="Markdown" to avoid errors with unescaped characters
            response = await client.post(
                url, json={"chat_id": chat_id, "text": message}
            )
            if response.status_code != 200:
                logger.error(f"Telegram API error: {response.text}")
                return False
            return True
    except Exception as e:
        logger.error(f"Failed to send telegram to {chat_id}: {e}")
        return False

"""Telegram alerting — minimal bot client that degrades gracefully.

Sends factual alert messages to a configured Telegram chat. If
``TELEGRAM_CHAT_ID`` (or the bot token) is unset, or the network request
fails, ``send()`` returns ``False`` and the caller's behavior is unchanged —
alerting never raises.
"""
import html
import logging

logger = logging.getLogger(__name__)


class TelegramAlerter:
    """Minimal Telegram bot client. Degrades gracefully if TELEGRAM_CHAT_ID unset."""

    def __init__(self):
        from cudaquant.config.settings import settings

        self.token = getattr(settings, "TELEGRAM_BOT_TOKEN", None)
        self.chat_id = getattr(settings, "TELEGRAM_CHAT_ID", None)

    def send(self, message: str) -> bool:
        """Send a message. Returns True if sent, False if skipped (no chat_id) or failed."""
        if not self.token or not self.chat_id:
            return False
        try:
            import httpx

            r = httpx.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                json={
                    "chat_id": self.chat_id,
                    # parse_mode=HTML: escape dynamic content so a stray `<`/`&`
                    # in a reason/error/model id cannot break the request.
                    "text": html.escape(message),
                    "parse_mode": "HTML",
                },
                timeout=10,
            )
            return r.status_code == 200
        except Exception as e:
            logger.warning("Telegram alert not sent: %s", e)
            return False

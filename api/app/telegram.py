"""Telegram: sign-in for the Mini App, and the bot that opens it.

The Mini App (the Flutter web build at /play/) sends Telegram's signed initData in the
X-Telegram-Init-Data header. We check Telegram's HMAC signature with the bot token, so a
player can't pretend to be someone else, and map the Telegram user id to a stable Pawdex
user id. See https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
import uuid

import httpx
from fastapi import APIRouter, Body, Header, HTTPException

from app.config import settings

log = logging.getLogger(__name__)

# Namespace for turning Telegram user ids into Pawdex user ids (uuid5). Never change it,
# or every Telegram player loses their collection.
TELEGRAM_NAMESPACE = uuid.UUID("3a9c1f6e-6d8b-4b0e-9c61-2f6a0d8e5b71")
MAX_AGE_SECONDS = 24 * 3600


class InvalidInitData(ValueError):
    pass


def telegram_user_id(init_data: str, bot_token: str, now: float | None = None) -> int:
    """The Telegram user id from signed Mini App initData, or InvalidInitData."""
    fields = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = fields.pop("hash", None)
    if not received_hash:
        raise InvalidInitData("no hash")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received_hash):
        raise InvalidInitData("bad signature")
    auth_date = int(fields.get("auth_date", "0"))
    if (now or time.time()) - auth_date > MAX_AGE_SECONDS:
        raise InvalidInitData("expired")
    try:
        return int(json.loads(fields["user"])["id"])
    except (KeyError, ValueError, TypeError) as exc:
        raise InvalidInitData("no user") from exc


def pawdex_user_id(telegram_id: int) -> uuid.UUID:
    return uuid.uuid5(TELEGRAM_NAMESPACE, f"telegram:{telegram_id}")


# --- The bot -------------------------------------------------------------------------

router = APIRouter(prefix="/telegram", tags=["telegram"])


def play_url() -> str:
    return f"{settings.public_url}/play/"


def _bot_api(method: str, **payload) -> dict:
    response = httpx.post(
        f"https://api.telegram.org/bot{settings.telegram_bot_token}/{method}", json=payload, timeout=20
    )
    return response.json()


def register_bot() -> None:
    """Point Telegram at our webhook and put a "Play" button in the bot's menu.

    Runs at startup when a bot token is configured, so the token never has to leave the
    server's .env.
    """
    try:
        result = _bot_api(
            "setWebhook",
            url=f"{settings.public_url}/telegram/webhook",
            secret_token=settings.telegram_webhook_secret,
            allowed_updates=["message"],
        )
        log.info("telegram setWebhook: %s", result.get("description", result))
        result = _bot_api(
            "setChatMenuButton",
            menu_button={"type": "web_app", "text": "Play", "web_app": {"url": play_url()}},
        )
        log.info("telegram setChatMenuButton: %s", result.get("description", result))
    except httpx.HTTPError as exc:
        log.warning("could not register the Telegram bot: %s", exc)


@router.post("/webhook", include_in_schema=False)
def webhook(update: dict = Body(...), x_telegram_bot_api_secret_token: str = Header(default="")):
    # Only Telegram knows the secret we gave it in setWebhook.
    if not settings.telegram_webhook_secret or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
    ):
        raise HTTPException(status_code=403)
    message = update.get("message") or {}
    chat_id = (message.get("chat") or {}).get("id")
    if chat_id is not None:
        _bot_api(
            "sendMessage",
            chat_id=chat_id,
            text=(
                "🐾 Pawdex — collect the street cats and dogs of your city!\n\n"
                "Photograph an animal, and Pawdex recognises it: every real cat and dog gets "
                "its own card, name and map zone. Find new ones first and name them forever."
            ),
            reply_markup={"inline_keyboard": [[{"text": "🐾 Play Pawdex", "web_app": {"url": play_url()}}]]},
        )
    return {"ok": True}

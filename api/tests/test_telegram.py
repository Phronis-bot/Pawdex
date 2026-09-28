"""Telegram Mini App sign-in and the bot webhook."""
import hashlib
import hmac
import json
import time
import urllib.parse
import uuid

import pytest

from app.config import settings
from app.telegram import InvalidInitData, pawdex_user_id, telegram_user_id
from tests.helpers import client

TOKEN = "123456:TEST-TOKEN"


def signed_init_data(user_id: int, token: str = TOKEN, auth_date: int | None = None) -> str:
    """initData exactly as Telegram builds it (see core.telegram.org/bots/webapps)."""
    fields = {
        "query_id": "AAH-test",
        "user": json.dumps({"id": user_id, "first_name": "Mo"}, separators=(",", ":")),
        "auth_date": str(auth_date or int(time.time())),
    }
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(fields)


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", TOKEN)
    monkeypatch.setattr(settings, "telegram_webhook_secret", "hook-secret")
    sent = []
    monkeypatch.setattr("app.telegram._bot_api", lambda method, **payload: sent.append((method, payload)) or {})
    return sent


def test_valid_init_data_gives_the_telegram_user():
    assert telegram_user_id(signed_init_data(42), TOKEN) == 42


@pytest.mark.parametrize(
    "init_data",
    [
        signed_init_data(42, token="999:OTHER-BOT"),  # signed for another bot
        signed_init_data(42, auth_date=int(time.time()) - 3 * 24 * 3600),  # too old
        signed_init_data(42).replace("%22id%22%3A42", "%22id%22%3A43"),  # tampered user
        "user=%7B%22id%22%3A42%7D",  # no signature at all
    ],
)
def test_forged_or_stale_init_data_is_rejected(init_data):
    with pytest.raises(InvalidInitData):
        telegram_user_id(init_data, TOKEN)


def test_mini_app_player_is_signed_in_and_stable(bot):
    headers = {"X-Telegram-Init-Data": signed_init_data(777)}
    first = client.get("/me", headers=headers).json()
    again = client.get("/me", headers={"X-Telegram-Init-Data": signed_init_data(777)}).json()

    assert first["id"] == again["id"] == str(pawdex_user_id(777))


def test_forged_mini_app_request_is_refused(bot):
    headers = {"X-Telegram-Init-Data": signed_init_data(777, token="999:OTHER-BOT")}
    assert client.get("/me", headers=headers).status_code == 401


def test_anonymous_id_cannot_claim_a_telegram_player(bot):
    headers = {"X-User-Id": str(pawdex_user_id(777))}
    assert client.get("/me", headers=headers).status_code == 401
    assert client.get("/me", headers={"X-User-Id": str(uuid.uuid4())}).status_code == 200


def test_telegram_sign_in_is_off_without_a_bot_token(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert client.get("/me", headers={"X-Telegram-Init-Data": signed_init_data(1)}).status_code == 401


def test_start_message_gets_a_play_button(bot):
    update = {"message": {"chat": {"id": 555}, "text": "/start"}}

    response = client.post(
        "/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "hook-secret"}
    )

    assert response.status_code == 200
    method, payload = bot[-1]
    assert method == "sendMessage" and payload["chat_id"] == 555
    button = payload["reply_markup"]["inline_keyboard"][0][0]
    assert button["web_app"]["url"].endswith("/play/")


def test_webhook_requires_telegrams_secret(bot):
    update = {"message": {"chat": {"id": 555}, "text": "/start"}}
    assert client.post("/telegram/webhook", json=update).status_code == 403
    assert client.post(
        "/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": "guess"}
    ).status_code == 403

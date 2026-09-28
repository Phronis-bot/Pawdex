import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_session
from app.models import User
from app.nicknames import random_nickname
from app.telegram import InvalidInitData, pawdex_user_id, telegram_user_id


def current_user_id(
    x_user_id: str | None = Header(default=None, description="Anonymous id generated and stored on the device"),
    x_telegram_init_data: str | None = Header(default=None, description="Signed initData of the Telegram Mini App"),
    session: Session = Depends(get_session),
) -> uuid.UUID:
    """Who is calling: a Telegram Mini App player (verified) or an anonymous app install.

    Unknown ids are registered on first use.
    """
    if x_telegram_init_data:
        if not settings.telegram_bot_token:
            raise HTTPException(status_code=401, detail="Telegram sign-in is not enabled")
        try:
            user_id = pawdex_user_id(telegram_user_id(x_telegram_init_data, settings.telegram_bot_token))
        except InvalidInitData:
            raise HTTPException(status_code=401, detail="Invalid Telegram sign-in")
    elif x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            raise HTTPException(status_code=401, detail="X-User-Id must be a UUID")
        # Devices generate random (version 4) ids. Telegram players have version 5 ids;
        # refusing anything else stops an anonymous caller from claiming a Telegram player.
        if user_id.version != 4:
            raise HTTPException(status_code=401, detail="X-User-Id must be a random UUID")
    else:
        raise HTTPException(status_code=401, detail="Sign-in required")

    session.execute(insert(User).values(id=user_id, nickname=random_nickname()).on_conflict_do_nothing())
    session.commit()
    return user_id

import uuid

from fastapi import Depends, Header, HTTPException
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.db import get_session
from app.models import User


def current_user_id(
    x_user_id: str = Header(description="Anonymous user id generated and stored on the device"),
    session: Session = Depends(get_session),
) -> uuid.UUID:
    """Anonymous auth: the device sends its own UUID; unknown ids are registered on first use."""
    try:
        user_id = uuid.UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-User-Id must be a UUID")

    session.execute(insert(User).values(id=user_id).on_conflict_do_nothing())
    session.commit()
    return user_id

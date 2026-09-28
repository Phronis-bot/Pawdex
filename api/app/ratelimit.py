"""Upload limits, so nobody can flood the server with photos.

Per player (counted in the database, survives restarts) and per IP address (in
memory; anonymous players can make up new ids, but not new IPs as easily).
"""
import threading
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.config import settings
from app.db import get_session
from app.models import Sighting

HOUR = 3600


class SlidingWindow:
    """Counts events per key over the last `window` seconds. One API process only."""

    def __init__(self):
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window: float = HOUR) -> bool:
        """Record an event; False if the key is already at its limit."""
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - window:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(now)
            return True

    def reset(self) -> None:
        with self._lock:
            self._events.clear()


ip_uploads = SlidingWindow()


def upload_allowed(
    request: Request,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
) -> None:
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = session.scalar(
        select(func.count()).where(Sighting.user_id == user_id, Sighting.created_at >= since)
    )
    if recent >= settings.uploads_per_user_per_hour:
        raise HTTPException(status_code=429, detail="Too many photos this hour. Take a break and try later!")

    ip = request.client.host if request.client else "unknown"
    if not ip_uploads.hit(ip, settings.uploads_per_ip_per_hour):
        raise HTTPException(status_code=429, detail="Too many photos from this network. Try again later.")

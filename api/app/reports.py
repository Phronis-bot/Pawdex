"""Players can report other players' photos. Enough reports hide the photo from everyone
except its author, until someone reviews it."""
import enum
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.config import settings
from app.db import get_session
from app.models import Report, Sighting

router = APIRouter(prefix="/sightings", tags=["reports"])


class ReportReason(str, enum.Enum):
    not_an_animal = "not_an_animal"
    person_visible = "person_visible"
    reveals_location = "reveals_location"
    inappropriate = "inappropriate"
    other = "other"


class ReportIn(BaseModel):
    reason: ReportReason


@router.post("/{sighting_id}/report", status_code=204)
def report_sighting(
    sighting_id: uuid.UUID,
    body: ReportIn,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    sighting = session.get(Sighting, sighting_id)
    # Only photos others can see (linked to an animal) can be reported, and not your own.
    if sighting is None or sighting.animal_id is None or sighting.user_id == user_id:
        raise HTTPException(status_code=404, detail="Sighting not found")

    # One report per player per photo; reporting again is a no-op.
    session.execute(
        insert(Report)
        .values(id=uuid.uuid4(), sighting_id=sighting_id, user_id=user_id, reason=body.reason.value)
        .on_conflict_do_nothing()
    )
    reporters = session.scalar(select(func.count()).where(Report.sighting_id == sighting_id))
    if reporters >= settings.reports_to_hide:
        sighting.hidden = True
    session.commit()

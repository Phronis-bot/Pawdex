import uuid

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.db import get_session
from app.models import Animal, Sighting
from app.schemas import AnimalOut, animal_out
from app.storage import PhotoStorage, get_storage

router = APIRouter(prefix="/animals", tags=["animals"])


def _animal(session: Session, animal_id: uuid.UUID) -> Animal:
    animal = session.get(Animal, animal_id)
    if animal is None:
        raise HTTPException(status_code=404, detail="Animal not found")
    return animal


class NameIn(BaseModel):
    name: str = Field(min_length=1, max_length=30)


@router.put("/{animal_id}/name", response_model=AnimalOut)
def name_animal(
    animal_id: uuid.UUID,
    body: NameIn,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    """The discoverer names the animal, once and forever."""
    name = body.name.strip()
    if not name:
        raise HTTPException(status_code=422, detail="Name must not be blank")

    # Lock the row so two requests can't both see "unnamed" and both set a name.
    animal = session.scalar(select(Animal).where(Animal.id == animal_id).with_for_update())
    if animal is None:
        raise HTTPException(status_code=404, detail="Animal not found")
    if animal.discoverer_id != user_id:
        raise HTTPException(status_code=403, detail="Only the discoverer can name this animal")
    if animal.name is not None:
        raise HTTPException(status_code=409, detail="This animal already has a name")

    animal.name = name
    session.commit()
    return animal_out(session, animal, user_id)


@router.get("/{animal_id}/photo", response_class=Response)
def animal_photo(
    animal_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
    storage: PhotoStorage = Depends(get_storage),
):
    """The animal's first photo, used to show candidates ("Is it Mo?")."""
    _animal(session, animal_id)
    key = session.scalar(
        select(Sighting.photo_key)
        .where(Sighting.animal_id == animal_id)
        .order_by(Sighting.created_at)
        .limit(1)
    )
    if key is None:
        raise HTTPException(status_code=404, detail="No photo yet")
    return Response(content=storage.read(key), media_type="image/jpeg")

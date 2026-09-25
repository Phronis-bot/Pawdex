import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from geoalchemy2 import WKTElement
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.classifier import ClipClassifier, get_classifier
from app.config import settings
from app.db import get_session
from app.models import Sighting, Species
from app.photos import InvalidImage, encode_for_storage, load_image
from app.storage import PhotoStorage, get_storage

router = APIRouter(prefix="/sightings", tags=["sightings"])


class SightingOut(BaseModel):
    """Public view of a sighting. Deliberately has no coordinates (exact location stays server-side)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    species: Species
    confidence: float
    created_at: datetime


@router.post("", status_code=201, response_model=SightingOut)
def create_sighting(
    photo: UploadFile,
    latitude: float = Form(ge=-90, le=90),
    longitude: float = Form(ge=-180, le=180),
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
    storage: PhotoStorage = Depends(get_storage),
    classifier: ClipClassifier = Depends(get_classifier),
):
    data = photo.file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Photo is too large")
    try:
        image = load_image(data)
    except InvalidImage:
        raise HTTPException(status_code=415, detail="Not a supported image")

    result = classifier.classify(image)
    if result.species is None:
        # Nothing to keep: the photo is not stored and no sighting is created.
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "no_animal",
                    "message": "No cat or dog found in this photo. Try getting closer.",
                }
            },
        )

    key = storage.save(encode_for_storage(image, settings.photo_max_side), "jpg")
    sighting = Sighting(
        user_id=user_id,
        species=result.species,
        confidence=result.confidence,
        photo_key=key,
        location=WKTElement(f"POINT({longitude} {latitude})", srid=4326),
    )
    session.add(sighting)
    session.commit()
    return sighting


@router.get("/mine", response_model=list[SightingOut])
def my_sightings(
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    return session.scalars(
        select(Sighting).where(Sighting.user_id == user_id).order_by(Sighting.created_at.desc())
    ).all()


@router.get("/{sighting_id}/photo", response_class=Response)
def sighting_photo(
    sighting_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
    storage: PhotoStorage = Depends(get_storage),
):
    sighting = session.get(Sighting, sighting_id)
    # Only the author sees their photos for now; 404 either way to avoid probing ids.
    if sighting is None or sighting.user_id != user_id:
        raise HTTPException(status_code=404, detail="Sighting not found")
    return Response(content=storage.read(sighting.photo_key), media_type="image/jpeg")

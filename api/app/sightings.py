import uuid

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, Response
from geoalchemy2 import WKTElement
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.auth import current_user_id
from app.classifier import ClipClassifier, get_classifier
from app.coats import new_animal
from app.config import settings
from app.db import get_session
from app.embedder import Embedder, get_embedder
from app.matching import Outcome, decide, find_candidates
from app.models import Sighting
from app.photos import InvalidImage, encode_for_storage, load_image
from app.schemas import CandidateOut, SightingOut, SightingResult, candidates_out, sighting_out, sighting_result
from app.storage import PhotoStorage, get_storage

router = APIRouter(prefix="/sightings", tags=["sightings"])


@router.post("", status_code=201, response_model=SightingResult)
def create_sighting(
    photo: UploadFile,
    latitude: float = Form(ge=-90, le=90),
    longitude: float = Form(ge=-180, le=180),
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
    storage: PhotoStorage = Depends(get_storage),
    classifier: ClipClassifier = Depends(get_classifier),
    embedder: Embedder = Depends(get_embedder),
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

    sighting = Sighting(
        user_id=user_id,
        species=result.species,
        confidence=result.confidence,
        photo_key=storage.save(encode_for_storage(image, settings.photo_max_side), "jpg"),
        location=WKTElement(f"POINT({longitude} {latitude})", srid=4326),
        embedding=embedder.embed(image),
        embedding_model=embedder.name,
    )
    session.add(sighting)
    session.flush()

    candidates = find_candidates(session, sighting)
    outcome = decide(candidates)
    if outcome is Outcome.match:
        sighting.animal_id = candidates[0].animal.id
    elif outcome is Outcome.new:
        sighting.animal = new_animal(image, sighting.species, user_id)
    # Outcome.uncertain: stays pending until the player answers via /resolve.
    session.commit()
    return sighting_result(session, sighting, outcome, candidates, user_id)


@router.get("/mine", response_model=list[SightingOut])
def my_sightings(
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    sightings = session.scalars(
        select(Sighting)
        .where(Sighting.user_id == user_id)
        .options(selectinload(Sighting.animal))
        .order_by(Sighting.created_at.desc())
    ).all()
    return [sighting_out(s, user_id) for s in sightings]


def _own_sighting(session: Session, sighting_id: uuid.UUID, user_id: uuid.UUID) -> Sighting:
    sighting = session.get(Sighting, sighting_id)
    # 404 for other people's sightings too, to avoid probing ids.
    if sighting is None or sighting.user_id != user_id:
        raise HTTPException(status_code=404, detail="Sighting not found")
    return sighting


def _pending_sighting(session: Session, sighting_id: uuid.UUID, user_id: uuid.UUID) -> Sighting:
    sighting = _own_sighting(session, sighting_id, user_id)
    if not sighting.pending:
        raise HTTPException(status_code=409, detail="This sighting is not waiting for confirmation")
    return sighting


@router.get("/{sighting_id}/candidates", response_model=list[CandidateOut])
def sighting_candidates(
    sighting_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    sighting = _pending_sighting(session, sighting_id, user_id)
    return candidates_out(session, find_candidates(session, sighting), user_id)


class ResolveIn(BaseModel):
    # One of the candidates, or null for "it's a new animal".
    animal_id: uuid.UUID | None = None


@router.post("/{sighting_id}/resolve", response_model=SightingResult)
def resolve_sighting(
    sighting_id: uuid.UUID,
    body: ResolveIn,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
    storage: PhotoStorage = Depends(get_storage),
):
    """The player's answer to "Is it Mo, or someone new?"."""
    sighting = _pending_sighting(session, sighting_id, user_id)

    if body.animal_id is None:
        image = load_image(storage.read(sighting.photo_key))
        sighting.animal = new_animal(image, sighting.species, user_id)
        outcome = Outcome.new
    else:
        # Only animals we actually offered: no linking to arbitrary animals elsewhere.
        if body.animal_id not in {c.animal.id for c in find_candidates(session, sighting)}:
            raise HTTPException(status_code=422, detail="That animal is not a candidate for this sighting")
        sighting.animal_id = body.animal_id
        outcome = Outcome.match
    session.commit()
    return sighting_result(session, sighting, outcome, [], user_id)


@router.get("/{sighting_id}/photo", response_class=Response)
def sighting_photo(
    sighting_id: uuid.UUID,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
    storage: PhotoStorage = Depends(get_storage),
):
    """Photos of sightings linked to an animal are public (they form its chronicle);
    unconfirmed ones stay private to their author."""
    sighting = session.get(Sighting, sighting_id)
    if sighting is None or (sighting.animal_id is None and sighting.user_id != user_id):
        raise HTTPException(status_code=404, detail="Sighting not found")
    return Response(content=storage.read(sighting.photo_key), media_type="image/jpeg")

"""API response shapes. None of them carries coordinates: exact locations stay server-side."""
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.matching import Candidate, Outcome
from app.models import Animal, Sighting, Species


class AnimalRef(BaseModel):
    id: uuid.UUID
    name: str | None


class AnimalOut(BaseModel):
    id: uuid.UUID
    species: Species
    name: str | None
    sightings_count: int
    # True only for the discoverer, and only until the name is set.
    can_name: bool


class SightingOut(BaseModel):
    id: uuid.UUID
    species: Species
    confidence: float
    created_at: datetime
    # True while the player still has to say which animal this is.
    pending: bool
    animal: AnimalRef | None


class CandidateOut(BaseModel):
    animal: AnimalOut
    similarity: float


class SightingResult(BaseModel):
    sighting: SightingOut
    outcome: Outcome
    animal: AnimalOut | None
    # Only filled when outcome is "uncertain".
    candidates: list[CandidateOut]


def animal_out(session: Session, animal: Animal, user_id: uuid.UUID) -> AnimalOut:
    count = session.scalar(select(func.count()).where(Sighting.animal_id == animal.id))
    return AnimalOut(
        id=animal.id,
        species=animal.species,
        name=animal.name,
        sightings_count=count,
        can_name=animal.name is None and animal.discoverer_id == user_id,
    )


def sighting_out(sighting: Sighting) -> SightingOut:
    animal = sighting.animal
    return SightingOut(
        id=sighting.id,
        species=sighting.species,
        confidence=sighting.confidence,
        created_at=sighting.created_at,
        pending=sighting.pending,
        animal=AnimalRef(id=animal.id, name=animal.name) if animal else None,
    )


def candidates_out(session: Session, candidates: list[Candidate], user_id: uuid.UUID) -> list[CandidateOut]:
    return [
        CandidateOut(animal=animal_out(session, c.animal, user_id), similarity=c.similarity)
        for c in candidates
    ]


def sighting_result(
    session: Session,
    sighting: Sighting,
    outcome: Outcome,
    candidates: list[Candidate],
    user_id: uuid.UUID,
) -> SightingResult:
    session.refresh(sighting)
    return SightingResult(
        sighting=sighting_out(sighting),
        outcome=outcome,
        animal=animal_out(session, sighting.animal, user_id) if sighting.animal else None,
        candidates=candidates_out(session, candidates, user_id) if outcome is Outcome.uncertain else [],
    )

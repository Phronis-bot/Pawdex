"""API response shapes. None of them carries coordinates: exact locations stay server-side."""
import uuid
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.breeds import BREEDS, Certainty
from app.coats import COATS, Rarity
from app.matching import Candidate, Outcome
from app.models import Animal, Sighting, Species, User
from app.street import street


class AnimalRef(BaseModel):
    id: uuid.UUID
    name: str | None
    can_name: bool


class AnimalOut(BaseModel):
    id: uuid.UUID
    species: Species
    name: str | None
    sightings_count: int
    # True only for the discoverer, and only until the name is set.
    can_name: bool
    # Null only for animals discovered before coats existed and not yet backfilled.
    rarity: Rarity | None


class ChronicleEntry(BaseModel):
    sighting_id: uuid.UUID
    created_at: datetime
    by: str  # photographer's nickname
    by_me: bool


class BreedOut(BaseModel):
    name: str
    # False means "looks like": the photo matches this breed best, but not surely enough.
    certain: bool
    # "confirmed" ("Siamese"), "likely" ("Looks like a Siamese") or "maybe" ("Maybe a
    # Siamese or a Thai": a guess; `also` is the second breed's name, if there is one).
    certainty: str
    also: str | None = None
    origin: str
    history: str
    relatives: str
    facts: list[str]


class CoatOption(BaseModel):
    key: str
    label: str


class StreetOut(BaseModel):
    name: str  # "Chó cỏ · local street dog", "Local street cat"
    facts: list[str]


class AnimalCard(AnimalOut):
    discovered_by: str  # discoverer's nickname
    discovered_by_me: bool
    # Null when the model wasn't sure and nobody picked one (no coat facts then either).
    coat: str | None
    coat_key: str | None = None
    coat_facts: list[str]
    coat_by_player: bool = False
    # Only for the discoverer: the coats they may pick from ("Wrong coat? Pick yours").
    coat_options: list[CoatOption] = []
    # Only on the card, never in map/zone/candidate responses.
    breed: BreedOut | None
    # True: no breed, because it's probably a mixed breed (rather than unknown).
    breed_mixed: bool = False
    # When there is no breed (mixed or unknown): the local street-animal name and facts.
    street: StreetOut | None = None
    # Oldest first; photos via GET /sightings/{sighting_id}/photo.
    chronicle: list[ChronicleEntry]


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
        can_name=_can_name(animal, user_id),
        rarity=animal.rarity,
    )


def animal_card(session: Session, animal: Animal, user_id: uuid.UUID) -> AnimalCard:
    coat = COATS[animal.species].get(animal.coat) if animal.coat else None
    breed = BREEDS[animal.species].get(animal.breed) if animal.breed else None
    also = BREEDS[animal.species].get(animal.breed_alt) if animal.breed_alt else None
    local = street(animal.species, animal.country)
    entries = session.execute(
        select(Sighting.id, Sighting.created_at, Sighting.user_id, User.nickname)
        .join(User, User.id == Sighting.user_id)
        .where(Sighting.animal_id == animal.id)
        # Reported photos disappear from the chronicle, except for their author.
        .where(or_(Sighting.hidden.is_(False), Sighting.user_id == user_id))
        .order_by(Sighting.created_at)
    ).all()
    return AnimalCard(
        **animal_out(session, animal, user_id).model_dump(),
        discovered_by=animal.discoverer.nickname,
        discovered_by_me=animal.discoverer_id == user_id,
        coat=coat.label if coat else None,
        coat_key=animal.coat if coat else None,
        coat_facts=list(coat.facts) if coat else [],
        coat_by_player=animal.coat_by_player,
        coat_options=[CoatOption(key=k, label=c.label) for k, c in COATS[animal.species].items()]
        if animal.discoverer_id == user_id else [],
        breed=BreedOut(
            name=breed.label,
            certain=animal.breed_certainty == Certainty.confirmed.value,
            certainty=animal.breed_certainty or Certainty.confirmed.value,
            also=also.label if also else None,
            origin=breed.origin,
            history=breed.history,
            relatives=breed.relatives,
            facts=list(breed.facts),
        ) if breed else None,
        breed_mixed=animal.breed_certainty == Certainty.mixed.value,
        street=StreetOut(name=local.name, facts=list(local.facts)) if not breed else None,
        chronicle=[
            ChronicleEntry(sighting_id=sid, created_at=at, by=nickname, by_me=uid == user_id)
            for sid, at, uid, nickname in entries
        ],
    )


def _can_name(animal: Animal, user_id: uuid.UUID) -> bool:
    return animal.name is None and animal.discoverer_id == user_id


def sighting_out(sighting: Sighting, user_id: uuid.UUID) -> SightingOut:
    animal = sighting.animal
    return SightingOut(
        id=sighting.id,
        species=sighting.species,
        confidence=sighting.confidence,
        created_at=sighting.created_at,
        pending=sighting.pending,
        animal=AnimalRef(id=animal.id, name=animal.name, can_name=_can_name(animal, user_id)) if animal else None,
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
        sighting=sighting_out(sighting, user_id),
        outcome=outcome,
        animal=animal_out(session, sighting.animal, user_id) if sighting.animal else None,
        candidates=candidates_out(session, candidates, user_id) if outcome is Outcome.uncertain else [],
    )

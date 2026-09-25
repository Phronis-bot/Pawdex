"""Which known animal is in a new photo? Only neighbours of the same species are considered."""
import enum
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.config import settings
from app.models import Animal, Sighting


class Outcome(str, enum.Enum):
    match = "match"  # confident: "It's Mo!"
    uncertain = "uncertain"  # ask the player: "Mo, or someone new?"
    new = "new"  # nobody similar nearby


@dataclass(frozen=True)
class Candidate:
    animal: Animal
    similarity: float


def find_candidates(session: Session, sighting: Sighting) -> list[Candidate]:
    """Animals of the same species seen within the radius, most similar first.

    An animal's similarity is its best score over all its sightings, so the more
    photos we have of it, the easier it is to recognise. `sighting` must be flushed.
    """
    me = aliased(Sighting)
    similarity = func.max(1 - Sighting.embedding.cosine_distance(me.embedding)).label("similarity")
    rows = session.execute(
        select(Sighting.animal_id, similarity)
        .join(me, me.id == sighting.id)
        .where(
            Sighting.animal_id.is_not(None),
            Sighting.species == me.species,
            Sighting.embedding_model == me.embedding_model,
            Sighting.id != me.id,
            func.ST_DWithin(Sighting.location, me.location, settings.match_radius_m),
        )
        .group_by(Sighting.animal_id)
        .having(similarity >= settings.match_uncertain)
        .order_by(similarity.desc())
        .limit(settings.match_max_candidates)
    ).all()
    return [Candidate(session.get(Animal, animal_id), sim) for animal_id, sim in rows]


def decide(candidates: list[Candidate]) -> Outcome:
    if not candidates:
        return Outcome.new
    if candidates[0].similarity >= settings.match_confident:
        return Outcome.match
    return Outcome.uncertain

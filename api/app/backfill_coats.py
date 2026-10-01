"""One-off: detect coat, rarity and breed for animals discovered before those existed.

Usage (inside the api container):  python -m app.backfill_coats [--breeds] [--coats]

--breeds re-detects the breed of every animal (e.g. after changing the breed model
or threshold). Coats are normally only filled where missing, since rarity shouldn't
change under players' feet; --coats re-detects them too, for fixing detection mistakes
(e.g. after adding a coat that was missing from the table); coats players picked by hand
are kept. Every run also fills in the country of discovery.
"""
import sys

from sqlalchemy import or_, select

from app.breeds import detect_breed
from app.coats import animal_crop, detect_coat, rarity_of
from app.db import SessionLocal
from app.models import Animal, Sighting
from app.photos import load_image
from app.sightings import sighting_country
from app.storage import get_storage


def main() -> None:
    redo_breeds = "--breeds" in sys.argv
    redo_coats = "--coats" in sys.argv
    storage = get_storage()
    with SessionLocal() as session:
        query = select(Animal)
        if not (redo_breeds or redo_coats):
            query = query.where(or_(Animal.coat.is_(None), Animal.breed.is_(None)))
        for animal in session.scalars(query):
            first = session.scalar(
                select(Sighting).where(Sighting.animal_id == animal.id).order_by(Sighting.created_at).limit(1)
            )
            animal.country = sighting_country(session, first)
            crop = animal_crop(load_image(storage.read(first.photo_key)), animal.species)
            if (animal.coat is None or redo_coats) and not animal.coat_by_player:
                animal.coat = detect_coat(crop, animal.species)
                animal.rarity = rarity_of(animal.species, animal.coat)
            breed = detect_breed(crop, animal.species)
            animal.breed = breed.key if breed else None
            animal.breed_certainty = breed.certainty.value if breed else None
            animal.breed_alt = breed.alt if breed else None
            label = f"{animal.breed} / {animal.breed_alt} ({animal.breed_certainty})" if breed else "unknown"
            print(f"{animal.name or animal.id}: {animal.coat} ({animal.rarity}), breed={label}, country={animal.country}")
        session.commit()


if __name__ == "__main__":
    main()

"""One-off: detect coat, rarity and breed for animals discovered before those existed.

Usage (inside the api container):  python -m app.backfill_coats [--breeds]

--breeds re-detects the breed of every animal (e.g. after changing the breed model
or threshold); coats are only filled where missing, since rarity must not change.
"""
import sys

from sqlalchemy import or_, select

from app.breeds import detect_breed
from app.coats import COATS, detect_coat
from app.db import SessionLocal
from app.models import Animal, Sighting
from app.photos import load_image
from app.storage import get_storage


def main() -> None:
    redo_breeds = "--breeds" in sys.argv
    storage = get_storage()
    with SessionLocal() as session:
        query = select(Animal)
        if not redo_breeds:
            query = query.where(or_(Animal.coat.is_(None), Animal.breed.is_(None)))
        for animal in session.scalars(query):
            first_photo = session.scalar(
                select(Sighting.photo_key)
                .where(Sighting.animal_id == animal.id)
                .order_by(Sighting.created_at)
                .limit(1)
            )
            image = load_image(storage.read(first_photo))
            if animal.coat is None:
                animal.coat = detect_coat(image, animal.species)
                animal.rarity = COATS[animal.species][animal.coat].rarity.value
            animal.breed = detect_breed(image, animal.species)
            print(f"{animal.name or animal.id}: {animal.coat} ({animal.rarity}), breed={animal.breed or 'mixed'}")
        session.commit()


if __name__ == "__main__":
    main()

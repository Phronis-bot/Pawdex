"""One-off: detect coat, rarity and breed for animals discovered before those existed.

Usage (inside the api container):  python -m app.backfill_coats [--breeds] [--coats]

--breeds re-detects the breed of every animal (e.g. after changing the breed model
or threshold). Coats are normally only filled where missing, since rarity shouldn't
change under players' feet; --coats re-detects them too, for fixing detection mistakes
(e.g. after adding a coat that was missing from the table).
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
    redo_coats = "--coats" in sys.argv
    storage = get_storage()
    with SessionLocal() as session:
        query = select(Animal)
        if not (redo_breeds or redo_coats):
            query = query.where(or_(Animal.coat.is_(None), Animal.breed.is_(None)))
        for animal in session.scalars(query):
            first_photo = session.scalar(
                select(Sighting.photo_key)
                .where(Sighting.animal_id == animal.id)
                .order_by(Sighting.created_at)
                .limit(1)
            )
            image = load_image(storage.read(first_photo))
            if animal.coat is None or redo_coats:
                animal.coat = detect_coat(image, animal.species)
                animal.rarity = COATS[animal.species][animal.coat].rarity.value
            breed = detect_breed(image, animal.species)
            animal.breed = breed[0] if breed else None
            animal.breed_certainty = breed[1].value if breed else None
            label = f"{animal.breed} ({animal.breed_certainty})" if breed else "unknown"
            print(f"{animal.name or animal.id}: {animal.coat} ({animal.rarity}), breed={label}")
        session.commit()


if __name__ == "__main__":
    main()

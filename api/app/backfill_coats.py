"""One-off: detect coat and rarity for animals discovered before phase 4.

Usage (inside the api container):  python -m app.backfill_coats
"""
from sqlalchemy import select

from app.coats import COATS, detect_coat
from app.db import SessionLocal
from app.models import Animal, Sighting
from app.photos import load_image
from app.storage import get_storage


def main() -> None:
    storage = get_storage()
    with SessionLocal() as session:
        for animal in session.scalars(select(Animal).where(Animal.coat.is_(None))):
            first_photo = session.scalar(
                select(Sighting.photo_key)
                .where(Sighting.animal_id == animal.id)
                .order_by(Sighting.created_at)
                .limit(1)
            )
            animal.coat = detect_coat(load_image(storage.read(first_photo)), animal.species)
            animal.rarity = COATS[animal.species][animal.coat].rarity.value
            print(f"{animal.name or animal.id}: {animal.coat} ({animal.rarity})")
        session.commit()


if __name__ == "__main__":
    main()

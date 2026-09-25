"""One-off: bring sightings stored before background blurring up to date.

Blurs the background of each stored photo and recomputes the re-identification
embedding from the animal crop, so old sightings keep matching new ones. Safe to
re-run: already processed sightings are skipped. Pre-phase-2 sightings (no
embedding, private to their author) are left alone.

Usage (inside the api container):  python -m app.reprocess_photos
"""
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.embedder import get_embedder
from app.models import Sighting
from app.photos import encode_for_storage, load_image
from app.segment import prepare_photo, reid_model_name
from app.storage import get_storage


def main() -> None:
    storage, embedder = get_storage(), get_embedder()
    target = reid_model_name(embedder)
    with SessionLocal() as session:
        todo = session.scalars(
            select(Sighting).where(Sighting.embedding.is_not(None), Sighting.embedding_model != target)
        ).all()
        replaced = []
        for sighting in todo:
            subject, stored = prepare_photo(load_image(storage.read(sighting.photo_key)), sighting.species)
            replaced.append(sighting.photo_key)
            sighting.photo_key = storage.save(encode_for_storage(stored, settings.photo_max_side), "jpg")
            sighting.embedding = embedder.embed(subject)
            sighting.embedding_model = target
            print(f"{sighting.id}: blurred and re-embedded")
        session.commit()
    # Only after the commit: the unblurred originals must not outlive the switch.
    for key in replaced:
        storage.delete(key)
    print(f"done: {len(todo)} sightings")


if __name__ == "__main__":
    main()

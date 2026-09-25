import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geography
from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Species(str, enum.Enum):
    cat = "cat"
    dog = "dog"


class User(Base):
    """Anonymous player identified by an id generated on the device."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Animal(Base):
    """One real, individual street animal."""

    __tablename__ = "animals"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    species: Mapped[Species] = mapped_column(Enum(Species, name="species"))
    # Given once by the discoverer and never changed.
    name: Mapped[str | None] = mapped_column(String(30))
    discoverer_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Sighting(Base):
    __tablename__ = "sightings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), index=True)
    species: Mapped[Species] = mapped_column(Enum(Species, name="species"))
    confidence: Mapped[float] = mapped_column(Float)
    photo_key: Mapped[str] = mapped_column(String(255))
    # Exact location. Server-side only: never serialize this to API responses.
    # The GiST index is created by migration 0002.
    location: Mapped[str] = mapped_column(Geography("POINT", srid=4326, spatial_index=False))
    # Null while the player hasn't confirmed which animal this is (or for pre-phase-2 rows).
    animal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("animals.id"), index=True)
    # Null only for sightings created before re-identification existed.
    embedding: Mapped[list[float] | None] = mapped_column(Vector())
    embedding_model: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    animal: Mapped[Animal | None] = relationship()

    @property
    def pending(self) -> bool:
        """Waiting for the player to say which animal this is."""
        return self.animal_id is None and self.embedding is not None

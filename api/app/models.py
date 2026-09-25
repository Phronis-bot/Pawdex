import enum
import uuid
from datetime import datetime

from geoalchemy2 import Geography
from sqlalchemy import DateTime, Enum, Float, ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


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
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

"""Map API: animals are only ever exposed as the H3 cell they live in.

Rule 3 of the product: exact locations stay on the server. Everything this module
returns is derived from the cell id alone (its centre and outline), so moving an
animal anywhere inside its cell does not change a single byte of the response.
"""
import uuid
from collections import defaultdict

import h3
from fastapi import APIRouter, Depends, HTTPException, Query
from geoalchemy2 import Geography, Geometry
from pydantic import BaseModel
from sqlalchemy import cast, func, select
from sqlalchemy.orm import Session

from app.auth import current_user_id
from app.config import settings
from app.db import get_session
from app.models import Animal, Sighting, Species
from app.schemas import AnimalOut, animal_out

router = APIRouter(prefix="/map", tags=["map"])


class Zone(BaseModel):
    cell: str
    # Cell geometry only: [lat, lon] of the hexagon's centre and corners.
    center: tuple[float, float]
    boundary: list[tuple[float, float]]
    cats: int
    dogs: int


def _home_cells(session: Session, lat: float, lon: float, radius_m: float) -> dict[uuid.UUID, tuple[str, Species]]:
    """Animal id -> (H3 cell of its most recent sighting, species), for animals near a point.

    Exact coordinates are read here and immediately reduced to a cell id.
    """
    latest = (
        select(Sighting.animal_id, Sighting.location)
        .where(Sighting.animal_id.is_not(None))
        .distinct(Sighting.animal_id)
        .order_by(Sighting.animal_id, Sighting.created_at.desc())
        .subquery()
    )
    point = cast(func.ST_SetSRID(func.ST_MakePoint(lon, lat), 4326), Geography)
    exact = cast(latest.c.location, Geometry)
    rows = session.execute(
        select(latest.c.animal_id, Animal.species, func.ST_Y(exact), func.ST_X(exact))
        .join(Animal, Animal.id == latest.c.animal_id)
        .where(func.ST_DWithin(latest.c.location, point, radius_m))
    ).all()
    return {
        animal_id: (h3.latlng_to_cell(a_lat, a_lon, settings.map_cell_resolution), species)
        for animal_id, species, a_lat, a_lon in rows
    }


def _zone(cell: str, cats: int, dogs: int) -> Zone:
    return Zone(
        cell=cell,
        center=h3.cell_to_latlng(cell),
        boundary=list(h3.cell_to_boundary(cell)),
        cats=cats,
        dogs=dogs,
    )


@router.get("/zones", response_model=list[Zone])
def zones(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    radius_m: float = Query(default=2000, gt=0),
    _: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    """Zones with animals around a point (typically the map's centre)."""
    counts: dict[str, dict[Species, int]] = defaultdict(lambda: defaultdict(int))
    for cell, species in _home_cells(session, lat, lon, min(radius_m, settings.map_max_radius_m)).values():
        counts[cell][species] += 1
    return [_zone(cell, c[Species.cat], c[Species.dog]) for cell, c in sorted(counts.items())]


@router.get("/zones/{cell}/animals", response_model=list[AnimalOut])
def zone_animals(
    cell: str,
    user_id: uuid.UUID = Depends(current_user_id),
    session: Session = Depends(get_session),
):
    """Animals whose most recent sighting is in this cell."""
    if not h3.is_valid_cell(cell) or h3.get_resolution(cell) != settings.map_cell_resolution:
        raise HTTPException(status_code=404, detail="Unknown zone")

    lat, lon = h3.cell_to_latlng(cell)
    # A circle around the centre that surely covers the whole hexagon.
    radius = 2 * h3.average_hexagon_edge_length(settings.map_cell_resolution, unit="m")
    ids = [animal_id for animal_id, (c, _) in _home_cells(session, lat, lon, radius).items() if c == cell]
    animals = session.scalars(select(Animal).where(Animal.id.in_(ids)).order_by(Animal.created_at)).all()
    return [animal_out(session, a, user_id) for a in animals]

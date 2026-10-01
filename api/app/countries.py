"""Which country a point is in — only for countries with local names for street animals.

Borders come from Natural Earth (1:50m admin-0 countries, public domain), rounded to
~100 m; countries.json holds only the countries listed in app/street.py. Points near a
border may land on the wrong side, which only changes a name on the card.
"""
import json
from functools import lru_cache
from pathlib import Path


@lru_cache
def _borders() -> dict[str, list[tuple[tuple[float, float, float, float], list[list[list[float]]]]]]:
    """Country code -> [(bounding box, rings)] per polygon; the first ring is the outline,
    the others are holes."""
    data = json.loads((Path(__file__).parent / "countries.json").read_text())
    out = {}
    for code, polygons in data.items():
        out[code] = []
        for rings in polygons:
            xs = [x for x, _ in rings[0]]
            ys = [y for _, y in rings[0]]
            out[code].append(((min(xs), min(ys), max(xs), max(ys)), rings))
    return out


def _inside(lon: float, lat: float, ring: list[list[float]]) -> bool:
    """Ray casting: count the ring's edges crossed by a ray going east from the point."""
    inside = False
    for (x1, y1), (x2, y2) in zip(ring, ring[1:] + ring[:1]):
        if (y1 > lat) != (y2 > lat) and lon < x1 + (lat - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return inside


def country_at(latitude: float, longitude: float) -> str | None:
    """ISO 3166 code ("VN", "RU") of the country at this point, or None for any other."""
    for code, polygons in _borders().items():
        for (x0, y0, x1, y1), rings in polygons:
            if x0 <= longitude <= x1 and y0 <= latitude <= y1 and _inside(longitude, latitude, rings[0]):
                if not any(_inside(longitude, latitude, hole) for hole in rings[1:]):
                    return code
    return None

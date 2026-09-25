"""Map zones, and rule 3: exact locations never leave the server."""
import h3
import pytest

from app.config import settings
from tests.conftest import BASE_VECTOR, vector_with_similarity
from tests.helpers import client, fixture, fresh_spot, new_user, post_photo

pytestmark = pytest.mark.usefixtures("fake_embedder")

CAT, DOG = fixture("cat_1.jpg"), fixture("dog_1.jpg")
RES = settings.map_cell_resolution


def zones(headers, lat, lon, radius_m=1000):
    response = client.get("/map/zones", headers=headers, params={"lat": lat, "lon": lon, "radius_m": radius_m})
    assert response.status_code == 200, response.text
    return response


def point_in_cell(cell: str, towards_corner: int, fraction: float) -> tuple[float, float]:
    """A point strictly inside `cell`, part-way from its centre towards one corner."""
    c_lat, c_lon = h3.cell_to_latlng(cell)
    v_lat, v_lon = h3.cell_to_boundary(cell)[towards_corner]
    lat, lon = c_lat + (v_lat - c_lat) * fraction, c_lon + (v_lon - c_lon) * fraction
    assert h3.latlng_to_cell(lat, lon, RES) == cell
    return lat, lon


def test_cells_are_between_250_and_500_metres_across():
    width = 2 * h3.average_hexagon_edge_length(RES, unit="m")
    assert 250 <= width <= 500


def test_zone_counts_cats_and_dogs_in_their_home_cell():
    player = new_user()
    cell = h3.latlng_to_cell(*fresh_spot(), RES)
    post_photo(player, CAT, *point_in_cell(cell, 0, 0.3))
    post_photo(player, CAT, *point_in_cell(cell, 2, 0.3))
    post_photo(player, DOG, *point_in_cell(cell, 4, 0.3))

    body = zones(player, *h3.cell_to_latlng(cell)).json()

    assert body == [
        {
            "cell": cell,
            "center": list(h3.cell_to_latlng(cell)),
            "boundary": [list(v) for v in h3.cell_to_boundary(cell)],
            "cats": 2,
            "dogs": 1,
        }
    ]


def test_zone_response_is_identical_wherever_the_animal_is_inside_the_cell(fake_embedder):
    """The strongest form of rule 3: the response carries no information beyond the cell."""
    player, viewer = new_user(), new_user()
    cell = h3.latlng_to_cell(*fresh_spot(), RES)
    center = h3.cell_to_latlng(cell)

    fake_embedder.queue.append(BASE_VECTOR)
    animal_id = post_photo(player, CAT, *point_in_cell(cell, 0, 0.2)).json()["animal"]["id"]
    before = zones(viewer, *center).text

    # Seen again on the far side of the same cell: its latest (exact) location changes.
    fake_embedder.queue.append(vector_with_similarity(0.95))
    again = post_photo(player, CAT, *point_in_cell(cell, 3, 0.8)).json()
    assert again["animal"]["id"] == animal_id
    after = zones(viewer, *center).text

    assert before == after


def test_exact_coordinates_never_appear_in_map_responses():
    player = new_user()
    lat, lon = fresh_spot()
    animal_id = post_photo(player, CAT, lat, lon).json()["animal"]["id"]
    cell = h3.latlng_to_cell(lat, lon, RES)

    responses = [
        zones(player, lat, lon),
        client.get(f"/map/zones/{cell}/animals", headers=player),
    ]

    for response in responses:
        # post_photo sent str(lat)/str(lon); an echo of the exact value would contain them.
        assert str(lat) not in response.text
        assert str(lon) not in response.text
    assert [a["id"] for a in responses[1].json()] == [animal_id]


def test_animal_counts_only_in_the_cell_of_its_latest_sighting(fake_embedder):
    player = new_user()
    old_cell = h3.latlng_to_cell(*fresh_spot(), RES)
    c_lat, c_lon = h3.cell_to_latlng(old_cell)
    v_lat, v_lon = h3.cell_to_boundary(old_cell)[0]
    inside = (c_lat + (v_lat - c_lat) * 0.9, c_lon + (v_lon - c_lon) * 0.9)
    # Just past the corner: a neighbouring cell, a few dozen metres away.
    across = (c_lat + (v_lat - c_lat) * 1.1, c_lon + (v_lon - c_lon) * 1.1)
    new_cell = h3.latlng_to_cell(*across, RES)
    assert new_cell != old_cell

    fake_embedder.queue.append(BASE_VECTOR)
    animal_id = post_photo(player, CAT, *inside).json()["animal"]["id"]
    # Seen again across the border and recognised: it now lives in the new cell.
    fake_embedder.queue.append(vector_with_similarity(0.95))
    assert post_photo(player, CAT, *across).json()["animal"]["id"] == animal_id

    body = zones(player, c_lat, c_lon).json()
    assert [(z["cell"], z["cats"]) for z in body] == [(new_cell, 1)]


def test_zone_animals_lists_who_lives_there():
    player = new_user()
    cell = h3.latlng_to_cell(*fresh_spot(), RES)
    cat = post_photo(player, CAT, *point_in_cell(cell, 1, 0.5)).json()["animal"]
    dog = post_photo(player, DOG, *point_in_cell(cell, 5, 0.5)).json()["animal"]
    neighbour = h3.grid_ring(cell, 1)[0]
    post_photo(player, CAT, *h3.cell_to_latlng(neighbour))

    body = client.get(f"/map/zones/{cell}/animals", headers=new_user()).json()

    assert {a["id"] for a in body} == {cat["id"], dog["id"]}
    assert all(a["can_name"] is False for a in body)  # a stranger is looking


def test_unknown_or_wrong_resolution_zone_is_404():
    headers = new_user()
    coarse = h3.latlng_to_cell(10.7, 106.7, RES - 1)
    assert client.get("/map/zones/not-a-cell/animals", headers=headers).status_code == 404
    assert client.get(f"/map/zones/{coarse}/animals", headers=headers).status_code == 404


def test_radius_is_capped():
    player = new_user()
    lat, lon = fresh_spot()
    post_photo(player, CAT, lat + 0.09, lon)  # ~10 km away, beyond the cap

    assert zones(player, lat, lon, radius_m=50_000).json() == []

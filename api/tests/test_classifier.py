from pathlib import Path

import pytest

from app.classifier import get_classifier
from app.models import Species
from app.photos import load_image

FIXTURES = Path(__file__).parent / "fixtures"

CASES = [
    ("cat_1.jpg", Species.cat),
    ("cat_2.jpg", Species.cat),
    ("cat_3.jpg", Species.cat),
    ("dog_1.jpg", Species.dog),
    ("dog_2.jpg", Species.dog),
    ("dog_3.jpg", Species.dog),
    ("none_1.jpg", None),
    ("none_2.jpg", None),
    ("none_3.jpg", None),
    ("none_4.jpg", None),
]


@pytest.mark.parametrize("filename,expected", CASES)
def test_classifies_fixture(filename, expected):
    result = get_classifier().classify(load_image((FIXTURES / filename).read_bytes()))
    assert result.species == expected, result.scores

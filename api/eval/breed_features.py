"""Cache breed-CLIP features of the cat test photos, so detector variants compare in seconds.

Usage (inside the api container):  python -m eval.breed_features
Writes /data/breed_eval/features.pt: a list of (set, expected Wikidata id or "mixed", name,
unit-length feature of the cropped animal). Sets: "curated" (eval/breeds) and "commons".
"""
import sys

import torch

from app.breeds import _breed_zero_shot
from app.coats import animal_crop
from app.models import Species
from eval.breed_head_eval import photos

OUT = "/data/breed_eval/features.pt"


def main():
    rows = []
    for name_of_set, flag in (("curated", None), ("commons", "--commons")):
        sys.argv = [sys.argv[0]] + ([flag] if flag else [])
        for expected, name, image in photos():
            f = _breed_zero_shot(Species.cat).image_features(animal_crop(image, Species.cat))
            rows.append((name_of_set, expected, name, f[0]))
            print(name_of_set, name, flush=True)
    torch.save(rows, OUT)


if __name__ == "__main__":
    main()

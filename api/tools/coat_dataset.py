"""Build a coat test set from Wikimedia Commons coat categories (freely licensed photos).

Usage (inside the api container):
    python -m tools.coat_dataset [--per-coat 15]

Writes /data/coat_eval/<species>/<coat key>/NN.jpg plus a manifest.tsv with each photo's
source, license and author. Used by eval/coat_eval.py to choose prompts and the confidence
threshold of app/coats.py. Commons categories are only roughly right, so expect some noise.
"""
import argparse
from pathlib import Path

from tools import breed_dataset

# Coat key (app/coats.py) -> Commons categories. Cats use the "domestic short-haired"
# colour categories: they are non-pedigree cats sorted by coat, like the cats players meet.
CATEGORIES = {
    "dog": {
        "black": ["Black dogs"],
        "white": ["White dogs"],
        "brown": ["Brown dogs"],
        "tan": ["Yellow dogs", "Red dogs"],
        "cream": ["Cream dogs"],
        "grey": ["Gray dogs"],
        "black_and_tan": ["Black-and-tan dogs"],
        "bicolor": ["Black-and-white dogs", "Piebald dogs"],
        "tricolor": ["Tricolour dogs"],
        "brindle": ["Brindle dogs"],
        "merle": ["Merle dogs"],
        "spotted": ["Spotted dogs"],
    },
    "cat": {
        "tabby": ["Black tabby domestic short-haired cats"],
        "tabby_and_white": ["Black tabby and white domestic short-haired cats"],
        "orange": ["Red tabby domestic short-haired cats"],
        "black_and_white": ["Black and white domestic short-haired cats"],
        "black": ["Black domestic short-haired cats"],
        "grey": ["Blue domestic short-haired cats"],
        "white": ["White domestic short-haired cats"],
        "colorpoint": ["Colourpoint domestic short-haired cats"],
        "calico": ["Black tortoiseshell and white domestic short-haired cats"],
        "tortoiseshell": ["Black tortoiseshell domestic short-haired cats"],
    },
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-coat", type=int, default=15)
    args = parser.parse_args()

    breed_dataset.OUT = Path("/data/coat_eval")
    breed_dataset.OUT.mkdir(parents=True, exist_ok=True)
    skip = breed_dataset.eval_titles()
    with open(breed_dataset.OUT / "manifest.tsv", "a", encoding="utf-8") as manifest:
        for species, coats in CATEGORIES.items():
            for key, categories in coats.items():
                n = breed_dataset.collect(species, key, key, categories, args.per_coat, skip, manifest, fetch=60)
                print(f"{species} {key}: {n}", flush=True)


if __name__ == "__main__":
    main()

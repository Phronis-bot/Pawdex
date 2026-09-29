"""The production cat breed rule (app.breeds.decide_head_breed) vs zero-shot alone, on cached
features of the test photos (eval/breed_features.py) — seconds instead of minutes.

Usage (inside the api container):  python -m eval.breed_rules
"""
import torch

from app.breeds import FAMILIES, WIKIDATA, _breed_zero_shot, breed_scores, decide_breed, decide_head_breed, head_probs
from app.models import Species

CAT = Species.cat
KEY = {q: k for k, q in WIKIDATA[CAT].items()}


def main():
    rules = {
        "head (production)": lambda f: decide_head_breed(head_probs(f, CAT), breed_scores(None, CAT, f)[1], CAT),
        "zero-shot alone": lambda f: decide_breed(*breed_scores(None, CAT, f), CAT),
    }
    rows = torch.load("/data/breed_eval/features.pt", weights_only=True)
    for set_name in ("curated", "commons"):
        mine = [r for r in rows if r[0] == set_name]
        print(f"\n### {set_name}: {sum(e != 'mixed' for _, e, _, _ in mine)} purebred, "
              f"{sum(e == 'mixed' for _, e, _, _ in mine)} street")
        for label, rule in rules.items():
            right = {"confirmed": 0, "likely": 0}
            wrong = {"confirmed": 0, "likely": 0}
            street = []
            for _, expected, name, f in mine:
                claim = rule(f[None])
                if not claim:
                    continue
                key, certainty = claim
                if expected == "mixed":
                    street.append(f"{name}->{key}")
                    continue
                family = FAMILIES[CAT].get(key, [key]) if certainty.value == "likely" else [key]
                (right if KEY.get(expected) in family else wrong)[certainty.value] += 1
            print(f"  {label:18s} confirmed right/wrong {right['confirmed']}/{wrong['confirmed']}, "
                  f"'looks like' right/wrong {right['likely']}/{wrong['likely']}, "
                  f"street as breed {len(street)} {street[:3]}")


if __name__ == "__main__":
    main()

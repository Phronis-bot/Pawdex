"""The production cat breed rule (app.breeds.decide_head_breed) vs zero-shot alone, on cached
features of the test photos (eval/breed_features.py) — seconds instead of minutes.

Usage (inside the api container):  python -m eval.breed_rules
"""
import torch

from app.breeds import FAMILIES, Certainty, WIKIDATA, _breed_zero_shot, breed_scores, decide_breed, decide_head_breed, head_probs
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
            tally: dict[str, int] = {}
            for _, expected, name, f in mine:
                claim = rule(f[None])
                kind = "street" if expected == "mixed" else "pure"
                if not claim:
                    out = "unknown"
                elif claim[1] is Certainty.mixed:
                    out = "mixed"
                elif kind == "street":
                    out = claim[1].value
                else:
                    options = [claim[0], *claim[2:]] if claim[1] is not Certainty.likely else FAMILIES[CAT].get(claim[0], [claim[0]])
                    out = f"{claim[1].value} {'right' if KEY.get(expected) in options else 'wrong'}"
                tally[f"{kind}: {out}"] = tally.get(f"{kind}: {out}", 0) + 1
            print(f"  {label}")
            for k, n in sorted(tally.items()):
                print(f"      {k:28s} {n}")


if __name__ == "__main__":
    main()

"""Compare the trained breed head (tools/train_breeds.py) with CLIP zero-shot on cats.

Usage (inside the api container):
    python -m eval.breed_head_eval            # eval/breeds, same photos as eval/breed_eval.py
    python -m eval.breed_head_eval --commons  # /data/breed_eval (tools/breed_dataset.py --eval)

Neither set shares a photo with the training set. Both methods see the animal cropped out
of the photo, as the app does. Breeds are compared as Wikidata ids ("mixed" for mixed).
"""
import sys
from pathlib import Path

import torch

from app.breeds import WIKIDATA, _breed_clip, breed_scores
from app.models import Species
from app.photos import load_image
from app.segment import crop_to_animal, find_animal
from eval.breed_eval import load
from tools.train_breeds import class_of

HEAD = Path(__file__).parent.parent / "app" / "breed_heads" / "cat.pt"
COMMONS = Path("/data/breed_eval/cat")
THRESHOLDS = [0.5, 0.6, 0.7, 0.8, 0.9]


@torch.inference_mode()
def head_scores(head, image) -> tuple[str, float]:
    model, processor = _breed_clip()
    f = model.get_image_features(**processor(images=image, return_tensors="pt"))
    f = f / f.norm(dim=-1, keepdim=True)
    probs = (f[0] * 10 @ head["weight"].T + head["bias"]).softmax(-1)
    i = int(probs.argmax())
    return head["classes"][i], float(probs[i])


def photos():
    """(expected Wikidata id or "mixed", name, image)"""
    if "--commons" in sys.argv:
        for folder in sorted(p for p in COMMONS.iterdir() if p.is_dir()):
            for f in sorted(folder.glob("*.jpg")):
                yield class_of(folder.name), f"{folder.name}/{f.name}", load_image(f.read_bytes())
        return
    for species, expected, name, image in load():
        if species == Species.cat:
            yield (WIKIDATA[Species.cat][expected] if expected else "mixed"), name, image


def main():
    head = torch.load(HEAD)
    qid = WIKIDATA[Species.cat]
    rows = []  # expected, name, head id, head prob, zero-shot id, zero-shot prob, zero-shot mixed
    for expected, name, image in photos():
        region = find_animal(image, Species.cat)
        subject = crop_to_animal(image, region) if region else image
        got, p = head_scores(head, subject)
        ranked, mixed = breed_scores(subject, Species.cat)
        zs = qid[ranked[0][0]] if ranked[0][1] > mixed else "mixed"
        rows.append((expected, name, got, p, zs, ranked[0][1], mixed))
        print(f"{name:50s} expect={expected:10s} head={got} {p:.2f}   zero-shot={zs} {ranked[0][1]:.2f}", flush=True)

    rules = {"zero-shot": lambda r, t: r[4] if r[5] >= t else "mixed",
             "head": lambda r, t: r[2] if r[3] >= t else "mixed"}
    for gate in (0.3, 0.5):
        rules[f"head, unless zero-shot 'mixed' >= {gate}"] = (
            lambda r, t, gate=gate: r[2] if r[3] >= t and r[6] < gate else "mixed")

    pure = [r for r in rows if r[0] != "mixed"]
    street = [r for r in rows if r[0] == "mixed"]
    print(f"\n{len(pure)} purebred photos of {len({r[0] for r in pure})} breeds, {len(street)} street photos")
    for label, claim in rules.items():
        print(f"== {label}")
        for t in THRESHOLDS:
            correct = sum(claim(r, t) == r[0] for r in pure)
            wrong = sum(claim(r, t) not in ("mixed", r[0]) for r in pure)
            fp = sum(claim(r, t) != "mixed" for r in street)
            print(f"  {t:.1f}: correct {correct}/{len(pure)}, wrong breed {wrong}, "
                  f"street as breed {fp}/{len(street)}")
    per_breed(rows, rules)


def per_breed(rows, rules) -> None:
    """Correct photos per breed for the head at 0.7, unless zero-shot says 'mixed' >= 0.3."""
    claim = rules["head, unless zero-shot 'mixed' >= 0.3"]
    by = {}
    for r in rows:
        ok, n = by.get(r[0], (0, 0))
        by[r[0]] = (ok + (claim(r, 0.7) == r[0]), n + 1)
    print("\nper breed (head >= 0.7, zero-shot 'mixed' < 0.3):")
    for key, (ok, n) in sorted(by.items(), key=lambda kv: kv[1][0] / kv[1][1]):
        print(f"  {ok}/{n}  {key}")


if __name__ == "__main__":
    main()

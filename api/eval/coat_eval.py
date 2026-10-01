"""Choose the coat model and confidence threshold (app/coats.py) on the Commons coat test set.

Usage (inside the api container):  python -m eval.coat_eval
Photos come from tools/coat_dataset.py (/data/coat_eval). Compares CLIP base on the whole
photo, CLIP base on the cropped animal and CLIP large (the breed model) on the crop.
"""
from collections import Counter
from pathlib import Path

from app.breeds import _breed_clip
from app.classifier import ZeroShot, get_classifier
from app.coats import COATS, animal_crop
from app.models import Species
from app.photos import InvalidImage, load_image

DATA = Path("/data/coat_eval")
THRESHOLDS = [0.0, 0.3, 0.4, 0.5, 0.6, 0.7]


def main():
    base = get_classifier()
    large_model, large_processor = _breed_clip()
    for species in (Species.dog, Species.cat):
        keys = list(COATS[species])
        prompts = [COATS[species][k].prompt for k in keys]
        variants = {
            "base, whole photo": (ZeroShot(base.model, base.processor, prompts), False),
            "base, crop": (ZeroShot(base.model, base.processor, prompts), True),
            "large, crop": (ZeroShot(large_model, large_processor, prompts), True),
        }
        rows = {name: [] for name in variants}  # (expected, predicted, prob)
        for folder in sorted(p for p in (DATA / species.value).iterdir() if p.is_dir()):
            if folder.name not in keys:
                continue
            for f in sorted(folder.glob("*.jpg")):
                try:
                    image = load_image(f.read_bytes())
                except InvalidImage:
                    continue
                crop = animal_crop(image, species)
                for name, (zero_shot, use_crop) in variants.items():
                    probs = zero_shot.probs(crop if use_crop else image)
                    i = max(range(len(probs)), key=probs.__getitem__)
                    rows[name].append((folder.name, keys[i], probs[i]))

        print(f"\n##### {species.value}: {len(next(iter(rows.values())))} photos")
        for name, scored in rows.items():
            print(f"== {name}")
            for t in THRESHOLDS:
                shown = [r for r in scored if r[2] >= t]
                right = sum(e == p for e, p, _ in shown)
                print(f"  threshold {t:.1f}: shown {len(shown):3d}, right {right:3d}, wrong {len(shown) - right:3d}")
            mistakes = Counter(f"{e} -> {p}" for e, p, _ in scored if e != p)
            print("  most common mistakes:", ", ".join(f"{k} ({n})" for k, n in mistakes.most_common(8)))


if __name__ == "__main__":
    main()

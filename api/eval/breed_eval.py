"""Tune breed_min_confidence: recognise purebreds, but never label street animals.

Usage (inside the api container):  python -m eval.breed_eval

eval/breeds/<species>_<breed key>/*.jpg are purebreds, eval/breeds/<species>_mixed/*.jpg
are street animals (sources in eval/breeds/_sources.tsv). The famous non-pedigree cats
from eval/reid and the Hoi An street dog fixture count as mixed too.
"""
from pathlib import Path

from app.breeds import BREEDS, breed_scores
from app.models import Species
from app.photos import load_image

EVAL = Path(__file__).parent
THRESHOLDS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]


def load():
    """(species, expected breed key or None, file name, image)"""
    items = []
    for folder in sorted(p for p in (EVAL / "breeds").iterdir() if p.is_dir()):
        species_name, key = folder.name.split("_", 1)
        species = Species(species_name)
        expected = None if key == "mixed" else key
        assert expected is None or expected in BREEDS[species], expected
        for f in sorted(folder.glob("*.jpg")):
            items.append((species, expected, f"{folder.name}/{f.name}", f))
    for name in ("cat_larry", "cat_palmerston", "cat_gladstone"):
        for f in sorted((EVAL / "reid" / name).glob("*.jpg")):
            items.append((Species.cat, None, f"reid/{name}/{f.name}", f))
    items.append((Species.dog, None, "fixtures/dog_3.jpg", EVAL.parent / "tests" / "fixtures" / "dog_3.jpg"))
    return [(s, e, n, load_image(f.read_bytes())) for s, e, n, f in items]


def decide(ranked, mixed, threshold):
    key, prob = ranked[0]
    return key if prob >= threshold and prob > mixed else None


def main():
    scored = []
    for species, expected, name, image in load():
        ranked, mixed = breed_scores(image, species)
        scored.append((expected, name, ranked, mixed))
        top = ", ".join(f"{k} {p:.2f}" for k, p in ranked[:2])
        print(f"{name:42s} expect={expected or 'mixed':22s} mixed={mixed:.2f}  {top}")

    for species in ("cat", "dog"):
        mine = [s for s in scored if _species(s[1]) == species]
        pure = [s for s in mine if s[0] is not None]
        street = [s for s in mine if s[0] is None]
        print(f"\n== {species}: {len(pure)} purebred, {len(street)} street photos")
        print("threshold  correct  wrong  street labelled as a breed")
        for t in THRESHOLDS:
            correct = sum(decide(r, m, t) == e for e, _, r, m in pure)
            wrong = [f"{n}->{decide(r, m, t)}" for e, n, r, m in pure if decide(r, m, t) not in (None, e)]
            false_pos = [f"{n}->{decide(r, m, t)}" for e, n, r, m in street if decide(r, m, t) is not None]
            print(f"   {t:.1f}     {correct:2d}/{len(pure)}   {len(wrong)}  {len(false_pos)}/{len(street)}  {wrong + false_pos}")


def _species(name: str) -> str:
    return "cat" if "cat_" in name else "dog"


if __name__ == "__main__":
    main()

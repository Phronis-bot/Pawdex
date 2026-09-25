"""Compare embedders on re-identifying the same animal across photos.

Usage (inside the api container):  python -m eval.reid_eval

eval/reid/<species>_<individual>/*.jpg holds several photos of one animal each
(sources and licenses in eval/reid/_sources.tsv). For every embedder we print the
cosine similarity of same-animal pairs versus different-animal pairs of the same
species, and top-1 accuracy: for each photo, is its most similar other photo the
same animal?
"""
import itertools
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from app.embedder import EMBEDDERS
from app.photos import load_image

ROOT = Path(__file__).parent / "reid"


@dataclass
class Report:
    same: list[float] = field(default_factory=list)
    different: list[float] = field(default_factory=list)
    top1_correct: int = 0
    total: int = 0


def load_photos():
    photos = []
    for folder in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        species, animal = folder.name.split("_", 1)
        for f in sorted(folder.glob("*.jpg")):
            photos.append((species, animal, load_image(f.read_bytes())))
    return photos


def evaluate(embedder, photos) -> Report:
    vectors = [embedder.embed(image) for *_, image in photos]

    def sim(i, j):
        return sum(a * b for a, b in zip(vectors[i], vectors[j]))

    report = Report(total=len(photos))
    for i, j in itertools.combinations(range(len(photos)), 2):
        if photos[i][0] != photos[j][0]:
            continue  # matching never compares across species
        (report.same if photos[i][1] == photos[j][1] else report.different).append(sim(i, j))

    for i in range(len(photos)):
        others = [j for j in range(len(photos)) if j != i and photos[j][0] == photos[i][0]]
        best = max(others, key=lambda j: sim(i, j))
        report.top1_correct += photos[best][1] == photos[i][1]
    return report


def pct(values, q):
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def main():
    photos = load_photos()
    print(f"{len(photos)} photos of {len({(s, a) for s, a, _ in photos})} animals")
    for embedder_cls in EMBEDDERS.values():
        embedder = embedder_cls()
        r = evaluate(embedder, photos)
        print(f"\n== {embedder.name}")
        print(f"same animal  n={len(r.same):3d}  min={min(r.same):.3f}  p10={pct(r.same, .1):.3f}  median={statistics.median(r.same):.3f}")
        print(f"diff animal  n={len(r.different):3d}  median={statistics.median(r.different):.3f}  p90={pct(r.different, .9):.3f}  max={max(r.different):.3f}")
        print(f"top-1 accuracy: {r.top1_correct}/{r.total}")


if __name__ == "__main__":
    main()

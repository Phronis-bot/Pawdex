"""Train the breed classifier head on the Commons training set (see tools/breed_dataset.py).

Usage (inside the api container):
    python -m tools.train_breeds cat

Every photo is cropped to the animal (like the app does), embedded with the breed CLIP
model, and a linear classifier is trained on top, with "mixed" as one of the classes.
20% of each class is held out to report honest accuracy. The head is saved to
app/breed_heads/<species>.pt; class keys are Wikidata ids ("mixed" for mixed breed).
"""
import random
import sys
from collections import Counter
from pathlib import Path

import torch

from app.breeds import _breed_clip
from app.models import Species
from app.photos import InvalidImage, load_image
from app.segment import crop_to_animal, find_animal

DATA = Path("/data/breed_train")
HEADS = Path(__file__).parent.parent / "app" / "breed_heads"
MIN_PHOTOS = 12  # classes with fewer usable photos are left out
# Varieties that even owners tell apart by pedigree papers, not looks, are trained as one
# class (held-out errors were mostly Burmese <-> European Burmese, Persian <-> Traditional).
SAME_CLASS = {
    "Q2928528": "Q42573",  # European Burmese -> Burmese
    "Q2928526": "Q42573",  # American Burmese -> Burmese
    "Q10666939": "Q42610",  # Chinchilla Persian -> Persian
    "Q7832303": "Q42610",  # Traditional Persian -> Persian
    "Q42661": "Q9665",  # Javanese -> Balinese
}


# Breeds bred from local street cats that look exactly like them; their Commons categories
# are full of ordinary cats too. Trained as "mixed": we never claim them from a photo.
LOOKS_LIKE_STREET = {
    "Q20793",  # European Shorthair
    "Q7962",  # American Shorthair
    "Q7970",  # Arabian Mau
    "Q29280",  # Brazilian Shorthair
    "Q7957",  # Aegean
    "Q42539",  # Anatoli
}


def class_of(folder: str) -> str:
    # "mixed", the per-coat "mixed-..." folders and street-looking breeds.
    if folder.startswith("mixed") or folder in LOOKS_LIKE_STREET:
        return "mixed"
    return SAME_CLASS.get(folder, folder)


@torch.inference_mode()
def embed_folder(species: Species, folder: Path, cache: dict) -> list[torch.Tensor]:
    model, processor = _breed_clip()
    vectors = []
    for f in sorted(folder.glob("*.jpg")):
        key = str(f)
        if key not in cache:
            try:
                image = load_image(f.read_bytes())
            except InvalidImage:
                cache[key] = None
                continue
            region = find_animal(image, species)
            if region is None:  # drawings, stamps, wrong animal, tiny subject...
                cache[key] = None
                continue
            features = model.get_image_features(**processor(images=crop_to_animal(image, region), return_tensors="pt"))
            cache[key] = (features / features.norm(dim=-1, keepdim=True))[0]
        if cache[key] is not None:
            vectors.append(cache[key])
    return vectors


def main() -> None:
    species = Species(sys.argv[1])
    root = DATA / species.value
    cache_path = root / "embeddings.pt"
    cache = torch.load(cache_path) if cache_path.exists() else {}

    by_class: dict[str, list[torch.Tensor]] = {}
    for folder in sorted(p for p in root.iterdir() if p.is_dir()):
        by_class.setdefault(class_of(folder.name), []).extend(embed_folder(species, folder, cache))
        torch.save(cache, cache_path)

    classes, x, y = [], [], []
    for name, vectors in sorted(by_class.items()):
        if len(vectors) < MIN_PHOTOS:
            print(f"  skip {name}: {len(vectors)} usable photos")
            continue
        classes.append(name)
        x += vectors
        y += [len(classes) - 1] * len(vectors)
        print(f"{name}: {len(vectors)} photos", flush=True)

    x, y = torch.stack(x), torch.tensor(y)
    rng = random.Random(0)
    val = set()
    for c in range(len(classes)):
        idx = [i for i in range(len(y)) if y[i] == c]
        val.update(rng.sample(idx, max(2, len(idx) // 5)))
    train_idx = [i for i in range(len(y)) if i not in val]
    val_idx = sorted(val)

    head = train(x[train_idx], y[train_idx], len(classes))
    report(head, x[val_idx], y[val_idx], classes)

    # Final head uses all photos.
    head = train(x, y, len(classes))
    HEADS.mkdir(exist_ok=True)
    torch.save({"classes": classes, "weight": head.weight.data, "bias": head.bias.data}, HEADS / f"{species.value}.pt")
    print(f"saved {HEADS / (species.value + '.pt')} with {len(classes)} classes")


def train(x: torch.Tensor, y: torch.Tensor, n_classes: int) -> torch.nn.Linear:
    torch.manual_seed(0)
    head = torch.nn.Linear(x.shape[1], n_classes)
    # Balance classes: "mixed" has many more photos than rare breeds.
    counts = Counter(y.tolist())
    weights = torch.tensor([1.0 / counts[c] for c in range(n_classes)]) * n_classes
    opt = torch.optim.AdamW(head.parameters(), lr=1e-2, weight_decay=1e-3)
    loss_fn = torch.nn.CrossEntropyLoss(weight=weights)
    for _ in range(400):
        opt.zero_grad()
        # CLIP embeddings are unit length; scale so logits aren't squashed.
        loss = loss_fn(head(x * 10), y)
        loss.backward()
        opt.step()
    return head


@torch.inference_mode()
def report(head, x, y, classes) -> None:
    probs = head(x * 10).softmax(dim=-1)
    top = probs.argmax(dim=-1)
    print(f"\nheld-out accuracy: {(top == y).float().mean():.1%} on {len(y)} photos")
    mixed = classes.index("mixed") if "mixed" in classes else -1
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        conf = probs.max(dim=-1).values
        claimed = (top != mixed) & (conf >= t)
        right = claimed & (top == y)
        street_as_breed = claimed & (y == mixed)
        print(f"  threshold {t}: breed claimed {int(claimed.sum())}, correct {int(right.sum())}, "
              f"wrong {int((claimed & ~(top == y)).sum())}, of them street animals {int(street_as_breed.sum())}")


if __name__ == "__main__":
    main()

"""Cache CLIP features of the coat test photos (tools/coat_dataset.py), so prompt and
threshold variants for app/coats.py compare in seconds.

Usage (inside the api container):  python -m eval.coat_features
Writes /data/coat_eval/features.pt: list of (species, expected coat, file, {model: feature}).
"""
from pathlib import Path

import torch

from app.breeds import _breed_clip
from app.classifier import get_classifier
from app.coats import animal_crop
from app.models import Species
from app.photos import InvalidImage, load_image

DATA = Path("/data/coat_eval")


@torch.inference_mode()
def features(model, processor, image) -> torch.Tensor:
    f = model.get_image_features(**processor(images=image, return_tensors="pt"))
    return (f / f.norm(dim=-1, keepdim=True))[0]


def main():
    base = get_classifier()
    large = _breed_clip()
    rows = []
    for species in (Species.dog, Species.cat):
        for folder in sorted(p for p in (DATA / species.value).iterdir() if p.is_dir()):
            for f in sorted(folder.glob("*.jpg")):
                try:
                    crop = animal_crop(load_image(f.read_bytes()), species)
                except InvalidImage:
                    continue
                rows.append((species.value, folder.name, f.name, {
                    "base": features(base.model, base.processor, crop),
                    "large": features(*large, crop),
                }))
    torch.save(rows, DATA / "features.pt")
    print(len(rows), "photos")


if __name__ == "__main__":
    main()

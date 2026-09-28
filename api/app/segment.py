"""Find the animal in a photo: its box (for re-identification) and outline (for blurring).

Uses torchvision's Mask R-CNN trained on COCO, which knows "cat" and "dog".
"""
from dataclasses import dataclass
from functools import lru_cache

import torch
from PIL import Image, ImageFilter
from torchvision.models.detection import MaskRCNN_ResNet50_FPN_V2_Weights, maskrcnn_resnet50_fpn_v2
from torchvision.transforms.functional import to_tensor

from app.config import settings
from app.models import Species

# COCO category ids as used by torchvision detection models.
COCO_LABELS = {Species.cat: 17, Species.dog: 18}


@dataclass(frozen=True)
class AnimalRegion:
    box: tuple[int, int, int, int]  # left, top, right, bottom in image pixels
    mask: Image.Image  # "L" mode, same size as the image, 255 = animal


@lru_cache
def _model():
    return maskrcnn_resnet50_fpn_v2(weights=MaskRCNN_ResNet50_FPN_V2_Weights.DEFAULT).eval()


@torch.inference_mode()
def find_animal(image: Image.Image, species: Species) -> AnimalRegion | None:
    """The most confident cat or dog of the given species, or None if none is found."""
    # Detection is slow on big images; run it on a smaller copy and scale back up.
    small = image.copy()
    small.thumbnail((settings.segment_max_side, settings.segment_max_side))
    out = _model()([to_tensor(small)])[0]

    wanted = COCO_LABELS[species]
    candidates = [
        i for i, (label, score) in enumerate(zip(out["labels"].tolist(), out["scores"].tolist()))
        if label == wanted and score >= settings.segment_min_score
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda i: out["scores"][i])

    scale_x, scale_y = image.width / small.width, image.height / small.height
    left, top, right, bottom = out["boxes"][best].tolist()
    box = (
        int(left * scale_x), int(top * scale_y),
        int(round(right * scale_x)), int(round(bottom * scale_y)),
    )
    mask = Image.fromarray((out["masks"][best, 0] > 0.5).numpy().astype("uint8") * 255, mode="L")
    return AnimalRegion(box=box, mask=mask.resize(image.size, Image.Resampling.BILINEAR))


def crop_to_animal(image: Image.Image, region: AnimalRegion, margin: float = 0.1) -> Image.Image:
    """The animal's box plus a small margin, for re-identification."""
    left, top, right, bottom = region.box
    dx, dy = int((right - left) * margin), int((bottom - top) * margin)
    return image.crop((
        max(0, left - dx), max(0, top - dy),
        min(image.width, right + dx), min(image.height, bottom + dy),
    ))


def prepare_photo(image: Image.Image, species: Species) -> tuple[Image.Image, Image.Image]:
    """(what to re-identify, what to store).

    Re-identification looks at the animal only, so the same street doesn't make two
    different cats look alike. The stored photo has its background blurred. If the
    animal can't be found, both are the whole photo.
    """
    region = find_animal(image, species)
    if region is None:
        return image, image
    stored = blur_background(image, region) if settings.blur_backgrounds else image
    return crop_to_animal(image, region), stored


def reid_model_name(embedder) -> str:
    """Embeddings of cropped photos aren't comparable with whole-photo ones: tag them."""
    return f"{embedder.name}-crop"


def blur_background(image: Image.Image, region: AnimalRegion) -> Image.Image:
    """Everything except the animal is blurred, so the photo gives away less about the place.

    Both the mask and the blur are computed on small copies and scaled back up: a blurred
    background looks the same either way, and it's many times faster on big photos.
    """
    # Grow the outline a little and soften its edge so fur isn't cut off harshly.
    small = region.mask.copy()
    small.thumbnail((MASK_WORK_SIDE, MASK_WORK_SIDE))
    grow = max(1, round(max(small.size) * 0.01))
    keep = (
        small.filter(ImageFilter.MaxFilter(2 * grow + 1))
        .filter(ImageFilter.GaussianBlur(grow))
        .resize(image.size, Image.Resampling.BILINEAR)
    )

    shrink = 4
    low = image.resize((max(1, image.width // shrink), max(1, image.height // shrink)), Image.Resampling.BILINEAR)
    radius = settings.blur_radius_fraction * max(low.size)
    blurred = low.filter(ImageFilter.GaussianBlur(radius)).resize(image.size, Image.Resampling.BILINEAR)
    return Image.composite(image, blurred, keep)


# Resolution at which the animal's outline is grown and feathered for blurring.
MASK_WORK_SIDE = 320

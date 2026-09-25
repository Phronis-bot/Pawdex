from functools import lru_cache
from typing import Protocol

import torch
from PIL import Image
from transformers import AutoImageProcessor, AutoModel

from app.classifier import get_classifier
from app.config import settings


class Embedder(Protocol):
    """Turns a photo of an animal into a unit-length vector; similar animals end up close."""

    name: str

    def embed(self, image: Image.Image) -> list[float]: ...


def _normalize(v: torch.Tensor) -> list[float]:
    return torch.nn.functional.normalize(v, dim=-1)[0].tolist()


class ClipEmbedder:
    name = "clip-vit-b32"

    def __init__(self):
        # Reuse the classifier's weights instead of loading CLIP twice.
        classifier = get_classifier()
        self.model, self.processor = classifier.model, classifier.processor

    @torch.inference_mode()
    def embed(self, image: Image.Image) -> list[float]:
        inputs = self.processor(images=image, return_tensors="pt")
        return _normalize(self.model.get_image_features(**inputs))


class DinoEmbedder:
    name = "dinov2-base"

    def __init__(self, model_name: str = "facebook/dinov2-base"):
        self.model = AutoModel.from_pretrained(model_name).eval()
        self.processor = AutoImageProcessor.from_pretrained(model_name)

    @torch.inference_mode()
    def embed(self, image: Image.Image) -> list[float]:
        inputs = self.processor(images=image, return_tensors="pt")
        return _normalize(self.model(**inputs).pooler_output)


EMBEDDERS = {"clip": ClipEmbedder, "dinov2": DinoEmbedder}


@lru_cache
def get_embedder() -> Embedder:
    return EMBEDDERS[settings.embedding_model]()

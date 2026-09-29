from dataclasses import dataclass
from functools import lru_cache

import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from app.config import settings
from app.models import Species

# Zero-shot prompts grouped by outcome. Each group's score is the sum of its prompts'
# probabilities, so "none" needs enough variety to catch typical non-animal shots.
PROMPTS: dict[str, list[str]] = {
    "cat": ["a photo of a cat", "a photo of a kitten"],
    "dog": ["a photo of a dog", "a photo of a puppy"],
    "none": [
        "a photo of a street",
        "a photo of a building",
        "a photo of a person",
        "a photo of food",
        "a photo of a car or a motorbike",
        "a photo of a plant",
        "a photo of a bird",
        "a photo of an object",
        "a blurry photo",
    ],
}


@dataclass(frozen=True)
class Classification:
    species: Species | None  # None means no cat or dog in the photo
    confidence: float
    scores: dict[str, float]


class ZeroShot:
    """CLIP zero-shot over a fixed list of prompts.

    The prompts never change, so their embeddings are computed once here; each photo
    then only needs the image encoder. Same maths as CLIPModel's forward pass.
    """

    @torch.inference_mode()
    def __init__(self, model: CLIPModel, processor: CLIPProcessor, prompts: list[str]):
        self.model, self.processor = model, processor
        text = model.get_text_features(**processor(text=prompts, return_tensors="pt", padding=True))
        self.text = text / text.norm(dim=-1, keepdim=True)
        self.scale = model.logit_scale.exp()

    @torch.inference_mode()
    def image_features(self, image: Image.Image) -> torch.Tensor:
        """Unit-length image embedding, shape (1, dim); reusable by other heads on the same model."""
        pixels = self.processor(images=image, return_tensors="pt")
        features = self.model.get_image_features(**pixels)
        return features / features.norm(dim=-1, keepdim=True)

    @torch.inference_mode()
    def probs(self, image: Image.Image, features: torch.Tensor | None = None) -> list[float]:
        if features is None:
            features = self.image_features(image)
        return (self.scale * features @ self.text.T).softmax(dim=-1)[0].tolist()


class ClipClassifier:
    def __init__(self, model_name: str, min_confidence: float):
        self.model = CLIPModel.from_pretrained(model_name).eval()
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.min_confidence = min_confidence
        self.groups = [group for group, prompts in PROMPTS.items() for _ in prompts]
        self.zero_shot = ZeroShot(self.model, self.processor, [p for ps in PROMPTS.values() for p in ps])

    def classify(self, image: Image.Image) -> Classification:
        probs = self.zero_shot.probs(image)

        scores = dict.fromkeys(PROMPTS, 0.0)
        for group, p in zip(self.groups, probs):
            scores[group] += p

        best = max(scores, key=scores.get)
        if best == "none" or scores[best] < self.min_confidence:
            return Classification(species=None, confidence=scores[best], scores=scores)
        return Classification(species=Species(best), confidence=scores[best], scores=scores)


@lru_cache
def get_classifier() -> ClipClassifier:
    # Loaded once per process; the first call downloads the weights into HF_HOME.
    return ClipClassifier(settings.clip_model, settings.min_animal_confidence)

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


class ClipClassifier:
    def __init__(self, model_name: str, min_confidence: float):
        self.model = CLIPModel.from_pretrained(model_name).eval()
        self.processor = CLIPProcessor.from_pretrained(model_name)
        self.min_confidence = min_confidence
        self.groups = [group for group, prompts in PROMPTS.items() for _ in prompts]
        self.prompts = [p for prompts in PROMPTS.values() for p in prompts]

    @torch.inference_mode()
    def classify(self, image: Image.Image) -> Classification:
        inputs = self.processor(text=self.prompts, images=image, return_tensors="pt", padding=True)
        probs = self.model(**inputs).logits_per_image.softmax(dim=-1)[0].tolist()

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

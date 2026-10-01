"""Compare coat prompt sets and models on cached features (eval/coat_features.py).

Usage (inside the api container):  python -m eval.coat_prompts
"""
from collections import Counter

import torch

from app.breeds import _breed_clip
from app.classifier import get_classifier
from app.coats import COATS
from app.models import Species

# Several descriptions per coat; their text embeddings are averaged ("prompt ensemble").
ENSEMBLE = {
    "dog": {
        "black": ["a photo of a solid black dog", "a completely black dog with no markings"],
        "white": ["a photo of a white dog", "a dog with an all-white coat"],
        "brown": ["a photo of a solid brown dog", "a chocolate brown dog", "a liver-coloured dog"],
        "tan": ["a photo of a yellow dog", "a tan dog", "a reddish ginger dog", "a golden-coloured street dog"],
        "cream": ["a photo of a pale cream coloured dog", "a light beige dog"],
        "grey": ["a photo of a solid grey dog", "a blue-grey dog"],
        "black_and_tan": ["a photo of a black and tan dog",
                          "a black dog with tan eyebrows, tan cheeks and tan legs",
                          "a dog coloured like a Rottweiler or a Dobermann"],
        "bicolor": ["a photo of a black and white dog", "a brown and white dog", "a dog with large white patches"],
        "tricolor": ["a photo of a tricolor dog with black, tan and white",
                     "a dog coloured like a Beagle or a Bernese Mountain Dog"],
        "brindle": ["a photo of a brindle dog with tiger stripes", "a dog with dark stripes over a brown coat"],
        "merle": ["a photo of a merle dog with a marbled coat", "a blue merle dog like an Australian Shepherd",
                  "a dog with irregular black patches on a grey coat"],
        "spotted": ["a photo of a dalmatian-like white dog with black spots", "a white dog covered in small spots"],
    },
    "cat": {
        "tabby": ["a photo of a striped tabby cat", "a brown or grey tabby cat with stripes all over"],
        "tabby_and_white": ["a photo of a tabby and white cat with a white chest and paws",
                            "a striped cat with white legs and a white belly"],
        "orange": ["a photo of an orange ginger cat", "a ginger tabby cat"],
        "black_and_white": ["a photo of a black and white tuxedo cat", "a black cat with a white chest and white paws"],
        "black": ["a photo of a solid black cat", "an all-black cat with no white"],
        "grey": ["a photo of a solid grey cat", "a blue-grey cat like a Russian Blue"],
        "chocolate": ["a photo of a solid chocolate brown cat"],
        "white": ["a photo of a solid white cat", "an all-white cat"],
        "colorpoint": ["a photo of a siamese colorpoint cat", "a pale cat with a dark face, ears, paws and tail"],
        "calico": ["a photo of a calico cat with orange, black and white patches",
                   "a white cat with orange and black patches"],
        "tortoiseshell": ["a photo of a tortoiseshell cat with mottled black and orange fur",
                          "a black and orange brindled cat"],
    },
}


@torch.inference_mode()
def text_matrix(model, processor, prompt_lists):
    rows = []
    for prompts in prompt_lists:
        t = model.get_text_features(**processor(text=prompts, return_tensors="pt", padding=True))
        t = (t / t.norm(dim=-1, keepdim=True)).mean(0)
        rows.append(t / t.norm())
    return torch.stack(rows), model.logit_scale.exp()


def main():
    rows = torch.load("/data/coat_eval/features.pt", weights_only=True)
    models = {"base": (get_classifier().model, get_classifier().processor), "large": _breed_clip()}
    for species in ("dog", "cat"):
        keys = list(COATS[Species(species)])
        mine = [r for r in rows if r[0] == species]
        print(f"\n##### {species}: {len(mine)} photos")
        sets = {"single": [[COATS[Species(species)][k].prompt] for k in keys],
                "ensemble": [ENSEMBLE[species][k] for k in keys]}
        probs = {}
        for m, (model, processor) in models.items():
            for name, prompts in sets.items():
                text, scale = text_matrix(model, processor, prompts)
                feats = torch.stack([r[3][m] for r in mine])
                probs[f"{m} {name}"] = (scale * feats @ text.T).softmax(-1)
        probs["base+large ensemble"] = (probs["base ensemble"] + probs["large ensemble"]) / 2
        for label, p in probs.items():
            conf, idx = p.max(-1)
            print(f"== {label}")
            for t in (0.0, 0.5, 0.6, 0.7, 0.8, 0.9):
                shown = [(r[1], keys[i]) for r, c, i in zip(mine, conf.tolist(), idx.tolist()) if c >= t]
                right = sum(e == g for e, g in shown)
                print(f"  {t:.1f}: shown {len(shown):3d}, right {right:3d}, wrong {len(shown) - right:3d}")
            mistakes = Counter(f"{r[1]}->{keys[i]}" for r, i in zip(mine, idx.tolist()) if r[1] != keys[i])
            print("  mistakes:", ", ".join(f"{k} ({n})" for k, n in mistakes.most_common(7)))
            if species == "dog":
                bt = Counter(keys[i] for r, i in zip(mine, idx.tolist()) if r[1] == "black_and_tan")
                print("  black_and_tan photos ->", dict(bt))


if __name__ == "__main__":
    main()

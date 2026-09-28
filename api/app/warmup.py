"""Download and load every model (and prompt embedding) once, so no player waits for it.

Runs in the background at API startup when PAWDEX_PRELOAD_MODELS is set, and at deploy
time (python -m app.warmup) to download weights before the new API process needs them.
"""
from app.breeds import _breed_zero_shot
from app.classifier import get_classifier
from app.coats import _coat_zero_shot
from app.embedder import get_embedder
from app.models import Species
from app.segment import _model as segmenter


def main() -> None:
    steps = [
        ("species classifier", get_classifier),
        ("re-identification", get_embedder),
        ("animal finder", segmenter),
    ]
    for species in Species:
        steps.append((f"{species.value} coats", lambda s=species: _coat_zero_shot(s)))
        steps.append((f"{species.value} breeds", lambda s=species: _breed_zero_shot(s)))
    for name, load in steps:
        print(f"loading {name}...", flush=True)
        load()
    print("all models ready", flush=True)


if __name__ == "__main__":
    main()

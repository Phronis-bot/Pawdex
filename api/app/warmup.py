"""Download and load every model once, so the first real upload isn't slow.

Usage (inside the api container):  python -m app.warmup
"""
from app.breeds import _breed_clip
from app.classifier import get_classifier
from app.embedder import get_embedder
from app.segment import _model as segmenter


def main() -> None:
    for name, load in [
        ("species/coat classifier", get_classifier),
        ("re-identification", get_embedder),
        ("breeds", _breed_clip),
        ("animal finder", segmenter),
    ]:
        print(f"loading {name}...", flush=True)
        load()
    print("all models ready")


if __name__ == "__main__":
    main()

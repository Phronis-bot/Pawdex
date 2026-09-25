"""The real re-identification model on photos of five well-known animals (see eval/reid)."""
from app.embedder import DinoEmbedder
from eval.reid_eval import evaluate, load_photos


def test_dinov2_recognises_the_same_animal():
    report = evaluate(DinoEmbedder(), load_photos())

    assert report.top1_correct == report.total
    # Thresholds in config.py rely on this gap.
    assert max(report.different) < 0.70

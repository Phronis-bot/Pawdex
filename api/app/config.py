from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PAWDEX_")

    database_url: str = "postgresql+psycopg://pawdex:pawdex@localhost:5432/pawdex"
    # Comma-separated list of allowed origins. "*" is fine for local dev only.
    cors_origins: str = "*"

    # Photo storage (local disk in dev).
    storage_dir: str = "/data/photos"
    max_upload_bytes: int = 15 * 1024 * 1024
    # Stored photos are re-encoded and downscaled so the longest side is at most this.
    photo_max_side: int = 1600

    # Species classifier (CLIP zero-shot).
    clip_model: str = "openai/clip-vit-base-patch32"
    # Minimum probability of the winning cat/dog group to accept the photo as an animal.
    min_animal_confidence: float = 0.5

    # Re-identification of individual animals. See eval/reid_eval.py for how the
    # model and thresholds were chosen.
    embedding_model: str = "dinov2"  # "clip" or "dinov2"
    # A new photo is only compared with animals of the same species seen within this radius.
    match_radius_m: float = 300
    # Cosine similarity at or above which we say "It's Mo!" without asking.
    # On the eval set no two different animals scored above 0.67.
    match_confident: float = 0.70
    # Between this and match_confident we ask the player; below it the animal is new.
    match_uncertain: float = 0.45
    match_max_candidates: int = 3

    # Map. Animals are shown only as H3 hexagon cells, never as points (rule 3: pets
    # get stolen). Resolution 9 hexagons are ~350 m across.
    map_cell_resolution: int = 9
    map_max_radius_m: float = 5000


settings = Settings()

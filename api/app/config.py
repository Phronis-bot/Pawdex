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

    # Public base URL of this API (links in the Telegram bot, the Mini App at /play/).
    public_url: str = "http://localhost:8000"
    # Telegram bot for the Mini App; empty disables Telegram sign-in and the bot.
    telegram_bot_token: str = ""
    # Random string Telegram echoes on every webhook call, so nobody else can post to it.
    telegram_webhook_secret: str = ""

    # Load every model when the API starts (production), instead of on the first photo.
    preload_models: bool = False

    # Abuse protection.
    uploads_per_user_per_hour: int = 30
    uploads_per_ip_per_hour: int = 100
    # A photo is hidden from other players once this many different players report it.
    reports_to_hide: int = 3

    # Finding the animal in the photo (app/segment.py).
    segment_max_side: int = 640
    # Short side the detector works at (see app/segment.py).
    segment_model_side: int = 400
    segment_min_score: float = 0.5
    # Stored photos get everything but the animal blurred (radius as a fraction of the
    # longest side), so shop signs and house numbers don't reveal where it lives.
    blur_backgrounds: bool = True
    blur_radius_fraction: float = 0.02

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

    # Breeds use a larger CLIP (~1.7 GB): the base one confused street cats with breeds.
    breed_clip_model: str = "openai/clip-vit-large-patch14"
    # A breed is shown only if CLIP gives it at least this probability and it beats
    # "mixed breed". Tuned per species with eval/breed_eval.py: a false breed on a street
    # animal is worse than a missed one.
    # Cats need 0.8: below it, non-pedigree British street cats get labelled Scottish Fold.
    breed_min_confidence: dict[str, float] = {"cat": 0.8, "dog": 0.6}
    # Between this and breed_min_confidence the card says "Looks like a Siamese" instead of
    # claiming the breed (or wrongly calling a likely Siamese "mixed").
    # On the eval set, dogs at 0.4 put no street dog in a breed; cats need 0.6 (at 0.5 a
    # black street cat "looked like" an Exotic Shorthair).
    breed_likely_confidence: dict[str, float] = {"cat": 0.6, "dog": 0.4}

    # Map. Animals are shown only as H3 hexagon cells, never as points (rule 3: pets
    # get stolen). Resolution 9 hexagons are ~350 m across.
    map_cell_resolution: int = 9
    map_max_radius_m: float = 5000


settings = Settings()

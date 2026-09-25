import io

from PIL import Image, ImageOps, UnidentifiedImageError


class InvalidImage(ValueError):
    pass


def load_image(data: bytes) -> Image.Image:
    """Decode an upload into an upright RGB image, or raise InvalidImage."""
    try:
        image = Image.open(io.BytesIO(data))
        image.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise InvalidImage("Not a supported image") from exc
    # Apply the EXIF orientation before the EXIF block is thrown away.
    image = ImageOps.exif_transpose(image)
    return image.convert("RGB")


def encode_for_storage(image: Image.Image, max_side: int) -> bytes:
    """Downscale and re-encode as JPEG.

    Re-encoding drops all EXIF metadata, including GPS tags: the exact location
    of an animal must never leak through a served photo.
    """
    image = image.copy()
    image.thumbnail((max_side, max_side))
    out = io.BytesIO()
    image.save(out, format="JPEG", quality=85)
    return out.getvalue()

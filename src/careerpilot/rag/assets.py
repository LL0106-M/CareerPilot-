import hashlib
from collections.abc import Mapping

from careerpilot.rag.models import ImageAsset, SourceDocument


def build_image_assets(document: SourceDocument) -> tuple[ImageAsset, ...]:
    """Register complete images without turning them into text or vector evidence."""
    raw_images = document.metadata.get("images")
    if not isinstance(raw_images, list):
        return ()
    assets: list[ImageAsset] = []
    for ordinal, raw in enumerate(raw_images):
        if not isinstance(raw, Mapping):
            continue
        object_uri = str(raw.get("object_uri") or "").strip()
        if not object_uri:
            continue
        page_number = _positive_int(raw.get("page_number"), default=1)
        identity = str(raw.get("image_id") or "").strip() or _image_id(
            document.id, page_number, ordinal, object_uri
        )
        assets.append(
            ImageAsset(
                id=identity,
                document_id=document.id,
                page_number=page_number,
                object_uri=object_uri,
                image_type=str(raw.get("image_type") or "image"),
                bbox=_bbox(raw.get("bbox")),
                caption=_optional(raw.get("caption")),
                metadata={
                    str(key): value
                    for key, value in raw.items()
                    if key
                    not in {
                        "image_id",
                        "page_number",
                        "object_uri",
                        "image_type",
                        "bbox",
                        "caption",
                    }
                },
                owner_user_id=document.owner_user_id,
            )
        )
    return tuple(assets)


def _image_id(document_id: str, page_number: int, ordinal: int, object_uri: str) -> str:
    value = f"{document_id}:{page_number}:{ordinal}:{object_uri}"
    return f"image-{hashlib.sha256(value.encode()).hexdigest()[:24]}"


def _positive_int(value: object, *, default: int) -> int:
    try:
        parsed = int(str(value))
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _bbox(value: object) -> tuple[float, float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        return None
    try:
        return tuple(float(item) for item in value)  # type: ignore[return-value]
    except (TypeError, ValueError):
        return None


def _optional(value: object) -> str | None:
    normalized = str(value).strip() if value not in (None, "") else ""
    return normalized or None

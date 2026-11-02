"""Card artwork: owner-supplied pig poses served from /media for Flex images."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final

MEDIA_DIR = Path(__file__).resolve().parent / "media"
POSES: Final = ("record", "edit", "delete", "restore")
MEDIA_NAME = re.compile(r"pig-(record|edit|delete|restore)\.[0-9a-f]{8}\.png")
# A pose without its own file borrows another one.
_FALLBACK: Final = {"restore": "record"}


def _file_for(pose: str) -> str | None:
    if not MEDIA_DIR.is_dir():
        return None
    names = sorted(
        path.name for path in MEDIA_DIR.glob(f"pig-{pose}.*.png") if MEDIA_NAME.fullmatch(path.name)
    )
    return names[0] if names else None


def media_url(pose: str, base_url: str | None) -> str | None:
    """Absolute HTTPS URL for a pose, or None when artwork or base URL is missing."""

    if not base_url or pose not in POSES:
        return None
    name = _file_for(pose) or (_file_for(_FALLBACK[pose]) if pose in _FALLBACK else None)
    return f"{base_url.rstrip('/')}/media/{name}" if name else None

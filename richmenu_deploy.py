"""Deploy the two-page rich menu to the LINE Messaging API.

Usage: python richmenu_deploy.py [--dry-run]
Needs LINE_CHANNEL_ACCESS_TOKEN unless --dry-run. Order keeps a default menu live
throughout: create new menus, repoint aliases, set default, then delete old menus.
"""

from __future__ import annotations

import argparse
import json
import os
import struct
import sys
from pathlib import Path

import httpx

from richmenu_config import ALIASES, CANVAS, IMAGE_PATHS, NAME_PREFIX, build_richmenu

API = "https://api.line.me"
DATA_API = "https://api-data.line.me"
MAX_IMAGE_BYTES = 1_000_000
# JPEG start-of-frame markers that carry the image size.
_SOF_MARKERS = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}


class DeployError(Exception):
    pass


def image_info(data: bytes) -> tuple[str, int, int]:
    """Return (content type, width, height) from the file signature and header."""
    if data.startswith(b"\x89PNG\r\n\x1a\n") and data[12:16] == b"IHDR" and len(data) >= 24:
        width, height = struct.unpack(">II", data[16:24])
        return "image/png", width, height
    if data.startswith(b"\xff\xd8"):
        offset = 2
        while offset + 4 <= len(data):
            if data[offset] != 0xFF:
                break
            marker = data[offset + 1]
            (length,) = struct.unpack(">H", data[offset + 2 : offset + 4])
            if marker in _SOF_MARKERS and offset + 9 <= len(data):
                height, width = struct.unpack(">HH", data[offset + 5 : offset + 9])
                return "image/jpeg", width, height
            offset += 2 + length
    raise DeployError("not a readable JPEG or PNG image")


def load_images(paths: dict[str, Path] = IMAGE_PATHS) -> dict[str, tuple[bytes, str]]:
    width, height = CANVAS
    images = {}
    for page, path in paths.items():
        if not path.is_file():
            raise DeployError(f"{page}: image missing at {path}")
        data = path.read_bytes()
        if len(data) > MAX_IMAGE_BYTES:
            raise DeployError(f"{page}: {len(data)} bytes exceeds {MAX_IMAGE_BYTES} bytes")
        try:
            content_type, w, h = image_info(data)
        except DeployError as error:
            raise DeployError(f"{page}: {error}") from None
        if (w, h) != (width, height):
            raise DeployError(f"{page}: image is {w}x{h}, expected {width}x{height}")
        images[page] = (data, content_type)
    return images


def _call(client: httpx.Client, method: str, url: str, **kwargs) -> dict:
    response = client.request(method, url, **kwargs)
    if response.is_success:
        return response.json() if response.content else {}
    try:
        message = response.json().get("message", "")
    except ValueError:
        message = response.text[:200]
    path = httpx.URL(url).path
    raise DeployError(f"{method} {path} -> {response.status_code}: {message}")


def deploy(client: httpx.Client, images: dict[str, tuple[bytes, str]]) -> dict[str, str]:
    """Publish both pages and return page -> new rich menu ID."""
    created: dict[str, str] = {}
    previous: dict[str, str] = {}  # alias -> menu ID before this run
    repointed: list[str] = []
    try:
        for page in ALIASES:
            menu = build_richmenu(page)
            _call(client, "POST", f"{API}/v2/bot/richmenu/validate", json=menu)
            created[page] = _call(client, "POST", f"{API}/v2/bot/richmenu", json=menu)["richMenuId"]
            data, content_type = images[page]
            _call(client, "POST", f"{DATA_API}/v2/bot/richmenu/{created[page]}/content",
                  content=data, headers={"Content-Type": content_type})
        for alias in _call(client, "GET", f"{API}/v2/bot/richmenu/alias/list")["aliases"]:
            previous[alias["richMenuAliasId"]] = alias["richMenuId"]
        for page, alias in ALIASES.items():
            if alias in previous:
                _call(client, "POST", f"{API}/v2/bot/richmenu/alias/{alias}", json={"richMenuId": created[page]})
            else:
                _call(client, "POST", f"{API}/v2/bot/richmenu/alias",
                      json={"richMenuAliasId": alias, "richMenuId": created[page]})
            repointed.append(alias)
    except DeployError:
        # Old menus are still live: point aliases back, then drop only what this run created.
        for alias in repointed:
            try:
                if alias in previous:
                    _call(client, "POST", f"{API}/v2/bot/richmenu/alias/{alias}", json={"richMenuId": previous[alias]})
                else:
                    _call(client, "DELETE", f"{API}/v2/bot/richmenu/alias/{alias}")
            except DeployError:
                pass
        for menu_id in created.values():
            try:
                _call(client, "DELETE", f"{API}/v2/bot/richmenu/{menu_id}")
            except DeployError:
                pass
        raise

    _call(client, "POST", f"{API}/v2/bot/user/all/richmenu/{created['page1']}")
    new_ids = set(created.values())
    for menu in _call(client, "GET", f"{API}/v2/bot/richmenu/list")["richmenus"]:
        if menu["name"].startswith(NAME_PREFIX) and menu["richMenuId"] not in new_ids:
            _call(client, "DELETE", f"{API}/v2/bot/richmenu/{menu['richMenuId']}")
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deploy the MooTun rich menu.")
    parser.add_argument("--dry-run", action="store_true", help="validate images and print the menus only")
    args = parser.parse_args(argv)
    try:
        images = load_images()
        if args.dry_run:
            print(json.dumps({page: build_richmenu(page) for page in ALIASES}, ensure_ascii=False, indent=2))
            for page, (data, content_type) in images.items():
                print(f"{page}: {content_type}, {len(data)} bytes")
            return 0
        token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "").strip()
        if not token:
            raise DeployError("LINE_CHANNEL_ACCESS_TOKEN is not set")
        with httpx.Client(headers={"Authorization": f"Bearer {token}"}, timeout=30) as client:
            ids = deploy(client, images)
    except DeployError as error:
        print(f"rich menu deploy failed: {error}", file=sys.stderr)
        return 1
    for page, menu_id in ids.items():
        print(f"{page}: {menu_id} ({ALIASES[page]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

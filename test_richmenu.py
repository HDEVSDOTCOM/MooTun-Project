from __future__ import annotations

import json
import re
import struct
import zlib
from itertools import combinations

import httpx
import pytest

import richmenu_config as config
import richmenu_deploy as deploy_module
from parser import CommandKind, parse_command
from richmenu_deploy import DeployError, deploy, image_info, load_images
from webapp_routes import SPA_TABS

STACKED_THAI_MARKS = re.compile(r"[ัิ-ื็][่-๋]")


def _action(page: str, area: str) -> dict:
    return config.PAGES[page][area]


def test_areas_tile_canvas_without_overlap():
    width, height = config.CANVAS
    rects = list(config.AREAS.values())
    for x, y, w, h in rects:
        assert 0 <= x and 0 <= y and w > 0 and h > 0
        assert x + w <= width and y + h <= height
    for (ax, ay, aw, ah), (bx, by, bw, bh) in combinations(rects, 2):
        assert ax + aw <= bx or bx + bw <= ax or ay + ah <= by or by + bh <= ay
    assert sum(w * h for _, _, w, h in rects) == width * height


def test_pages_share_geometry_and_limit():
    assert set(config.PAGES) == {"page1", "page2"}
    for areas in config.PAGES.values():
        assert list(areas) == list(config.AREAS)
        assert len(areas) <= 20


@pytest.mark.parametrize(
    ("page", "area", "kind"),
    [
        ("page1", "R1A", CommandKind.MONTHLY_SUMMARY),
        ("page1", "R2B", CommandKind.RECENT),
        ("page1", "R3B", CommandKind.HELP),
        ("page2", "BIG", CommandKind.SAVINGS_STATUS),
        ("page2", "R2A", CommandKind.DELETE_LATEST),
        ("page2", "R2B", CommandKind.EXPORT),
        ("page2", "R3B", CommandKind.HELP),
    ],
)
def test_message_buttons_parse_to_commands(page, area, kind):
    action = _action(page, area)
    assert action["type"] == "message"
    assert parse_command(action["text"]).kind is kind


@pytest.mark.parametrize(
    ("area", "sample", "kind"),
    [
        ("R1A", "5000 ทริป", CommandKind.SET_SAVINGS_GOAL),
        ("R1B", "100", CommandKind.ADD_SAVINGS),
        ("R3A", "5 ดีมาก", CommandKind.FEEDBACK),
    ],
)
def test_keyboard_buttons_prefill_valid_commands(area, sample, kind):
    action = _action("page2", area)
    assert action["type"] == "postback"
    assert action["inputOption"] == "openKeyboard"
    assert parse_command(action["fillInText"] + sample).kind is kind


def test_compose_button_opens_empty_keyboard():
    action = _action("page1", "BIG")
    assert action["type"] == "postback"
    assert action["inputOption"] == "openKeyboard"
    assert "fillInText" not in action


def test_uri_buttons_target_our_liff_tabs():
    pattern = re.compile(rf"https://liff\.line\.me/{re.escape(config.LIFF_ID)}/([a-z]+)")
    uris = [a for areas in config.PAGES.values() for a in areas.values() if a["type"] == "uri"]
    assert uris
    for action in uris:
        match = pattern.fullmatch(action["uri"])
        assert match and match.group(1) in SPA_TABS
    assert _action("page1", "R1B")["uri"].endswith("/analysis")
    assert _action("page1", "R2A")["uri"].endswith("/analysis")
    assert _action("page1", "R3A")["uri"].endswith("/settings")


def test_switch_buttons_target_defined_aliases():
    forward = _action("page1", "WIDE")
    back = _action("page2", "WIDE")
    assert forward["type"] == back["type"] == "richmenuswitch"
    assert forward["richMenuAliasId"] == config.ALIASES["page2"]
    assert back["richMenuAliasId"] == config.ALIASES["page1"]


def test_line_limits():
    for page in config.PAGES:
        assert len(config.build_richmenu(page)["chatBarText"]) <= 14
    for alias in config.ALIASES.values():
        assert re.fullmatch(r"[a-z0-9_-]{1,32}", alias)
        assert alias.startswith(config.NAME_PREFIX)
    for areas in config.PAGES.values():
        for action in areas.values():
            assert len(action.get("data", "")) <= 300
            assert 0 < len(action["label"]) <= 20
    # Page 2 labels are drawn by Pillow without raqm, which drops stacked marks.
    # Page 1 labels only describe the owner art and are never rendered.
    for action in config.PAGES["page2"].values():
        assert not STACKED_THAI_MARKS.search(action["label"])


def test_build_richmenu_shape():
    menu = config.build_richmenu("page1")
    assert menu["name"] == "mootoon-page1"
    assert menu["selected"] is True
    assert menu["size"] == {"width": 2500, "height": 1686}
    assert menu["areas"][0]["bounds"] == {"x": 0, "y": 0, "width": 1375, "height": 1067}
    assert menu["areas"][0]["action"] == config.PAGES["page1"]["BIG"]
    with pytest.raises(KeyError):
        config.build_richmenu("page3")


# --- deploy -----------------------------------------------------------------


def _png(width: int, height: int) -> bytes:
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    chunk = b"IHDR" + ihdr
    return b"\x89PNG\r\n\x1a\n" + struct.pack(">I", len(ihdr)) + chunk + struct.pack(">I", zlib.crc32(chunk))


REAL_CLIENT = httpx.Client  # tests below monkeypatch httpx.Client


class FakeLine:
    """In-memory Messaging API: rich menus, aliases, default menu, request log."""

    def __init__(self, menus=None, aliases=None, fail=None):
        self.menus = dict(menus or {})  # id -> name
        self.aliases = dict(aliases or {})  # alias -> menu id
        self.default = None
        self.uploaded = {}
        self.log: list[str] = []
        self.fail = fail or {}  # "METHOD host/path" prefix -> response
        self._next = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        key = f"{request.method} {request.url.host}{path}"
        self.log.append(key)
        for prefix, response in self.fail.items():
            if key.startswith(prefix):
                return response
        if path == "/v2/bot/richmenu/validate":
            return httpx.Response(200, json={})
        if request.method == "POST" and path == "/v2/bot/richmenu":
            self._next += 1
            menu_id = f"richmenu-new{self._next}"
            self.menus[menu_id] = json.loads(request.content)["name"]
            return httpx.Response(200, json={"richMenuId": menu_id})
        if path.endswith("/content"):
            self.uploaded[path.split("/")[4]] = request.headers["content-type"]
            return httpx.Response(200, json={})
        if path == "/v2/bot/richmenu/alias/list":
            aliases = [{"richMenuAliasId": a, "richMenuId": m} for a, m in self.aliases.items()]
            return httpx.Response(200, json={"aliases": aliases})
        if request.method == "POST" and path == "/v2/bot/richmenu/alias":
            body = json.loads(request.content)
            self.aliases[body["richMenuAliasId"]] = body["richMenuId"]
            return httpx.Response(200, json={})
        if request.method == "POST" and path.startswith("/v2/bot/richmenu/alias/"):
            self.aliases[path.rsplit("/", 1)[1]] = json.loads(request.content)["richMenuId"]
            return httpx.Response(200, json={})
        if path.startswith("/v2/bot/user/all/richmenu/"):
            self.default = path.rsplit("/", 1)[1]
            return httpx.Response(200, json={})
        if path == "/v2/bot/richmenu/list":
            menus = [{"richMenuId": i, "name": n} for i, n in self.menus.items()]
            return httpx.Response(200, json={"richmenus": menus})
        if request.method == "DELETE" and path.startswith("/v2/bot/richmenu/alias/"):
            self.aliases.pop(path.rsplit("/", 1)[1], None)
            return httpx.Response(200, json={})
        if request.method == "DELETE" and path.startswith("/v2/bot/richmenu/"):
            self.menus.pop(path.rsplit("/", 1)[1], None)
            return httpx.Response(200, json={})
        return httpx.Response(404, json={"message": "not in fake"})

    def client(self, token: str = "test-token") -> httpx.Client:
        return REAL_CLIENT(
            transport=httpx.MockTransport(self.handler), headers={"Authorization": f"Bearer {token}"}
        )


IMAGES = {"page1": (b"one", "image/jpeg"), "page2": (b"two", "image/png")}


def test_image_info_reads_jpeg_and_png():
    assert image_info(_png(2500, 1686)) == ("image/png", 2500, 1686)
    assert image_info(config.IMAGE_PATHS["page1"].read_bytes()) == ("image/jpeg", 2500, 1686)


def test_image_info_rejects_other_bytes():
    for data in (b"", b"GIF89a....", b"\xff\xd8\xff\xe0truncated"):
        with pytest.raises(DeployError):
            image_info(data)


def test_committed_images_are_valid():
    images = load_images()
    assert set(images) == {"page1", "page2"}
    for data, content_type in images.values():
        assert content_type == "image/jpeg"
        assert len(data) <= deploy_module.MAX_IMAGE_BYTES


def test_load_images_rejects_wrong_size_and_oversize(tmp_path):
    small = tmp_path / "small.png"
    small.write_bytes(_png(1200, 810))
    with pytest.raises(DeployError, match="2500x1686"):
        load_images({"page1": small})
    big = tmp_path / "big.png"
    big.write_bytes(_png(2500, 1686) + b"\0" * deploy_module.MAX_IMAGE_BYTES)
    with pytest.raises(DeployError, match="bytes"):
        load_images({"page1": big})
    with pytest.raises(DeployError, match="missing"):
        load_images({"page1": tmp_path / "nope.jpg"})


def test_png_named_jpg_uses_signature_type(tmp_path):
    path = tmp_path / "page1.jpg"
    path.write_bytes(_png(2500, 1686))
    assert load_images({"page1": path})["page1"][1] == "image/png"


def test_first_deploy_creates_aliases_and_default():
    line = FakeLine()
    ids = deploy(line.client(), IMAGES)
    assert ids == {"page1": "richmenu-new1", "page2": "richmenu-new2"}
    assert line.aliases == {"mootoon-page1": "richmenu-new1", "mootoon-page2": "richmenu-new2"}
    assert line.default == "richmenu-new1"
    assert line.uploaded == {"richmenu-new1": "image/jpeg", "richmenu-new2": "image/png"}
    assert line.log[:4] == [
        "POST api.line.me/v2/bot/richmenu/validate",
        "POST api.line.me/v2/bot/richmenu",
        "POST api-data.line.me/v2/bot/richmenu/richmenu-new1/content",
        "POST api.line.me/v2/bot/richmenu/validate",
    ]
    assert line.log.count("POST api.line.me/v2/bot/richmenu/alias") == 2
    default_call = line.log.index("POST api.line.me/v2/bot/user/all/richmenu/richmenu-new1")
    assert default_call > line.log.index("POST api.line.me/v2/bot/richmenu/alias")


def test_redeploy_updates_aliases_and_deletes_old_mootoon_menus():
    line = FakeLine(
        menus={"old1": "mootoon-page1", "old2": "mootoon-page2", "orphan": "mootoon-page2", "keep": "other-menu"},
        aliases={"mootoon-page1": "old1", "mootoon-page2": "old2"},
    )
    deploy(line.client(), IMAGES)
    assert set(line.menus) == {"keep", "richmenu-new1", "richmenu-new2"}
    assert line.aliases == {"mootoon-page1": "richmenu-new1", "mootoon-page2": "richmenu-new2"}
    assert "POST api.line.me/v2/bot/richmenu/alias" not in line.log
    assert "POST api.line.me/v2/bot/richmenu/alias/mootoon-page1" in line.log


def test_foreign_aliases_untouched():
    line = FakeLine(menus={"x": "other"}, aliases={"campaign": "x"})
    deploy(line.client(), IMAGES)
    assert line.aliases["campaign"] == "x"
    assert not any("alias/campaign" in entry for entry in line.log)


def test_failure_cleans_up_created_menus():
    line = FakeLine(
        menus={"old1": "mootoon-page1"},
        aliases={"mootoon-page1": "old1"},
        fail={
            "POST api-data.line.me/v2/bot/richmenu/richmenu-new2/content": httpx.Response(
                400, json={"message": "bad image"}
            )
        },
    )
    with pytest.raises(DeployError) as error:
        deploy(line.client(), IMAGES)
    assert "400" in str(error.value) and "bad image" in str(error.value)
    assert line.menus == {"old1": "mootoon-page1"}
    assert line.aliases == {"mootoon-page1": "old1"}
    assert line.default is None


def test_alias_failure_restores_repointed_aliases():
    line = FakeLine(
        menus={"old1": "mootoon-page1", "old2": "mootoon-page2"},
        aliases={"mootoon-page1": "old1", "mootoon-page2": "old2"},
        fail={"POST api.line.me/v2/bot/richmenu/alias/mootoon-page2": httpx.Response(500, json={"message": "boom"})},
    )
    with pytest.raises(DeployError, match="500"):
        deploy(line.client(), IMAGES)
    assert line.aliases == {"mootoon-page1": "old1", "mootoon-page2": "old2"}
    assert set(line.menus) == {"old1", "old2"}


def test_first_deploy_alias_failure_removes_new_aliases():
    calls = {"n": 0}
    line = FakeLine()
    original = line.handler

    def second_alias_create_fails(request):
        if request.method == "POST" and request.url.path == "/v2/bot/richmenu/alias":
            calls["n"] += 1
            if calls["n"] == 2:
                line.log.append("POST alias (failed)")
                return httpx.Response(500, json={"message": "boom"})
        return original(request)

    line.handler = second_alias_create_fails
    with pytest.raises(DeployError):
        deploy(line.client(), IMAGES)
    assert line.aliases == {}
    assert line.menus == {}


def test_non_json_error_body():
    line = FakeLine(
        fail={"POST api.line.me/v2/bot/richmenu/validate": httpx.Response(502, text="<html>Bad Gateway</html>")}
    )
    with pytest.raises(DeployError) as error:
        deploy(line.client(), IMAGES)
    message = str(error.value)
    assert "502" in message and "/v2/bot/richmenu/validate" in message and "Bad Gateway" in message


def test_main_requires_token(monkeypatch, capsys):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(deploy_module.httpx, "Client", lambda *a, **k: pytest.fail("network used"))
    assert deploy_module.main([]) == 1
    assert "LINE_CHANNEL_ACCESS_TOKEN" in capsys.readouterr().err


def test_main_dry_run_needs_no_token(monkeypatch, capsys):
    monkeypatch.delenv("LINE_CHANNEL_ACCESS_TOKEN", raising=False)
    monkeypatch.setattr(deploy_module.httpx, "Client", lambda *a, **k: pytest.fail("network used"))
    assert deploy_module.main(["--dry-run"]) == 0
    assert "mootoon-page2" in capsys.readouterr().out


def test_token_never_in_output(monkeypatch, capsys):
    token = "secret-token-xyz"
    line = FakeLine(
        fail={"POST api.line.me/v2/bot/richmenu/validate": httpx.Response(401, json={"message": "Authentication failed"})}
    )
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", token)
    monkeypatch.setattr(deploy_module.httpx, "Client", lambda *a, **k: line.client(token))
    assert deploy_module.main([]) == 1
    captured = capsys.readouterr()
    assert "401" in captured.err
    assert token not in captured.err + captured.out

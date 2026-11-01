from __future__ import annotations

import re
from itertools import combinations

import pytest

import richmenu_config as config
from parser import CommandKind, parse_command
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

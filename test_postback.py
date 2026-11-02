from __future__ import annotations

import pytest

from postback import HELP_TOPICS, DeleteTx, HelpTopic, Undo, parse_postback

HEX = "0123456789abcdef0123456789abcdef"


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("a=del&t=42", DeleteTx(42)),
        ("a=del&t=123456789", DeleteTx(123456789)),
        (f"a=undo&id={HEX}", Undo(HEX)),
        *[(f"a=help&t={topic}", HelpTopic(topic)) for topic in HELP_TOPICS],
    ],
)
def test_parse_postback_accepts(data, expected):
    assert parse_postback(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        "richmenu=compose",
        "richmenu=page2",
        "a=del&t=0",
        "a=del&t=1234567890",
        "a=del&t=-1",
        "a=del&t=007",
        "a=del&t=4&t=5",
        "a=del",
        "a=del&t=",
        "a=undo&id=XYZ",
        f"a=undo&id={HEX[:-1]}",
        f"a=undo&id={HEX.upper()}",
        "a=help&t=admin",
        "a=del&t=4&x=1",
        "a=nuke&t=1",
        "",
        "a=del&t=4" + "&" * 300,
        None,
        b"a=del&t=4",
        12,
    ],
)
def test_parse_postback_rejects(data):
    assert parse_postback(data) is None

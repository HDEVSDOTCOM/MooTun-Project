"""Shared pytest setup."""

import pytest

import app as app_module


@pytest.fixture(autouse=True)
def _no_loading_pause(monkeypatch):
    """The webhook holds replies so "..." is visible; tests don't need to wait."""

    monkeypatch.setattr(app_module, "LOADING_MIN_SECONDS", 0)

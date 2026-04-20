"""Shared fixtures for the dash-wrap test suite."""

from __future__ import annotations

import pytest
from dash import Dash, dcc


def pytest_setup_options():
    """Chrome options used by DashDuo's Selenium driver.

    ``--no-sandbox`` + ``--disable-dev-shm-usage`` are required on
    GitHub's ubuntu runners (and most container environments) — without
    them Chrome exits immediately with SessionNotCreatedException.
    """
    from selenium.webdriver.chrome.options import Options

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    return options


@pytest.fixture
def make_graph():
    """Return a factory for fresh ``dcc.Graph`` instances.

    Each call returns a new graph with a unique id and a trivial figure,
    so tests can't accidentally share state through the component
    instance.
    """
    counter = {"i": 0}

    def _make(id_: str | None = None, figure: dict | None = None) -> dcc.Graph:
        counter["i"] += 1
        return dcc.Graph(
            id=id_ or f"graph-{counter['i']}",
            figure=figure if figure is not None else {"data": [], "layout": {}},
        )

    return _make


@pytest.fixture
def app() -> Dash:
    """Return a fresh ``Dash`` app with an isolated callback registry."""
    return Dash(__name__)

"""Shared fixtures for the dash-wrap test suite."""

from __future__ import annotations

import pytest
from dash import Dash, dcc


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

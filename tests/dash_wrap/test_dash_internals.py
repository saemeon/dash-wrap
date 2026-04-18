"""Regression-pin tests for the undocumented Dash internals we rely on.

If Dash ever renames or removes ``Component._set_random_id`` or
``Component._prop_names``, these tests fail loudly. The CI matrix runs
this file against every supported Dash version so the breakage surfaces
before release.
"""

from __future__ import annotations

import pytest
from dash import Input, Output, dcc
from dash.development.base_component import Component

from dash_wrap import wrap


def test_set_random_id_exists_on_component():
    assert hasattr(Component, "_set_random_id")
    assert callable(Component._set_random_id)


def test_prop_names_available_on_dcc_graph_instance():
    # In Dash 4.x ``_prop_names`` became an instance attribute set in
    # ``Component.__init__``. Our validator reads it via ``getattr`` on
    # the innermost instance, so that's what we pin here.
    g = dcc.Graph(id="x")
    pns = g._prop_names
    for name in ("figure", "config", "responsive"):
        assert name in pns, (
            f"dcc.Graph._prop_names no longer lists {name!r}; "
            "update dash_wrap/_defaults.py."
        )


def test_dash_dependency_invokes_set_random_id_on_wrapper(monkeypatch, make_graph):
    graph = make_graph(id_="watched")
    wrapper = wrap(graph)

    calls: list[int] = []
    original = type(wrapper)._set_random_id

    def spy(self):
        calls.append(1)
        return original(self)

    monkeypatch.setattr(type(wrapper), "_set_random_id", spy)
    dep = Output(wrapper, "figure")
    assert dep.component_id == "watched"
    assert calls, "Dash did not call _set_random_id on the wrapper"


def test_dash_input_dependency_resolves_wrapper_id(make_graph):
    graph = make_graph(id_="watched")
    wrapper = wrap(graph)
    dep = Input(wrapper, "figure")
    assert dep.component_id == "watched"


@pytest.mark.parametrize(
    "prop, component_factory",
    [
        ("figure", lambda: dcc.Graph(id="x")),
        ("value", lambda: dcc.Input(id="x")),
        ("value", lambda: dcc.Dropdown(id="x")),
        ("data", lambda: dcc.Store(id="x")),
    ],
)
def test_proxy_defaults_reference_real_props(prop, component_factory):
    c = component_factory()
    assert prop in c._prop_names


def test_dash_version_accessible():
    import dash

    assert hasattr(dash, "__version__")
    major = int(dash.__version__.split(".")[0])
    # Our floor is Dash 2.9 — run on 2.x or 3.x or later.
    assert major >= 2

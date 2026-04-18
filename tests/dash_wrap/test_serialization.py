"""Unit tests for Dash layout emission and copy / pickle round-trips."""

from __future__ import annotations

import copy
import pickle

from dash import dcc, html

from dash_wrap import wrap


def test_to_plotly_json_type_is_div(make_graph):
    wrapper = wrap(make_graph())
    descriptor = wrapper.to_plotly_json()
    assert descriptor["type"] == "Div"
    assert descriptor["namespace"] == "dash_html_components"


def test_to_plotly_json_has_no_id(make_graph):
    wrapper = wrap(make_graph())
    descriptor = wrapper.to_plotly_json()
    assert "id" not in descriptor["props"]


def test_inner_component_appears_in_children(make_graph):
    graph = make_graph()
    wrapper = wrap(graph)
    descriptor = wrapper.to_plotly_json()
    children = descriptor["props"]["children"]
    assert len(children) == 1
    assert children[0] is graph


def test_figure_container_serialises_as_figure(make_graph):
    wrapper = wrap(make_graph(), container=html.Figure)
    assert wrapper.to_plotly_json()["type"] == "Figure"


def test_deepcopy_wrapper_has_independent_inner(make_graph):
    graph = make_graph()
    wrapper = wrap(graph)
    clone = copy.deepcopy(wrapper)
    assert clone is not wrapper
    assert clone.__wrapped__ is not graph
    # mutate the clone's inner; original stays untouched.
    clone.figure = {"data": [99]}
    assert graph.figure == {"data": [], "layout": {}}


def test_pickle_roundtrip(make_graph):
    graph = make_graph(figure={"data": [1]})
    wrapper = wrap(graph)
    restored = pickle.loads(pickle.dumps(wrapper))
    assert restored._set_random_id() == graph.id
    assert restored.figure == {"data": [1]}
    assert isinstance(restored, dcc.Graph)


# ---------- (N) nested serialisation ------------------------------------


def test_nested_serialisation_produces_nested_divs(make_graph):
    graph = make_graph()
    outer = wrap(wrap(graph))
    descriptor = outer.to_plotly_json()
    assert descriptor["type"] == "Div"
    inner_descriptor = descriptor["props"]["children"][0].to_plotly_json()
    assert inner_descriptor["type"] == "Div"
    assert inner_descriptor["props"]["children"][0] is graph

"""Unit tests for user subclassing of ``ComponentWrapper`` and the
tier-2 factory-generated classes."""

from __future__ import annotations

import pytest
from dash import dcc, html

from dash_wrap import ComponentWrapper, make_wrapper_class


class ChartCard(ComponentWrapper[dcc.Graph]):
    """Example card-styled wrapper for a graph."""

    def __init__(self, graph: dcc.Graph, title: str) -> None:
        super().__init__(
            graph,
            proxy_props=["figure", "config"],
            children=[html.H3(title), graph],
            className="card",
        )


def test_subclass_instance_retains_wrapper_behaviour(make_graph):
    graph = make_graph()
    card = ChartCard(graph, title="Revenue")
    assert isinstance(card, dcc.Graph)
    assert isinstance(card, ComponentWrapper)
    assert card._set_random_id() == graph.id
    assert card.figure == graph.figure
    assert card.className == "card"


def test_subclass_proxy_set_write_reaches_inner(make_graph):
    graph = make_graph()
    card = ChartCard(graph, title="t")
    card.figure = {"data": [1, 2, 3]}
    assert graph.figure == {"data": [1, 2, 3]}


def test_subclass_prop_names_is_divs(make_graph):
    graph = make_graph()
    card = ChartCard(graph, title="t")
    assert "children" in card._prop_names
    assert "figure" not in card._prop_names


def test_subclass_preserves_generic_parameterisation():
    # Parameterisation at the class level should not raise — this lets
    # users write ``MySubclass[dcc.Graph]`` in annotations.
    assert ComponentWrapper[dcc.Graph] is not None


def test_subclass_that_skips_super_init_errors(make_graph):
    class Broken(ComponentWrapper[dcc.Graph]):
        def __init__(self, graph: dcc.Graph) -> None:
            # deliberately do NOT call super().__init__
            pass

    broken = Broken(make_graph())
    # With no __init__, _proxy_props and __wrapped__ are not set; any
    # attribute access that would otherwise hit the proxy chain raises.
    with pytest.raises(AttributeError):
        _ = broken.figure


# ---------- tier-2 subclassing ------------------------------------------


FigureWrapper = make_wrapper_class(html.Figure)


class CaptionedChart(FigureWrapper[dcc.Graph]):
    """Example tier-2 subclass of a non-Div wrapper."""

    def __init__(self, graph: dcc.Graph, caption: str) -> None:
        super().__init__(
            graph,
            proxy_props=["figure", "config"],
            children=[graph, html.Figcaption(caption)],
        )


def test_tier2_subclass_renders_as_figure(make_graph):
    graph = make_graph()
    card = CaptionedChart(graph, caption="ABS 2024")
    assert card.to_plotly_json()["type"] == "Figure"
    assert isinstance(card, dcc.Graph)
    assert isinstance(card, html.Figure)
    assert card._set_random_id() == graph.id

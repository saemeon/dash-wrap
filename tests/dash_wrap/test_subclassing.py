"""Unit tests for user subclassing.

Covers both tier-1 (``ComponentWrapper``) and tier-2
(factory-generated non-Div wrapper classes) subclassing.
"""

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


def test_subclass_class_attribute_shadows_proxy_forwarding(make_graph):
    """Subclass-defined class attributes win over proxy forwarding.

    ``__getattr__`` runs only when normal descriptor/class lookup
    fails, so a subclass attribute (even one named like a proxy prop)
    is served from the subclass, not forwarded to the inner
    component. Documented expectation that the
    forwarding-follows-not-shadows rule matches Python's normal
    MRO semantics.
    """

    class Tagged(ComponentWrapper[dcc.Graph]):
        tag = "card-v1"  # class attribute, not a proxy prop
        figure = "CLASS-DEFINED"  # deliberately collides with Graph's prop

        def __init__(self, graph: dcc.Graph) -> None:
            super().__init__(graph, proxy_props=["figure", "config"])

    graph = make_graph(figure={"data": [{"y": [1]}]})
    tagged = Tagged(graph)
    # tag is not in proxy_props and not on html.Div — subclass wins.
    assert tagged.tag == "card-v1"
    # figure IS in proxy_props, but because it's also a class-level
    # attribute, normal lookup finds it before __getattr__ fires.
    # The inner's figure is unchanged; the wrapper exposes the class
    # attr. This is Python's defined attribute-resolution order —
    # users who want proxy behaviour must not also set a class attr
    # of the same name.
    assert tagged.figure == "CLASS-DEFINED"
    assert graph.figure == {"data": [{"y": [1]}]}


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

"""Unit tests for ``ComponentWrapper`` and ``_WrapperMixin``.

Covers construction, adapter methods, attribute proxy, and nested-chain
behaviour. Entries tagged ``(N)`` in CLAUDE.md exercise nested-wrapper
cases.
"""

from __future__ import annotations

import pytest
from dash import dcc, html

from dash_wrap import ComponentWrapper, wrap
from dash_wrap._wrapper import _contains

# ---------- construction --------------------------------------------------


def test_raises_when_inner_has_no_id():
    graph = dcc.Graph(figure={"data": []})
    with pytest.raises(ValueError, match="id"):
        ComponentWrapper(graph, proxy_props=["figure"])


def test_raises_when_inner_is_not_a_component():
    with pytest.raises(TypeError, match="Component"):
        ComponentWrapper("not a component", proxy_props=[])  # type: ignore[arg-type]


def test_accepts_pattern_matching_dict_id():
    graph = dcc.Graph(id={"type": "g", "index": 1}, figure={})
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert wrapper._set_random_id() == {"type": "g", "index": 1}


def test_raises_for_unknown_proxy_prop(make_graph):
    with pytest.raises(ValueError, match="nonexistent"):
        ComponentWrapper(make_graph(), proxy_props=["nonexistent"])


def test_raises_when_children_omits_inner(make_graph):
    graph = make_graph()
    with pytest.raises(ValueError, match="inner"):
        ComponentWrapper(graph, proxy_props=["figure"], children=[html.Div()])


def test_auto_includes_inner_when_children_is_none(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert wrapper.children == [graph]
    assert wrapper.children[0] is graph


def test_explicit_children_with_inner_ok(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"], children=[graph])
    assert wrapper.children == [graph]


def test_children_containment_walks_subtree(make_graph):
    graph = make_graph()
    children = [html.H3("title"), html.Div([html.Small("src"), graph])]
    wrapper = ComponentWrapper(graph, proxy_props=["figure"], children=children)
    assert wrapper.children is children


def test_contains_helper_matches_nested_target(make_graph):
    target = make_graph()
    tree = [html.H3("title"), html.Div([html.Small("src"), target])]
    assert _contains(tree, target) is True


def test_contains_helper_returns_false_for_missing(make_graph):
    target = make_graph()
    other = make_graph()
    tree = [html.H3("title"), html.Div([html.Small("src"), other])]
    assert _contains(tree, target) is False


def test_contains_helper_handles_none_and_primitives():
    assert _contains(None, dcc.Graph(id="x")) is False
    assert _contains("some string", dcc.Graph(id="x")) is False


# ---------- adapter behaviour --------------------------------------------


def test_wrapped_attribute_is_identity(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert wrapper.__wrapped__ is graph


def test_set_random_id_returns_inner_id(make_graph):
    graph = make_graph(id_="specific-id")
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert wrapper._set_random_id() == "specific-id"


def test_set_random_id_does_not_set_id_on_self(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    wrapper._set_random_id()
    # id must remain absent from the wrapper's own __dict__ so no id is
    # serialised into the outer div's props.
    assert "id" not in wrapper.__dict__


def test_proxy_prop_read_returns_inner_value(make_graph):
    graph = make_graph(figure={"data": [1]})
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert wrapper.figure == {"data": [1]}


def test_proxy_prop_write_updates_inner(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    wrapper.figure = {"data": [42]}
    assert graph.figure == {"data": [42]}


def test_non_proxy_read_raises_attribute_error(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    with pytest.raises(AttributeError):
        _ = wrapper.nonexistent_attr


def test_non_proxy_write_lands_on_outer(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    wrapper.style = {"padding": "10px"}
    assert wrapper.style == {"padding": "10px"}
    # And not on the inner: dcc.Graph has its own `style` prop, but we
    # wrote via the outer's __setattr__, so inner's remains unset.
    assert getattr(graph, "style", None) is None


# ---------- identity / isinstance ----------------------------------------


def test_isinstance_matches_inner_type(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert isinstance(wrapper, dcc.Graph)


def test_isinstance_matches_html_div(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert isinstance(wrapper, html.Div)


def test_runtime_type_is_componentwrapper(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    # type() reads the C-level ob_type slot, bypassing the __class__
    # property, so Dash's layout machinery still sees ComponentWrapper.
    assert type(wrapper) is ComponentWrapper


def test_prop_names_inherited_from_div(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=["figure"])
    assert "children" in wrapper._prop_names
    assert "style" in wrapper._prop_names


# ---------- (N) nested-wrapper cases -------------------------------------


def test_nested_two_level_chain(make_graph):
    graph = make_graph()
    inner = wrap(graph)
    outer = wrap(inner)
    assert outer.__wrapped__ is inner
    assert outer.__wrapped__.__wrapped__ is graph


def test_nested_three_level_chain(make_graph):
    graph = make_graph()
    w1 = wrap(graph)
    w2 = wrap(w1)
    w3 = wrap(w2)
    assert w3.__wrapped__ is w2
    assert w3.__wrapped__.__wrapped__ is w1
    assert w3.__wrapped__.__wrapped__.__wrapped__ is graph


def test_nested_id_resolves_to_innermost(make_graph):
    graph = make_graph(id_="innermost")
    w3 = wrap(wrap(wrap(graph)))
    assert w3._set_random_id() == "innermost"


def test_nested_class_spoof_at_all_levels(make_graph):
    graph = make_graph()
    w1 = wrap(graph)
    w2 = wrap(w1)
    w3 = wrap(w2)
    for level in (w1, w2, w3):
        assert isinstance(level, dcc.Graph)
        assert level.__class__ is dcc.Graph


def test_nested_attribute_read_chains_to_graph(make_graph):
    graph = make_graph(figure={"data": [1]})
    w2 = wrap(wrap(graph))
    assert w2.figure == {"data": [1]}


def test_nested_attribute_write_updates_graph_only(make_graph):
    graph = make_graph()
    w1 = wrap(graph)
    w2 = wrap(w1)
    w2.figure = {"data": [99]}
    assert graph.figure == {"data": [99]}
    # intermediate wrapper doesn't hold its own figure copy
    assert "figure" not in w1.__dict__
    assert "figure" not in w2.__dict__


def test_nested_self_reference_is_impossible(make_graph):
    graph = make_graph()
    wrapper = wrap(graph)
    # cycle-prevention is structural; assert the sanity invariant
    assert wrapper.__wrapped__ is not wrapper


# ---------- misc construction --------------------------------------------


def test_div_kwargs_forwarded_to_outer(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(
        graph,
        proxy_props=["figure"],
        className="card",
        style={"padding": "8px"},
    )
    assert wrapper.className == "card"
    assert wrapper.style == {"padding": "8px"}


def test_div_kwargs_with_id_on_outer(make_graph):
    graph = make_graph(id_="inner-id")
    wrapper = ComponentWrapper(graph, proxy_props=["figure"], id="outer-id")
    # If the caller deliberately passes an `id`, the outer div keeps it;
    # callback resolution still goes through inner via _set_random_id.
    assert wrapper.id == "outer-id"
    assert wrapper._set_random_id() == "inner-id"


def test_empty_proxy_props_allowed(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=[])
    assert wrapper._proxy_props == frozenset()
    with pytest.raises(AttributeError):
        _ = wrapper.figure


def test_proxy_props_stored_as_frozenset(make_graph):
    graph = make_graph()
    wrapper = ComponentWrapper(graph, proxy_props=("figure", "config", "figure"))
    assert wrapper._proxy_props == frozenset({"figure", "config"})

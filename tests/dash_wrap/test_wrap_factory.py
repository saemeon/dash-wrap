"""Unit tests for :func:`dash_wrap.wrap`, the proxy-defaults registry,
and :func:`dash_wrap.is_wrapped`."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from dash import dcc, html

from dash_wrap import (
    ComponentWrapper,
    is_wrapped,
    register_proxy_defaults,
    wrap,
)
from dash_wrap._defaults import _DEFAULTS, get_proxy_defaults

# ---------- wrap() default-lookup behaviour -------------------------------


def test_wrap_picks_graph_defaults(make_graph):
    wrapper = wrap(make_graph())
    assert set(wrapper._proxy_props) == {"figure", "config", "responsive"}


def test_explicit_proxy_props_overrides_defaults(make_graph):
    wrapper = wrap(make_graph(), proxy_props=["figure"])
    assert wrapper._proxy_props == frozenset({"figure"})


def test_wrap_unknown_component_has_empty_proxy_props():
    # dcc.Store has no entry in the registry: proxy_props defaults to ().
    store = dcc.Store(id="s", data={"x": 1})
    wrapper = wrap(store)
    assert wrapper._proxy_props == frozenset()


def test_wrap_preserves_explicit_children(make_graph):
    graph = make_graph()
    other = html.Small("caption")
    wrapper = wrap(graph, children=[graph, other])
    assert wrapper.children == [graph, other]


def test_wrap_auto_includes_inner_when_children_none(make_graph):
    graph = make_graph()
    wrapper = wrap(graph)
    assert wrapper.children == [graph]


def test_wrap_forwards_div_kwargs(make_graph):
    wrapper = wrap(make_graph(), className="card", style={"padding": "4px"})
    assert wrapper.className == "card"
    assert wrapper.style == {"padding": "4px"}


# ---------- wrap() with custom container ---------------------------------


def test_wrap_with_html_figure_container(make_graph):
    wrapper = wrap(make_graph(), container=html.Figure)
    assert wrapper.to_plotly_json()["type"] == "Figure"
    assert is_wrapped(wrapper)


def test_wrap_default_container_returns_componentwrapper(make_graph):
    wrapper = wrap(make_graph())
    assert isinstance(wrapper, ComponentWrapper)
    assert type(wrapper) is ComponentWrapper


# ---------- register_proxy_defaults --------------------------------------


def test_register_proxy_defaults_is_picked_up():
    saved = dict(_DEFAULTS)
    try:
        register_proxy_defaults(dcc.Store, ["data"])
        wrapper = wrap(dcc.Store(id="s", data={"x": 1}))
        assert "data" in wrapper._proxy_props
    finally:
        _DEFAULTS.clear()
        _DEFAULTS.update(saved)


def test_register_proxy_defaults_is_idempotent():
    saved = dict(_DEFAULTS)
    try:
        register_proxy_defaults(dcc.Store, ["data"])
        register_proxy_defaults(dcc.Store, ["data", "storage_type"])
        assert get_proxy_defaults(dcc.Store) == ("data", "storage_type")
    finally:
        _DEFAULTS.clear()
        _DEFAULTS.update(saved)


def test_register_proxy_defaults_rejects_non_component():
    with pytest.raises(TypeError, match="Component"):
        register_proxy_defaults(int, ["x"])  # type: ignore[arg-type]


# ---------- nested proxy_props inheritance (N) ---------------------------


def test_wrap_wrap_inherits_inner_proxy_props(make_graph):
    graph = make_graph()
    inner = wrap(graph)
    outer = wrap(inner)
    # Without this inheritance, type(inner) is ComponentWrapper, which
    # has no registry entry — outer would get an empty proxy_props and
    # attribute access would break.
    assert outer._proxy_props == inner._proxy_props


def test_wrap_wrap_explicit_overrides_inheritance(make_graph):
    graph = make_graph()
    inner = wrap(graph)
    outer = wrap(inner, proxy_props=["figure"])
    assert outer._proxy_props == frozenset({"figure"})


# ---------- is_wrapped ----------------------------------------------------


def test_is_wrapped_true_for_wrap_result(make_graph):
    assert is_wrapped(wrap(make_graph())) is True


def test_is_wrapped_false_for_bare_graph(make_graph):
    assert is_wrapped(make_graph()) is False


def test_is_wrapped_false_for_plain_div():
    assert is_wrapped(html.Div()) is False


def test_is_wrapped_true_for_non_div_container(make_graph):
    wrapper = wrap(make_graph(), container=html.Section)
    assert is_wrapped(wrapper) is True


def test_is_wrapped_false_for_object_with_unrelated_wrapped_attr():
    # Simulate functools.wraps / wrapt.ObjectProxy: attribute is present
    # but the object is not a dash-wrap wrapper.
    impostor = SimpleNamespace(__wrapped__=dcc.Graph(id="x"))
    assert is_wrapped(impostor) is False


def test_is_wrapped_false_for_arbitrary_values():
    for v in (None, 42, "str", [1, 2], {"a": 1}):
        assert is_wrapped(v) is False

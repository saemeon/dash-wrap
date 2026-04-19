"""Unit tests for :func:`dash_wrap.make_wrapper_class`.

Covers the non-Div subclassing factory and its class cache.
"""

from __future__ import annotations

import pytest
from dash import dcc, html

from dash_wrap import ComponentWrapper, make_wrapper_class
from dash_wrap._wrapper import _WrapperMixin


def test_html_div_returns_componentwrapper():
    assert make_wrapper_class(html.Div) is ComponentWrapper


def test_non_div_container_returns_distinct_class():
    fig_cls = make_wrapper_class(html.Figure)
    assert fig_cls is not ComponentWrapper
    assert issubclass(fig_cls, html.Figure)
    assert issubclass(fig_cls, _WrapperMixin)


def test_cache_returns_same_class_on_repeated_calls():
    a = make_wrapper_class(html.Figure)
    b = make_wrapper_class(html.Figure)
    assert a is b


def test_generated_class_has_sensible_name():
    fig_cls = make_wrapper_class(html.Figure)
    assert fig_cls.__name__ == "FigureWrapper"
    assert fig_cls.__qualname__ == "FigureWrapper"


def test_generated_class_is_generic_parameterisable():
    fig_cls = make_wrapper_class(html.Figure)
    # Generic[T] support: parameterisation does not raise and returns
    # something usable as a base class.
    parameterised = fig_cls[dcc.Graph]
    assert parameterised is not None


def test_generated_class_instance_renders_as_container_type(make_graph):
    sec_cls = make_wrapper_class(html.Section)
    wrapper = sec_cls(make_graph(), proxy_props=["figure"])
    assert wrapper.to_plotly_json()["type"] == "Section"


def test_rejects_non_component_container():
    with pytest.raises(TypeError, match="Component"):
        make_wrapper_class(int)  # type: ignore[arg-type]


# ---------- (N) nested cross-container ------------------------------------


def test_figure_wrapper_inside_component_wrapper(make_graph):
    graph = make_graph()
    fig_cls = make_wrapper_class(html.Figure)
    inner = fig_cls(graph, proxy_props=["figure"])
    # Outer is a ComponentWrapper (html.Div based)
    outer = ComponentWrapper(inner, proxy_props=["figure"])
    assert outer.to_plotly_json()["type"] == "Div"
    assert outer.children[0].to_plotly_json()["type"] == "Figure"
    assert outer._set_random_id() == graph.id


def test_component_wrapper_inside_figure_wrapper(make_graph):
    graph = make_graph()
    fig_cls = make_wrapper_class(html.Figure)
    inner = ComponentWrapper(graph, proxy_props=["figure"])
    outer = fig_cls(inner, proxy_props=["figure"])
    assert outer.to_plotly_json()["type"] == "Figure"
    assert outer.children[0].to_plotly_json()["type"] == "Div"
    assert outer._set_random_id() == graph.id

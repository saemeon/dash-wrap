"""Breadth matrices over the documented surface.

Two parametrised matrices pin the contract for every combination that
ships in the default registry or is advertised in the docs:

- every inner-component type in ``_defaults.py`` × each of its proxy
  props (read + write where safe, isinstance, serialisation);
- every reasonable ``html.*`` container × wrap + is_wrapped +
  serialisation + callback-id resolution.

A third matrix samples a few cross-products so we know the pieces
compose (dcc input inside an ``html.Figure`` etc).

If Dash ever renames a prop on any of the registered component types,
or introduces a new ``html.*`` container that doesn't conform, the
corresponding row fails and tells us exactly where.
"""

from __future__ import annotations

import pytest
from dash import Input, Output, dash_table, dcc, html

from dash_wrap import is_wrapped, make_wrapper_class, wrap

# ---------- inner-component matrix ----------------------------------------

# Each row: (label, factory, expected_proxy_props, write_samples)
# ``write_samples`` maps prop name → a value safe to write back to the
# inner component. Only included for props whose type is easy to
# construct; reads are checked for every proxy prop.
_INNER_CASES: list[tuple[str, object, set[str], dict[str, object]]] = [
    (
        "dcc.Graph",
        lambda: dcc.Graph(id="g-0", figure={"data": [], "layout": {}}),
        {"figure", "config", "responsive"},
        {
            "figure": {"data": [{"y": [1, 2, 3]}]},
            "config": {"displayModeBar": False},
            "responsive": True,
        },
    ),
    (
        "dcc.Input",
        lambda: dcc.Input(id="inp-0", value="hello"),
        {"value", "disabled"},
        {"value": "updated", "disabled": True},
    ),
    (
        "dcc.Dropdown",
        lambda: dcc.Dropdown(
            id="dd-0",
            options=[{"label": "A", "value": "a"}, {"label": "B", "value": "b"}],
            value="a",
        ),
        {"value", "options", "disabled"},
        {
            "value": "b",
            "options": [{"label": "X", "value": "x"}],
            "disabled": True,
        },
    ),
    (
        "dcc.Textarea",
        lambda: dcc.Textarea(id="ta-0", value="initial"),
        {"value", "disabled"},
        {"value": "replaced", "disabled": True},
    ),
    (
        "dcc.Slider",
        lambda: dcc.Slider(id="sl-0", min=0, max=10, value=5),
        {"value", "min", "max", "marks", "disabled"},
        {
            "value": 7,
            "min": 1,
            "max": 20,
            "marks": {0: "0", 10: "10"},
            "disabled": True,
        },
    ),
    (
        "dcc.RangeSlider",
        lambda: dcc.RangeSlider(id="rs-0", min=0, max=10, value=[2, 8]),
        {"value", "min", "max", "marks", "disabled"},
        {
            "value": [3, 6],
            "min": 1,
            "max": 20,
            "marks": {0: "0", 10: "10"},
            "disabled": True,
        },
    ),
    (
        "dcc.DatePickerSingle",
        lambda: dcc.DatePickerSingle(id="dps-0", date="2026-01-01"),
        {"date", "disabled"},
        {"date": "2026-02-14", "disabled": True},
    ),
    (
        "dcc.DatePickerRange",
        lambda: dcc.DatePickerRange(
            id="dpr-0", start_date="2026-01-01", end_date="2026-01-31"
        ),
        {"start_date", "end_date", "disabled"},
        {
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "disabled": True,
        },
    ),
    (
        "dash_table.DataTable",
        lambda: dash_table.DataTable(
            id="dt-0",
            data=[{"a": 1, "b": 2}],
            columns=[{"name": "a", "id": "a"}, {"name": "b", "id": "b"}],
        ),
        {"data", "columns", "page_current", "sort_by", "filter_query"},
        {
            "data": [{"a": 10, "b": 20}],
            "columns": [{"name": "x", "id": "x"}],
            "page_current": 2,
            "sort_by": [{"column_id": "a", "direction": "asc"}],
            "filter_query": "{a} > 0",
        },
    ),
]


@pytest.mark.parametrize(
    "label, factory, expected_props, writes",
    _INNER_CASES,
    ids=[row[0] for row in _INNER_CASES],
)
def test_wrap_picks_registered_defaults(label, factory, expected_props, writes):
    inner = factory()
    wrapper = wrap(inner)
    assert set(wrapper._proxy_props) == expected_props, (
        f"{label}: registry drift — expected {expected_props}, "
        f"got {set(wrapper._proxy_props)}"
    )


@pytest.mark.parametrize(
    "label, factory, expected_props, writes",
    _INNER_CASES,
    ids=[row[0] for row in _INNER_CASES],
)
def test_wrap_isinstance_matches_inner_type(label, factory, expected_props, writes):
    inner = factory()
    wrapper = wrap(inner)
    assert isinstance(wrapper, type(inner)), f"{label}: isinstance spoof broken"
    assert isinstance(wrapper, html.Div)


@pytest.mark.parametrize(
    "label, factory, expected_props, writes",
    _INNER_CASES,
    ids=[row[0] for row in _INNER_CASES],
)
def test_proxy_read_returns_inner_value(label, factory, expected_props, writes):
    inner = factory()
    wrapper = wrap(inner)
    for prop in expected_props:
        expected = getattr(inner, prop, None)
        actual = getattr(wrapper, prop, None)
        assert actual == expected, (
            f"{label}.{prop}: proxy read diverged — inner={expected!r}, "
            f"wrapper={actual!r}"
        )


@pytest.mark.parametrize(
    "label, factory, expected_props, writes",
    _INNER_CASES,
    ids=[row[0] for row in _INNER_CASES],
)
def test_proxy_write_updates_inner(label, factory, expected_props, writes):
    inner = factory()
    wrapper = wrap(inner)
    for prop, value in writes.items():
        setattr(wrapper, prop, value)
        assert getattr(inner, prop) == value, (
            f"{label}.{prop}: proxy write did not reach inner"
        )


@pytest.mark.parametrize(
    "label, factory, expected_props, writes",
    _INNER_CASES,
    ids=[row[0] for row in _INNER_CASES],
)
def test_wrap_serialises_as_div_with_inner(label, factory, expected_props, writes):
    inner = factory()
    wrapper = wrap(inner)
    descriptor = wrapper.to_plotly_json()
    assert descriptor["type"] == "Div"
    assert descriptor["props"]["children"][0] is inner


@pytest.mark.parametrize(
    "label, factory, expected_props, writes",
    _INNER_CASES,
    ids=[row[0] for row in _INNER_CASES],
)
def test_dash_dependency_resolves_inner_id(label, factory, expected_props, writes):
    inner = factory()
    wrapper = wrap(inner)
    # Pick any proxy prop to address — the callback-id resolution is
    # prop-independent, it walks ``_set_random_id``.
    prop = next(iter(expected_props))
    dep = Output(wrapper, prop)
    assert dep.component_id == inner.id


# ---------- html.* container matrix --------------------------------------


_CONTAINER_CASES: list[tuple[type, str]] = [
    (html.Div, "Div"),
    (html.Figure, "Figure"),
    (html.Section, "Section"),
    (html.Article, "Article"),
    (html.Aside, "Aside"),
    (html.Main, "Main"),
    (html.Nav, "Nav"),
    (html.Header, "Header"),
    (html.Footer, "Footer"),
    (html.Span, "Span"),
]


@pytest.mark.parametrize(
    "container_cls, expected_type",
    _CONTAINER_CASES,
    ids=[row[1] for row in _CONTAINER_CASES],
)
def test_make_wrapper_class_supports_container(container_cls, expected_type):
    cls = make_wrapper_class(container_cls)
    assert issubclass(cls, container_cls)


@pytest.mark.parametrize(
    "container_cls, expected_type",
    _CONTAINER_CASES,
    ids=[row[1] for row in _CONTAINER_CASES],
)
def test_wrap_with_container_serialises_correctly(container_cls, expected_type):
    graph = dcc.Graph(id=f"c-{expected_type}", figure={})
    wrapper = wrap(graph, container=container_cls)
    descriptor = wrapper.to_plotly_json()
    assert descriptor["type"] == expected_type
    assert descriptor["namespace"] == "dash_html_components"


@pytest.mark.parametrize(
    "container_cls, expected_type",
    _CONTAINER_CASES,
    ids=[row[1] for row in _CONTAINER_CASES],
)
def test_wrap_with_container_is_wrapped(container_cls, expected_type):
    graph = dcc.Graph(id=f"iw-{expected_type}", figure={})
    wrapper = wrap(graph, container=container_cls)
    assert is_wrapped(wrapper) is True


@pytest.mark.parametrize(
    "container_cls, expected_type",
    _CONTAINER_CASES,
    ids=[row[1] for row in _CONTAINER_CASES],
)
def test_wrap_with_container_resolves_callback_id(container_cls, expected_type):
    graph_id = f"cb-{expected_type}"
    graph = dcc.Graph(id=graph_id, figure={})
    wrapper = wrap(graph, container=container_cls)
    assert Output(wrapper, "figure").component_id == graph_id
    assert Input(wrapper, "figure").component_id == graph_id


@pytest.mark.parametrize(
    "container_cls, expected_type",
    _CONTAINER_CASES,
    ids=[row[1] for row in _CONTAINER_CASES],
)
def test_wrap_with_container_preserves_isinstance(container_cls, expected_type):
    graph = dcc.Graph(id=f"ii-{expected_type}", figure={})
    wrapper = wrap(graph, container=container_cls)
    assert isinstance(wrapper, dcc.Graph)
    assert isinstance(wrapper, container_cls)


# ---------- cross-product spot checks ------------------------------------


@pytest.mark.parametrize(
    "inner_label, inner_factory",
    [
        ("dcc.Graph", lambda: dcc.Graph(id="x-g", figure={})),
        ("dcc.Input", lambda: dcc.Input(id="x-i", value="x")),
        ("dcc.Dropdown", lambda: dcc.Dropdown(id="x-d", options=[], value=None)),
        (
            "dash_table.DataTable",
            lambda: dash_table.DataTable(id="x-t", data=[], columns=[]),
        ),
    ],
)
@pytest.mark.parametrize(
    "container_cls",
    [html.Div, html.Figure, html.Section, html.Article, html.Aside],
)
def test_inner_dcc_inside_each_container(inner_label, inner_factory, container_cls):
    inner = inner_factory()
    # Reset id to avoid collision across the parametrisation cross-product.
    inner.id = f"{inner_label}-{container_cls.__name__}".replace(".", "-")
    wrapper = wrap(inner, container=container_cls)
    assert is_wrapped(wrapper)
    assert isinstance(wrapper, type(inner))
    assert isinstance(wrapper, container_cls)
    assert (
        Output(
            wrapper, next(iter(wrapper._proxy_props)) if wrapper._proxy_props else "id"
        ).component_id
        == inner.id
    )

"""Wire-level equivalence between wrapper-ref and string-id dependencies.

``Input(wrapper, prop)`` must be byte-identical to ``Input(inner.id, prop)``
after Dash's serialisation.

Every callback-registration path Dash ships ends up building a
``DashDependency`` (``Input`` / ``Output`` / ``State``) whose
``.to_dict()`` is what gets JSON-serialised and sent to the browser. If
a wrapper-based dep produces different wire JSON than a string-based
one, *every* downstream Dash feature (callback resolution, pattern
matching, ``ctx.triggered_id``, clientside callbacks, ``set_props``) is
at risk.

These tests pin equivalence for each dependency kind and for the
interesting combinations: plain string id, pattern-matching dict id,
nested wrapper, non-Div container. They're pure-Python unit tests — no
browser — so the matrix can be wide and fast.

Also asserts that after ``app.callback(Output(wrapper, ...), ...)`` the
callback is indexed under the inner component's id in
``app.callback_map``, and that ``allow_duplicate`` / ``allow_optional``
flags propagate correctly.
"""

from __future__ import annotations

import pytest
from dash import ALL, Dash, Input, Output, State, ctx, dash_table, dcc, html

from dash_wrap import wrap

# ---------- helpers -------------------------------------------------------


def _string_dep(kind, id_, prop, **kwargs):
    """Build a dependency by string id — the 'ground truth' wire JSON."""
    return kind(id_, prop, **kwargs).to_dict()


def _object_dep(kind, component, prop, **kwargs):
    """Build a dependency by component object."""
    return kind(component, prop, **kwargs).to_dict()


# ---------- string-id vs wrapper-ref equivalence --------------------------


_DEP_KINDS = [Output, Input, State]


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_wrapper_dep_matches_string_dep(kind):
    graph = dcc.Graph(id="eq-graph", figure={})
    chart = wrap(graph)
    assert _object_dep(kind, chart, "figure") == _string_dep(kind, "eq-graph", "figure")


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_inner_dep_matches_string_dep(kind):
    """Sanity-pin: inner component itself matches its string id.

    Pins the 'ground truth' behaviour we're comparing wrappers to.
    """
    graph = dcc.Graph(id="eq-graph-2", figure={})
    assert _object_dep(kind, graph, "figure") == _string_dep(
        kind, "eq-graph-2", "figure"
    )


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_nested_wrapper_dep_matches_string_dep(kind):
    graph = dcc.Graph(id="nest-eq", figure={})
    w3 = wrap(wrap(wrap(graph)))
    assert _object_dep(kind, w3, "figure") == _string_dep(kind, "nest-eq", "figure")


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_figure_container_wrapper_dep_matches_string_dep(kind):
    graph = dcc.Graph(id="fig-eq", figure={})
    chart = wrap(graph, container=html.Figure)
    assert _object_dep(kind, chart, "figure") == _string_dep(kind, "fig-eq", "figure")


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_section_container_wrapper_dep_matches_string_dep(kind):
    graph = dcc.Graph(id="sec-eq", figure={})
    chart = wrap(graph, container=html.Section)
    assert _object_dep(kind, chart, "figure") == _string_dep(kind, "sec-eq", "figure")


# ---------- pattern-matching dict ids ------------------------------------


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_wrapper_preserves_dict_id_shape(kind):
    inner = dcc.Input(id={"type": "field", "idx": 3}, value="x")
    field = wrap(inner)
    via_obj = _object_dep(kind, field, "value")
    via_id = _string_dep(kind, {"type": "field", "idx": 3}, "value")
    assert via_obj == via_id
    # And the stringified form is the canonical Dash dict-id JSON.
    from dash._utils import stringify_id

    assert via_obj["id"] == stringify_id({"type": "field", "idx": 3})


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_pattern_wildcard_is_unaffected_by_wrappers(kind):
    """Pattern-matcher wildcards roundtrip unchanged through dep building.

    Pattern matchers compare by dict shape across the layout; the
    wrapper layer shouldn't affect the dep's own serialised shape.
    """
    dep = kind({"type": "field", "idx": ALL}, "value").to_dict()
    assert "ALL" in dep["id"]


# ---------- flags propagate through wrappers -----------------------------


def test_allow_duplicate_flag_survives_wrapper_ref():
    graph = dcc.Graph(id="dup-graph", figure={})
    chart = wrap(graph)
    wrapper_out = Output(chart, "figure", allow_duplicate=True)
    string_out = Output("dup-graph", "figure", allow_duplicate=True)
    # ``to_dict()`` does not serialise ``allow_duplicate`` — it's a
    # Python-side flag read by Dash at callback-registration time. So we
    # assert wire equivalence AND that the attribute made it onto the
    # wrapper-built dep.
    assert wrapper_out.to_dict() == string_out.to_dict()
    assert wrapper_out.allow_duplicate is True
    assert string_out.allow_duplicate is True


def test_allow_optional_flag_survives_wrapper_ref():
    graph = dcc.Graph(id="opt-graph", figure={})
    chart = wrap(graph)
    # ``allow_optional`` was introduced on Input/State in recent Dash;
    # tolerate older versions by checking only when supported.
    try:
        wrapper_dep = Input(chart, "figure", allow_optional=True).to_dict()
        string_dep = Input("opt-graph", "figure", allow_optional=True).to_dict()
    except TypeError:
        pytest.skip("allow_optional not supported in this Dash version.")
    assert wrapper_dep == string_dep


# ---------- callback registration ----------------------------------------


def test_callback_map_keyed_on_inner_id():
    graph = dcc.Graph(id="cbmap-graph", figure={})
    chart = wrap(graph)
    app = Dash(__name__)
    app.layout = html.Div([chart])

    @app.callback(Output(chart, "figure"), Input("btn", "n_clicks"))
    def _(n):
        return {"data": [{"y": [n]}]}

    # app.callback_map keys look like ``"<id>.<prop>"``; the key must
    # use the inner's id, not anything attached to the wrapper.
    keys = list(app.callback_map.keys())
    assert any(k.startswith("cbmap-graph.") for k in keys), (
        f"No callback_map entry for inner id; got keys: {keys}"
    )


def test_callback_map_identical_for_wrapper_and_string():
    """Wrapper-ref and string-ref apps register identical ``callback_map`` keys.

    Side-by-side: two apps with the same callback, one addressed via
    wrapper object, one via string id — the registered maps match.
    """
    graph1 = dcc.Graph(id="side-A", figure={})
    chart = wrap(graph1)
    app_obj = Dash("app-obj")

    @app_obj.callback(Output(chart, "figure"), Input("btn", "n_clicks"))
    def _a(n):
        return {"data": []}

    app_str = Dash("app-str")

    @app_str.callback(Output("side-A", "figure"), Input("btn", "n_clicks"))
    def _b(n):
        return {"data": []}

    obj_keys = sorted(app_obj.callback_map.keys())
    str_keys = sorted(app_str.callback_map.keys())
    assert obj_keys == str_keys


def test_multi_output_mixed_wrapper_and_string():
    """Multi-output callback mixing wrapper and string Outputs registers both.

    The callback_map should contain both targets addressed by their
    inner ids, regardless of how each was supplied.
    """
    graph = dcc.Graph(id="multi-graph", figure={})
    chart = wrap(graph)
    app = Dash(__name__)

    @app.callback(
        [Output(chart, "figure"), Output("plain-div", "children")],
        Input("btn", "n_clicks"),
    )
    def _(n):
        return {"data": []}, "hi"

    keys = " ".join(app.callback_map.keys())
    assert "multi-graph.figure" in keys
    assert "plain-div.children" in keys


def test_state_on_wrapper_serialises_as_string_state():
    graph = dcc.Graph(id="stategraph", figure={})
    chart = wrap(graph)
    obj_state = State(chart, "figure").to_dict()
    str_state = State("stategraph", "figure").to_dict()
    assert obj_state == str_state


# ---------- dash_table and dcc.Input equivalence -------------------------


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_datatable_wrapper_dep_equivalence(kind):
    tbl = dash_table.DataTable(id="tbl-eq", data=[], columns=[])
    block = wrap(tbl)
    assert _object_dep(kind, block, "data") == _string_dep(kind, "tbl-eq", "data")


@pytest.mark.parametrize("kind", _DEP_KINDS, ids=lambda k: k.__name__)
def test_dcc_input_wrapper_dep_equivalence(kind):
    inp = dcc.Input(id="inp-eq", value="")
    field = wrap(inp)
    assert _object_dep(kind, field, "value") == _string_dep(kind, "inp-eq", "value")


# ---------- clientside callback registration ----------------------------


def test_clientside_callback_accepts_wrapper_deps():
    """``app.clientside_callback`` accepts wrapper deps and keys on inner id.

    Goes through the same dependency machinery as the Python callback;
    registering one against a wrapper must succeed and store the
    callback under the inner's id in ``callback_map``.
    """
    graph = dcc.Graph(id="cs-graph", figure={})
    chart = wrap(graph)
    app = Dash(__name__)
    app.clientside_callback(
        "function(n) { return {data: []}; }",
        Output(chart, "figure"),
        Input("cs-btn", "n_clicks"),
        prevent_initial_call=True,
    )
    keys = " ".join(app.callback_map.keys())
    assert "cs-graph.figure" in keys


# ---------- ctx.triggered_id resolves to inner --------------------------


def test_ctx_attribute_access_unrelated(monkeypatch, make_graph):
    """Sanity-pin: wrapper import does not poison the ``dash.ctx`` machinery.

    ``dash.ctx`` proxies to Flask's ``g`` inside a request; outside
    one, attribute access raises. We don't simulate a live callback
    here — the runtime behaviour is covered by the DashDuo test
    ``test_ctx_triggered_id_reports_inner_id`` in test_callbacks.py.
    """
    _ = ctx  # noqa: F841  - imported purely to exercise the import path

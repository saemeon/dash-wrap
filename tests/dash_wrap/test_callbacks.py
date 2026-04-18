"""Integration tests — a real browser driving a live Dash app via DashDuo.

Each test builds a minimal app, launches Chrome via Selenium, triggers a
user action, and asserts the resulting DOM / state. These exercise the
full round-trip: Python layout → serialized JSON → browser render →
user event → callback → Python update → DOM diff.

If Chrome / chromedriver aren't available the entire module is skipped —
the CI matrix runs these on ``ubuntu-latest`` where Chrome is
pre-installed.
"""

from __future__ import annotations

import json

import pytest

# ``dash.testing`` imports the Selenium-based harness that needs both a
# working Chrome binary and chromedriver. Skip the module if either is
# unavailable so the rest of the suite runs.
pytest.importorskip("selenium")
pytest.importorskip("dash.testing")


def _ensure_matching_chromedriver() -> None:
    """Best-effort: install a chromedriver that matches the local Chrome.

    If ``chromedriver-autoinstaller`` is available (optional dev dep),
    fetch a driver that matches the current Chrome version and prepend
    its directory to ``PATH``. No-op when the package isn't installed —
    CI uses ``browser-actions/setup-chrome`` which keeps versions in
    sync already.
    """
    import os

    try:
        import chromedriver_autoinstaller
    except ImportError:
        return
    try:
        path = chromedriver_autoinstaller.install()
    except Exception:
        return
    if path:
        os.environ["PATH"] = (
            f"{os.path.dirname(path)}{os.pathsep}{os.environ.get('PATH', '')}"
        )


def _chrome_available() -> bool:
    """Probe whether Selenium can actually launch a Chrome session."""
    _ensure_matching_chromedriver()
    try:
        from selenium.webdriver import Chrome, ChromeOptions
    except Exception:
        return False
    opts = ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-gpu")
    try:
        driver = Chrome(options=opts)
    except Exception:
        return False
    driver.quit()
    return True


pytestmark = pytest.mark.skipif(
    not _chrome_available(),
    reason="Chrome / chromedriver not available in this environment.",
)

from dash import Dash, Input, Output, State, dcc, html  # noqa: E402
from dash.development.base_component import Component  # noqa: E402

from dash_wrap import make_wrapper_class, wrap  # noqa: E402


def _count_elements_with_id(dash_duo) -> int:
    script = (
        "return Array.from(document.querySelectorAll('[id]'))"
        ".filter(el => el.id && el.id !== 'react-entry-point' && "
        "el.id !== '_dash-app-content' && el.id !== '_dash-global-error-container').length;"
    )
    return dash_duo.driver.execute_script(script)


def test_output_figure_updates_inner(dash_duo):
    graph = dcc.Graph(id="g", figure={"data": []})
    chart = wrap(graph)

    app = Dash(__name__)
    app.layout = html.Div(
        [
            html.Button("update", id="btn"),
            chart,
        ]
    )

    @app.callback(
        Output(chart, "figure"),
        Input("btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _update(n):
        return {"data": [{"type": "bar", "x": [1, 2, 3], "y": [n, n, n]}]}

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#g")
    dash_duo.find_element("#btn").click()
    dash_duo.wait_for_element("#g .plotly .bars path.point, #g .bars path")
    # No client-side errors means the callback resolved and updated the
    # inner graph via the wrapper's Output dependency.
    assert dash_duo.get_logs() in (None, []), dash_duo.get_logs()


def test_state_on_wrapper_reads_inner(dash_duo):
    graph = dcc.Graph(id="g2", figure={"data": [{"y": [7]}]})
    chart = wrap(graph)

    app = Dash(__name__)
    app.layout = html.Div(
        [
            html.Button("read", id="btn"),
            chart,
            html.Div(id="out"),
        ]
    )

    @app.callback(
        Output("out", "children"),
        Input("btn", "n_clicks"),
        State(chart, "figure"),
        prevent_initial_call=True,
    )
    def _read(_n, fig):
        return json.dumps(fig)

    dash_duo.start_server(app)
    dash_duo.wait_for_element("#g2")
    dash_duo.find_element("#btn").click()
    dash_duo.wait_for_text_to_equal("#out", json.dumps({"data": [{"y": [7]}]}))


def test_wrap_preserves_single_id_in_dom(dash_duo):
    graph = dcc.Graph(id="only-id", figure={"data": []})
    chart = wrap(
        graph,
        children=[html.H3("heading"), graph, html.Small("source")],
    )
    app = Dash(__name__)
    app.layout = html.Div([chart])
    dash_duo.start_server(app)
    dash_duo.wait_for_element("#only-id")
    # Only one element should carry the id (the inner plotly div); the
    # outer wrapper has no id attribute.
    count = dash_duo.driver.execute_script(
        "return document.querySelectorAll('[id=\"only-id\"]').length;"
    )
    assert count == 1


def test_pattern_matching_id_inner_ok(dash_duo):
    graph = dcc.Graph(id={"type": "g", "idx": 1}, figure={"data": []})
    chart = wrap(graph)
    app = Dash(__name__, suppress_callback_exceptions=True)
    app.layout = html.Div([html.Button("b", id="btn"), chart])

    @app.callback(
        Output(chart, "figure"),
        Input("btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _update(_n):
        return {"data": [{"y": [1, 2]}]}

    dash_duo.start_server(app)
    dash_duo.find_element("#btn").click()
    # If callback resolution failed, Dash would log a client-side error.
    dash_duo.wait_for_no_elements(".dash-fe-error-container")


# ---------- (N) nested callback resolution -------------------------------


def test_nested_output_updates_innermost(dash_duo):
    graph = dcc.Graph(id="deep", figure={"data": []})
    inner = wrap(graph)
    outer = wrap(inner)

    app = Dash(__name__)
    app.layout = html.Div([html.Button("b", id="btn"), outer])

    @app.callback(
        Output(outer, "figure"),
        Input("btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _update(_n):
        return {"data": [{"y": [42]}]}

    dash_duo.start_server(app)
    dash_duo.find_element("#btn").click()
    dash_duo.wait_for_no_elements(".dash-fe-error-container")


def test_mixed_container_nest_callback_resolves(dash_duo):
    graph = dcc.Graph(id="mixed", figure={"data": []})
    figure_wrapper_cls = make_wrapper_class(html.Figure)
    section_wrapper_cls = make_wrapper_class(html.Section)
    inner: Component = figure_wrapper_cls(graph, proxy_props=["figure"])
    outer: Component = section_wrapper_cls(inner, proxy_props=["figure"])

    app = Dash(__name__)
    app.layout = html.Div([html.Button("b", id="btn"), outer])

    @app.callback(
        Output(outer, "figure"),
        Input("btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _update(_n):
        return {"data": [{"y": [1]}]}

    dash_duo.start_server(app)
    dash_duo.find_element("#btn").click()
    dash_duo.wait_for_no_elements(".dash-fe-error-container")


def test_figure_wrapper_with_figcaption_sibling(dash_duo):
    graph = dcc.Graph(id="cap", figure={"data": []})
    caption = html.Figcaption("ABS 2024", id="cap-text")
    chart = wrap(graph, container=html.Figure, children=[graph, caption])

    app = Dash(__name__)
    app.layout = html.Div([html.Button("b", id="btn"), chart])

    @app.callback(
        Output("cap-text", "children"),
        Input("btn", "n_clicks"),
        prevent_initial_call=True,
    )
    def _update(_n):
        return "ABS 2024 (updated)"

    dash_duo.start_server(app)
    dash_duo.find_element("#btn").click()
    dash_duo.wait_for_text_to_equal("#cap-text", "ABS 2024 (updated)")

"""Static-type contract for the public API.

These tests are type-checker-only: they assert what ``ty`` / ``pyright``
/ ``mypy`` should see when they look at ``wrap()``, ``ComponentWrapper``,
and friends. Pytest only confirms the file imports cleanly; the real
verification is CI running ``uv run ty check tests/``.

When adding cases, follow the existing pattern: build the value once,
then use ``reveal_type`` to pin the expected declared type, with a
comment that duplicates the expectation so humans can spot regressions
without a type checker.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

from dash import dash_table, dcc, html

from dash_wrap import ComponentWrapper, make_wrapper_class, wrap

if TYPE_CHECKING:
    # Static-only section: these calls exercise the declared types.
    # ``reveal_type`` is provided by type checkers; no runtime import.

    graph_src = dcc.Graph(id="x")
    chart = wrap(graph_src)
    reveal_type(chart)  # expected: dcc.Graph  # noqa: F821

    table = wrap(dash_table.DataTable(id="t"))
    reveal_type(table)  # expected: dash_table.DataTable  # noqa: F821

    cw = ComponentWrapper(graph_src, proxy_props=["figure"])
    reveal_type(cw)  # expected: ComponentWrapper[dcc.Graph]  # noqa: F821

    # chart is typed as dcc.Graph, so .__wrapped__ should also be dcc.Graph
    reveal_type(chart.__wrapped__)  # expected: dcc.Graph  # noqa: F821

    # The declared type of ``chart`` is dcc.Graph, which has no
    # ``children`` prop, so this line should be flagged by a strict
    # type checker. Runtime-wise it's legal because of the __class__
    # spoof; users who need the outer div's children should opt in via
    # an explicit cast:
    outer_children = cast(html.Div, chart).children

    fig_cls = make_wrapper_class(html.Figure)
    fig_wrapper = fig_cls(graph_src, proxy_props=["figure"])
    reveal_type(fig_wrapper)  # expected: FigureWrapper-like  # noqa: F821


def test_typing_module_imports():
    """Runtime no-op that guarantees the file is syntactically valid."""
    assert wrap is not None
    assert ComponentWrapper is not None
    assert make_wrapper_class is not None

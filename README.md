[![PyPI](https://img.shields.io/pypi/v/dash-wrap)](https://pypi.org/project/dash-wrap/)
[![Python](https://img.shields.io/pypi/pyversions/dash-wrap)](https://pypi.org/project/dash-wrap/)
[![License](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Dash](https://img.shields.io/badge/Dash-008DE4?logo=plotly&logoColor=white)](https://dash.plotly.com/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

# dash-wrap

Callback-identity-preserving component wrappers for Plotly Dash. Wrap
any Dash component in an `html.Div` (or other container) with arbitrary
sibling components — captions, headings, toolbars — while keeping the
wrapper a drop-in replacement for the inner component everywhere Dash
inspects it.

- `Output(chart, "figure")` updates the inner graph
- `chart.figure = fig` writes through to the inner
- `isinstance(chart, dcc.Graph)` is still `True`

Think of it as _AIO, but callback-transparent_.

## Installation

```bash
pip install dash-wrap
```

## Usage

```python
from dash import Dash, Input, Output, dcc, html
from dash_wrap import wrap

app = Dash(__name__)

graph = dcc.Graph(id="revenue", figure=make_fig())
chart = wrap(graph, children=[graph, html.Small("Source: ABS")])

app.layout = html.Div([
    html.Button("Refresh", id="btn"),
    chart,
])


@app.callback(Output(chart, "figure"), Input("btn", "n_clicks"))
def update(n):
    return make_fig(n)
```

### Semantic `<figure>` + `<figcaption>`

```python
chart = wrap(
    graph,
    container=html.Figure,
    children=[graph, html.Figcaption("Revenue by year, 2018–2024")],
)
```

### Stable named wrapper (subclassing)

```python
from dash_wrap import ComponentWrapper

class ChartCard(ComponentWrapper[dcc.Graph]):
    def __init__(self, graph: dcc.Graph, title: str) -> None:
        super().__init__(
            graph,
            proxy_props=["figure", "config"],
            children=[html.H3(title), graph],
            className="card",
        )
```

## Public API

| Name | Purpose |
| --- | --- |
| `wrap` | Primary factory — auto proxy_props from registry, returns typed as inner. |
| `ComponentWrapper` | `html.Div`-based wrapper class; subclass for stable named wrappers. |
| `is_wrapped` | Check whether an object is a dash-wrap wrapper specifically. |
| `register_proxy_defaults` | Register default proxy props for custom component types. |
| `make_wrapper_class` | Generate `Generic[T]`-parameterised wrapper classes for non-`Div` containers. |

## How it works

Three small pieces:

1. `_set_random_id` override returns the innermost component's id and
   doesn't set one on the wrapper — callbacks resolve to the inner,
   the outer div has no HTML id, no `DuplicateIdError`.
2. `__class__` property spoofs the inner's class for `isinstance`
   while `type()` still sees the container — Dash serialises the outer
   as its real type.
3. `__getattr__` / `__setattr__` proxy selected props (`figure`,
   `value`, etc.) through to the inner.

See the [full docs](https://saemeon.github.io/dash-wrap/) for recipes,
nested-wrapper semantics, and caveats.

## License

MIT

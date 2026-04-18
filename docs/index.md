# dash-wrap

Callback-identity-preserving component wrappers for Plotly Dash. Wrap any
Dash component in an `html.Div` (or other container) with arbitrary
sibling components — captions, headings, toolbars — while keeping the
wrapper a drop-in replacement for the inner component everywhere Dash
inspects it.

- `Output(chart, "figure")` updates the inner graph
- `chart.figure = fig` writes through to the inner
- `isinstance(chart, dcc.Graph)` is still `True`

Think of it as _AIO, but callback-transparent_.

## Install

```bash
pip install dash-wrap
```

## 30-second example

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

`chart` looks like a `dcc.Graph` to Dash's callback system, to
`isinstance`, and to your type checker. The rendered DOM is a
`<div>` wrapping a plotly graph and a caption.

## Recipes

### Card-styled graph

```python
chart = wrap(
    graph,
    children=[html.H3("Revenue"), graph, html.Small("Source: ABS")],
    className="card",
    style={"padding": "16px", "borderRadius": "8px"},
)
```

### Semantic HTML: `<figure>` + `<figcaption>`

```python
chart = wrap(
    graph,
    container=html.Figure,
    children=[graph, html.Figcaption("Revenue by year, 2018–2024")],
)
```

### Input + inline error message

```python
from dash import dcc
input_ = dcc.Input(id="email", type="email")
form_field = wrap(
    input_,
    children=[input_, html.Span(id="email-err", className="error")],
)
```

### DataTable + toolbar

```python
from dash import dash_table
table = dash_table.DataTable(id="orders", data=rows, columns=cols)
block = wrap(
    table,
    children=[html.Div([html.Button("Export"), html.Button("Refresh")]), table],
    className="table-block",
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

## How it works

Three pieces, all small:

1. **`_set_random_id` override** — Dash calls this on a component
   instance the first time it appears in an `Output` / `Input` / `State`.
   Our override returns the inner component's id (walking a chain for
   nested wrappers) and does not set an id on the wrapper itself. Result:
   callbacks written against the wrapper resolve to the inner, and the
   outer `<div>` emits no `id` attribute — no `DuplicateIdError`.
2. **`__class__` property** — makes `isinstance(wrapper, type(inner))`
   return `True`. `type(wrapper)` still reports the real class, so
   Dash's `_type` / `_namespace` lookups keep reporting the container
   (`Div`), and serialization is unaffected. Borrowed conceptually from
   `wrapt.ObjectProxy`.
3. **`__getattr__` / `__setattr__` with a `proxy_props` allowlist** —
   selected attribute names read and write through to `inner`.

Nesting works at arbitrary depth: `wrap(wrap(wrap(graph)))` — each level
adds its own container and siblings; `_set_random_id` walks the chain
to the innermost component.

## Caveats

- **`_set_random_id` is undocumented Dash API.** The regression-pin
  test (`tests/test_dash_internals.py`) asserts the hook exists and is
  invoked on every supported Dash version; CI will flag breakage early.
- **`type(wrapper)` is still `ComponentWrapper`.** Checks using
  `type(x) is dcc.Graph` will fail; use `isinstance` or `is_wrapped`.
- **Multi-wrapping a single inner is not supported.** Dash requires one
  parent per component. Use two wrappers side by side with separate
  inner components.
- **Subclass API stability.** The `wrap()` function is the stable
  contract; subclassing `ComponentWrapper` is supported but may evolve
  in minor versions. Pin your dash-wrap dep if you subclass extensively.
- **Declared type-lie on wrapper.** `wrap(graph)` is declared as
  `dcc.Graph` for IDE ergonomics, but at runtime the object has the
  outer div's `children` prop too. Accessing `wrapper.children` works;
  static type checkers flag it. Cast explicitly (`cast(html.Div, chart)`)
  when you need the outer-div props.

## API

### wrap

::: dash_wrap.wrap

### ComponentWrapper

::: dash_wrap.ComponentWrapper

### is_wrapped

::: dash_wrap.is_wrapped

### register_proxy_defaults

::: dash_wrap.register_proxy_defaults

### make_wrapper_class

::: dash_wrap.make_wrapper_class

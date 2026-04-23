# dash-wrap — design plan and maintenance notes

**Status**: shipped. `v0.0.1` scaffold built and tested in the
`brand-toolkit` monorepo; ready for extraction to its own GitHub repo
and PyPI release.

- 262 tests passing (249 unit + 13 DashDuo integration), 100%
  line coverage on `src/`.
- ruff clean (including `D` pydocstyle), ruff format clean, ty clean.
- CI workflows written for `test`, `lint`, `publish`, `docs`.
- [tests/dash_wrap/conftest.py](tests/dash_wrap/conftest.py) defines
  `pytest_setup_options` to configure Chrome (`--headless=new`,
  `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`) —
  required for DashDuo to launch on GitHub's ubuntu runners and in
  most container environments. Without these, Chrome exits
  immediately with `SessionNotCreatedException`. Load-bearing — do
  not remove.

This doc serves two audiences:

- A **returning maintainer** picking up the package months later:
  start with "File tree" and "Implementation notes" below — they
  describe everything load-bearing about the current code.
- **A fresh Claude Code session** extending or refactoring: read
  "Purpose", "Public API", "Implementation sketch", and "Implementation
  notes" to understand invariants before touching code.

## Handoff

What the author (Simon) still owns, after this doc was produced:

1. `gh repo create saemeon/dash-wrap --public --source=dash-wrap`.
2. Configure PyPI trusted publisher → workflow `publish.yml`.
3. Tag `v0.0.1`, create GitHub release — `publish.yml` publishes.
4. GitHub Pages: branch `documentation` (created on first `docs.yml` run).
5. Later: plan-milestone 7 — wire into `dash-capture` via
   `capture_graph(..., wrap=True)` and collapse `SNBGraph` in snbplt.

**Load-bearing Dash internals**: depends on
`Component._set_random_id()` and `Component._prop_names` — both
`_`-prefixed, not part of Dash's documented public API.
[tests/dash_wrap/test_dash_internals.py](tests/dash_wrap/test_dash_internals.py)
flags the day Dash removes or renames these. Don't silently work
around failures there; investigate.

## File tree

```text
dash-wrap/
├── CLAUDE.md                       # this file
├── LICENSE                         # MIT
├── README.md                       # pitch + usage + public API table
├── CHANGELOG.md                    # keep-a-changelog format
├── pyproject.toml                  # config, ruff (incl. D), ty, pytest
├── uv.lock
├── mkdocs.yml                      # material + mkdocstrings + mike
├── .gitignore
├── .pre-commit-config.yaml         # prek: ruff + ty
├── .github/workflows/
│   ├── test.yml                    # Python 3.10–3.13 × Dash 2.9/2.14/2.17/3.0 matrix, Chrome via setup-chrome
│   ├── lint.yml                    # prek + ty jobs
│   ├── publish.yml                 # PyPI via OIDC on release publish
│   └── docs.yml                    # mike deploy on main + version tags
├── src/dash_wrap/
│   ├── __init__.py                 # re-exports 5 public names
│   ├── _wrapper.py                 # _WrapperMixin, ComponentWrapper, _contains, _unpickle_wrapper
│   ├── _factory.py                 # make_wrapper_class + class cache
│   ├── _wrap.py                    # wrap, is_wrapped
│   ├── _defaults.py                # default proxy-props registry + register_proxy_defaults
│   ├── _version.py                 # setuptools-scm-generated (gitignored)
│   └── py.typed                    # PEP 561 marker
├── tests/dash_wrap/
│   ├── conftest.py                 # make_graph + app fixtures
│   ├── test_wrapper.py             # 33 unit tests — construction, proxy, isinstance, __wrapped__
│   ├── test_wrap_factory.py        # 19 unit tests — wrap(), registry, is_wrapped
│   ├── test_factory.py             # 9 unit tests — make_wrapper_class + cache + MRO
│   ├── test_subclassing.py         # 6 unit tests — user subclassing (tier-1 + tier-2)
│   ├── test_serialization.py       # 7 unit tests — to_plotly_json, deepcopy, pickle
│   ├── test_broad_coverage.py      # 124 breadth-matrix tests — every registered inner × every html.* container
│   ├── test_dependency_equivalence.py  # 35 unit tests — wrapper-ref vs string-id dep wire equivalence
│   ├── test_dash_internals.py      # 9 regression-pin tests on _set_random_id / _prop_names
│   ├── test_typing.py              # TYPE_CHECKING block + runtime stub
│   └── test_callbacks.py           # 13 DashDuo integration tests (user events, ctx, pattern, clientside, chained)
└── docs/
    └── index.md                    # single-page site — pitch, recipes, how-it-works, API
```

Session-scaffolding files that are safe to delete post-extraction:
`PROGRESS.md`, `PROMPT.md`, `QUESTIONS.md`. Their load-bearing content
is absorbed into this doc.

## Purpose

A Python micropackage that provides callback-identity-preserving component wrappers for Plotly Dash. The elevator pitch: *AIO but callback-transparent.* Wrap any Dash component in an `html.Div` (or other container) with arbitrary sibling components while preserving:

- `Output(wrapper, prop)` — callback validator resolves the wrapper's id to the inner component.
- `wrapper.figure = new_fig` — Python-side attribute access on selected props.
- `isinstance(wrapper, type(inner))` — type identity via `__class__` override.

**Scope statement** (from Q6): drop-in replacements that extend single-level components — about *changing styling / appearance* of a normal component, not *combining* multiple components. A wrapper always has exactly one inner addressable component.

Research confirmed (via broad PyPI/GitHub/forum search) that this semantic slot is empty. Closest prior art is Dash's All-in-One (AIO) pattern, which explicitly trades away identity transparency.

## Non-goals (explicit)

- Not a layout framework (no grid / flex helpers, no theming).
- Not a component library (no pre-built cards, tooltips, etc.).
- Not a Dash extension (no callback machinery, no middleware).
- Not React / JS — pure Python.
- Not multi-inner or "compound component" support. Use two wrappers side by side instead.

## Dependencies

- Python 3.10+
- `dash >= 2.9` (stable pattern-matching callbacks)

**Forward-looking constraints for future work:**

- **Do not add a dependency on `wrapt`.** We borrow conceptual
  patterns (`__class__` spoof, `__wrapped__` convention) but our
  split-identity need (rendering sees `html.Div`, callbacks see
  inner) rules out using `wrapt.ObjectProxy` directly. A hard dep
  would be user-visible weight with no payoff.
- **No `TODO` / `FIXME` / placeholder comments in shipped code.** If
  a design decision is unresolved, log it in `CHANGELOG.md` under a
  `## Unreleased` section or in a GitHub issue, not in a comment
  that future readers will dismiss.
- **Don't expand the public API without a design note here.** The
  five-name surface (`wrap`, `ComponentWrapper`, `is_wrapped`,
  `register_proxy_defaults`, `make_wrapper_class`) is deliberately
  small. Additions should come with a corresponding "Design
  rationale" bullet below.

## Public API — five names

```python
from dash_wrap import (
    wrap,                     # primary factory
    ComponentWrapper,         # Generic[T], html.Div-based, subclassing target
    is_wrapped,               # isinstance(obj, ComponentWrapper)
    register_proxy_defaults,  # extensibility for inner-component types
    make_wrapper_class,       # non-Div subclassing (tier-2)
)
```

### `wrap()` — primary, documented first (95% of users stop here)

```python
def wrap(
    inner: T,
    *,
    proxy_props: Iterable[str] | None = None,
    children: Any = None,
    container: type[Component] = html.Div,
    **div_kwargs: Any,
) -> T: ...
```

- **Type-level**: `TypeVar("T", bound=Component)` — returns the inner's type. Pylance sees `wrap(graph)` as `dcc.Graph`. Runtime agrees via `__class__` spoofing.
- `proxy_props=None` → auto-detect from the registry keyed by `type(inner)`.
- `children=None` → auto-include `inner` as `[inner]`.
- `container=html.Div` → override for semantic tags (`html.Figure`, `html.Section`, `html.Article`, `html.Aside`). Internally uses a cached generated subclass.
- `**div_kwargs` → forwarded to the outer container's props (`style`, `className`, etc.).

### `ComponentWrapper` — public class for subclassing (tier-1)

```python
class ComponentWrapper(html.Div, Generic[T]):
    __wrapped__: T
    _proxy_props: frozenset[str]

    def __init__(
        self,
        inner: T,
        *,
        proxy_props: Iterable[str],
        children: Any = None,
        **div_kwargs: Any,
    ) -> None: ...
```

Users subclass for stable-named custom wrappers:

```python
class ChartCard(ComponentWrapper[dcc.Graph]):
    def __init__(self, graph: dcc.Graph, title: str) -> None:
        super().__init__(
            graph,
            proxy_props=["figure", "config"],
            children=[html.H3(title), graph],
            className="card",
        )
```

### `is_wrapped(obj)` — specifically-ours check

```python
def is_wrapped(obj: Any) -> bool:
    """True if obj is a dash-wrap wrapper specifically."""
    return isinstance(obj, ComponentWrapper)
```

Checks by class, not by `__wrapped__` attribute, so it distinguishes us from `wrapt.ObjectProxy` / `functools.wraps` / other `__wrapped__`-using tools.

### `register_proxy_defaults(component_type, proxy_props)` — extensibility

```python
def register_proxy_defaults(
    component_type: type[Component],
    proxy_props: Iterable[str],
) -> None: ...
```

Lets ecosystem libraries register defaults for their own types. Ships with defaults for:

| Component | Default proxy props |
|---|---|
| `dcc.Graph` | `figure`, `config`, `responsive` |
| `dash_table.DataTable` | `data`, `columns`, `page_current`, `sort_by`, `filter_query` |
| `dcc.Input` | `value`, `disabled` |
| `dcc.Dropdown` | `value`, `options`, `disabled` |
| `dcc.Textarea` | `value`, `disabled` |
| `dcc.Slider` / `RangeSlider` | `value`, `min`, `max`, `marks`, `disabled` |
| `dcc.DatePickerSingle` / `Range` | `date`, `start_date`, `end_date`, `disabled` |

### `make_wrapper_class(container_cls)` — non-Div subclassing (tier-2)

```python
FigureWrapper = make_wrapper_class(html.Figure)

class CaptionedChart(FigureWrapper[dcc.Graph]):
    def __init__(self, graph: dcc.Graph, caption: str) -> None:
        super().__init__(
            graph,
            proxy_props=["figure", "config"],
            children=[graph, html.Figcaption(caption)],
        )
```

Generates (and caches) a `Generic[T]` subclass of the given container. Tier-3 (private `WrapperMixin` for diamond inheritance) is internal only in v1.

## Usage examples

```python
from dash_wrap import wrap

# 1. Minimal — wrap a graph with a caption sibling
graph = dcc.Graph(id="revenue", figure=fig)
chart = wrap(graph, children=[graph, html.Small("Source: ABS")])

# 2. Explicit proxy_props, styling on the outer div
chart = wrap(
    graph,
    proxy_props=["figure", "config", "responsive"],
    children=[html.H3("Revenue"), graph, html.Small("Source: ABS")],
    className="card",
)

# 3. Semantic HTML: <figure> with <figcaption>
chart = wrap(
    graph,
    container=html.Figure,
    children=[graph, html.Figcaption("Revenue by year, 2018–2024")],
)

# 4. Drop-in callback usage — identical to dcc.Graph
@app.callback(Output(chart, "figure"), Input("year", "value"))
def update(year):
    return make_fig(year)

# 5. Python-side access (typed by Pylance as dcc.Graph)
chart.figure = new_fig            # proxies to inner graph
isinstance(chart, dcc.Graph)      # True
isinstance(chart, html.Div)       # True
chart.__wrapped__                 # the inner dcc.Graph
```

## Implementation sketch

### Internal factoring: `_WrapperMixin`

The adapter logic (`_set_random_id`, `__class__` property, `__getattr__`, `__setattr__`, construction validation) is factored into a private `_WrapperMixin` so both `ComponentWrapper` (the public `html.Div`-based class) and the dynamically generated classes from `make_wrapper_class(other_container)` share a single implementation without duplication. Both compose the mixin with the appropriate Dash container:

```python
class _WrapperMixin:
    # all the adapter methods + __init__ validation live here

class ComponentWrapper(_WrapperMixin, html.Div, Generic[T]):
    pass

# inside make_wrapper_class(container_cls):
class _Wrapper(_WrapperMixin, container_cls, Generic[T]):
    pass
```

`_WrapperMixin` stays private in v1. Tier-3 (exposing it publicly for diamond-inheritance cases) is deferred to v0.2+.

### Sketch

```python
# src/dash_wrap/_wrapper.py
from __future__ import annotations
from typing import Any, Generic, Iterable, TypeVar
from dash import html
from dash.development.base_component import Component

T = TypeVar("T", bound=Component)


class ComponentWrapper(html.Div, Generic[T]):
    """html.Div subclass that proxies selected props to an inner Dash
    component and adapts its identity to Dash's callback registry."""

    def __init__(
        self,
        inner: T,
        *,
        proxy_props: Iterable[str],
        children: Any = None,
        **div_kwargs: Any,
    ) -> None:
        if not hasattr(inner, "id") or inner.id is None:
            raise ValueError(
                "ComponentWrapper requires an inner component with an id."
            )
        proxy_set = frozenset(proxy_props)
        available = set(getattr(inner, "_prop_names", ()))
        if available:
            unknown = proxy_set - available
            if unknown:
                raise ValueError(
                    f"proxy_props {sorted(unknown)} not on "
                    f"{type(inner).__name__}; available: {sorted(available)}"
                )

        object.__setattr__(self, "__wrapped__", inner)
        object.__setattr__(self, "_proxy_props", proxy_set)

        if children is None:
            children = [inner]
        elif not _contains(children, inner):
            raise ValueError(
                "children must include inner (pass None to auto-include)."
            )

        super().__init__(children=children, **div_kwargs)

    def _set_random_id(self) -> str:
        # Dash's id-generation hook. Walk the __wrapped__ chain down to the
        # innermost concrete component so nested wrappers resolve correctly.
        # Return value is what Dash uses for callback resolution; not
        # persisted onto self → no HTML id → no DuplicateIdError.
        node = self.__wrapped__
        while is_wrapped(node):
            node = node.__wrapped__
        return node.id

    @property
    def __class__(self):  # type: ignore[override]
        # isinstance(wrapper, type(inner)) → True. Uses inner's __class__
        # (not type()) so the property recurses through nested wrappers:
        # each level's __class__ invokes the next level's property until
        # it bottoms out at a non-wrapper whose __class__ is its real type.
        # Does NOT affect Dash rendering (which reads _type/_namespace from
        # the defining class, inherited from html.Div). Adapted from
        # wrapt.ObjectProxy.
        return self.__wrapped__.__class__

    def __getattr__(self, name: str) -> Any:
        if name in self._proxy_props:
            return getattr(self.__wrapped__, name)
        raise AttributeError(
            f"{type(self).__name__!r} has no attribute {name!r}"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        if name in self.__dict__.get("_proxy_props", ()):
            setattr(self.__wrapped__, name, value)
        else:
            super().__setattr__(name, value)


def _contains(tree: Any, target: Component) -> bool:
    if tree is target:
        return True
    if isinstance(tree, Component):
        return _contains(getattr(tree, "children", None), target)
    if isinstance(tree, (list, tuple)):
        return any(_contains(c, target) for c in tree)
    return False


# src/dash_wrap/_factory.py  (sketch)
_CLASS_CACHE: dict[type[Component], type] = {html.Div: ComponentWrapper}

def make_wrapper_class(container_cls: type[Component]) -> type:
    if container_cls in _CLASS_CACHE:
        return _CLASS_CACHE[container_cls]
    # internal WrapperMixin factored out of ComponentWrapper
    class _Wrapper(_WrapperMixin, container_cls, Generic[T]):
        ...
    _Wrapper.__name__ = f"{container_cls.__name__}Wrapper"
    _Wrapper.__qualname__ = _Wrapper.__name__
    _CLASS_CACHE[container_cls] = _Wrapper
    return _Wrapper


# src/dash_wrap/_wrap.py  (sketch)
_DEFAULTS: dict[type[Component], tuple[str, ...]] = { ... }

def register_proxy_defaults(
    component_type: type[Component],
    proxy_props: Iterable[str],
) -> None:
    _DEFAULTS[component_type] = tuple(proxy_props)

def wrap(
    inner: T,
    *,
    proxy_props: Iterable[str] | None = None,
    children: Any = None,
    container: type[Component] = html.Div,
    **div_kwargs: Any,
) -> T:
    if proxy_props is None:
        # When wrapping a wrapper, inherit the inner's proxy_props so the
        # chain works transparently. Otherwise look up defaults by type.
        if is_wrapped(inner):
            proxy_props = inner._proxy_props
        else:
            proxy_props = _DEFAULTS.get(type(inner), ())
    cls = make_wrapper_class(container)
    return cls(inner, proxy_props=proxy_props, children=children, **div_kwargs)

def is_wrapped(obj: Any) -> bool:
    return isinstance(obj, ComponentWrapper)
```

## Typing design

- `wrap()` uses `TypeVar("T", bound=Component)` → return type is the inner's type. `chart = wrap(graph)` gives `chart: dcc.Graph` in Pylance.
- `ComponentWrapper` is `Generic[T]` — typed subclassing via `class MyCard(ComponentWrapper[dcc.Graph]): ...`. `self.__wrapped__: dcc.Graph` narrows correctly.
- `make_wrapper_class()` returns `Generic[T]`-parameterized classes → tier-2 subclasses get the same typing.

### Type-lie trade-off

Pylance sees `wrap(graph)` as `dcc.Graph`. So `chart.children` (an `html.Div` prop not on `dcc.Graph`) fails type-checking. Runtime allows it because Dash's renderer iterates `_prop_names` including `children`. Desired behavior: the type checker nudges users away from accessing div-level props via the wrapper, while Dash internals keep working. If users genuinely need div-level access, `cast(html.Div, chart).children` is the explicit opt-in.

## Edge cases

| Case | Handling |
|---|---|
| Inner has no id | `ValueError` at construction |
| Inner has dict (pattern-matching) id | Works — `_set_random_id` returns whatever id is |
| `proxy_props` includes a prop the inner doesn't have | `ValueError` against inner's `_prop_names` |
| `children` provided but omits inner | `ValueError` — inner must render somewhere |
| Nested wrappers (`wrap(wrap(graph))`) | Supported first-class — see dedicated "Nested wrappers" section below |
| `triggered_id` from click | Returns inner's id (standard Dash behavior) |
| `copy.deepcopy` / pickle | Regular attributes + `Component.__reduce__` handles it |
| `div_kwargs` key coincides with a `proxy_prop` name | **Silent precedence** (Q14): kwargs set the outer; attribute reads/writes go through `proxy_props` to inner. Documented as two mechanisms |
| `isinstance(wrapper, html.Div)` | True (real subclassing) |
| `isinstance(wrapper, type(inner))` | True (`__class__` property) |
| `type(wrapper)` | `ComponentWrapper` — used by Dash for `_type`/`_namespace` inheritance |
| Proxy prop read after callback update | Returns initial value (standard Dash — client-side updates don't mutate server-side Python) |
| Multiple wrappers sharing one inner | Unsupported — inner has one parent in a Dash tree |
| Accessing `wrapper.children` via Python | Allowed (Dash renderer needs it); Pylance flags when inner's type has no `children` prop |

## Nested wrappers — first-class support

Nested wrappers are a real use case (e.g., a `dcc.Graph` wrapped for capture, then re-wrapped for corporate framing — each layer adds one concern). The design supports arbitrary depth:

```python
graph = dcc.Graph(id="x", figure=fig)
inner = wrap(graph, children=[graph, html.Small("inner caption")])
outer = wrap(inner, children=[inner, html.Small("outer caption")])
```

### What works and why

| Operation | Result | Why |
|---|---|---|
| `outer.__wrapped__` | `inner` | stored once at construction |
| `outer.__wrapped__.__wrapped__` | `graph` | user climbs the chain explicitly |
| `is_wrapped(outer)`, `is_wrapped(inner)` | `True` | `isinstance(_, ComponentWrapper)` |
| `is_wrapped(graph)` | `False` | graph isn't a wrapper |
| `outer.id` (via `_set_random_id`) | `"x"` | walks chain to innermost concrete component |
| `outer.__class__` | `dcc.Graph` | `__class__` property recurses: `outer.__wrapped__.__class__` → `inner.__wrapped__.__class__` → `graph.__class__` |
| `isinstance(outer, dcc.Graph)` | `True` | follows from `__class__` |
| `outer.figure` | `graph.figure` | `__getattr__` chain: `outer` → `inner` → `graph` |
| `outer.figure = fig` | updates `graph.figure` | `__setattr__` chain |
| `Output(outer, "figure")` in callback | resolves to `graph`'s id, updates `graph.figure` | same mechanism as the single-level case |
| DOM rendering | 3-level `<div>` tree, one `id="x"` on the graph | only graph has an explicit id |

### Ergonomic detail: `wrap(inner_wrapper)` inherits proxy_props

When calling `wrap(inner)` where `inner` is itself a wrapper, there's no `type(inner)` entry in the defaults registry (it would be `ComponentWrapper`, not `dcc.Graph`). To keep the drop-in contract, `wrap()` inherits `proxy_props` from the inner wrapper automatically — see the `wrap()` sketch above.

### Validation behavior under nesting

`_contains(children, inner)` recurses through the component subtree. For nested wrappers this means:

- `wrap(inner)` with no children → auto-includes `[inner]`. ✓
- `wrap(inner, children=[inner, other])` → containment check finds `inner` directly. ✓
- `wrap(inner, children=[graph, other])` → user tried to skip a level by putting `graph` directly — `_contains` only matches `is` identity, doesn't match `graph` against `inner`, so `ValueError` is raised. ✓

### What's not supported

- **Cycles**: impossible to construct because `__wrapped__` is set in `__init__` before the outer exists, so you can't point outer→inner→outer.
- **Wrapping unrelated components under one wrapper**: that's "multi-inner" (Q6), explicitly out of scope.
- **Sharing the same inner across multiple wrappers in the same tree**: Dash requires each component to have one parent.

### Performance

Attribute access on a k-deep chain is O(k). Each hop is a frozenset membership check + one `getattr`. For realistic use (1–3 levels) this is noise; we don't optimize.

## Testing strategy

Exhaustive — every edge case documented above has a matching test. Tests are organized by file; entries prefixed `(N)` exercise nested-wrapper behavior specifically.

### `tests/test_wrapper.py` — construction & adapter behavior

- Construction with no `id` on inner → `ValueError`.
- Construction with dict (pattern-matching) `id` on inner → accepted; `wrapper.id` returns the dict.
- Construction with `proxy_props` naming a prop the inner doesn't have → `ValueError` listing available props.
- Construction with `children=[…, not inner, …]` (inner missing) → `ValueError`.
- Construction with `children=None` → auto-includes `[inner]`.
- Construction with `children=[inner]` explicit → no error.
- Construction with `children` containing inner nested inside another Component's children → containment walker finds it, no error.
- `wrapper.__wrapped__` is the inner component (identity, not equality).
- `wrapper.id` returns inner's id (single-level).
- `wrapper.<proxy_prop>` read → inner's current value.
- `wrapper.<proxy_prop>` write → updates inner.
- `wrapper.<non_proxy_attr>` read where attr not on wrapper or inner → `AttributeError`.
- `wrapper.style = {...}` (not in proxy_props) → stored on outer div, not inner.
- `isinstance(wrapper, type(inner))` → True.
- `isinstance(wrapper, html.Div)` → True.
- `type(wrapper) is ComponentWrapper` → True (runtime type, distinct from `__class__`).
- `wrapper._prop_names` inherits from `html.Div`.
- **(N)** 2-level chain: `wrapper2 = wrap(wrap(graph))` — `wrapper2.__wrapped__` is the inner wrapper; `wrapper2.__wrapped__.__wrapped__` is the graph.
- **(N)** 3-level chain: identity traversal at each level.
- **(N)** Nested `wrapper.id` → innermost graph's id.
- **(N)** Nested `wrapper.__class__` → innermost type (e.g. `dcc.Graph`).
- **(N)** Nested `isinstance(wrapper, dcc.Graph)` → True at every level.
- **(N)** Nested attribute read `wrapper2.figure` → chains to graph.
- **(N)** Nested attribute write `wrapper2.figure = fig` → updates graph, not any intermediate.
- **(N)** Cycle-prevention is structural (impossible to construct) — no explicit test needed, but assert via a sanity check that `wrapper.__wrapped__ is not wrapper`.

### `tests/test_wrap_factory.py` — the `wrap()` function and proxy defaults

- `wrap(graph)` with no kwargs → default `proxy_props` from the registry (`figure`, `config`, `responsive`).
- `wrap(graph, proxy_props=["figure"])` → explicit overrides the registry default.
- `wrap(unknown_component)` where type not in registry → empty `proxy_props`; attribute access falls back to `AttributeError`.
- `wrap(graph, children=[graph, other])` → explicit children preserved.
- `wrap(graph, container=html.Figure)` → returned object renders as `<figure>`.
- `wrap(graph, container=html.Div)` → returns a `ComponentWrapper` instance specifically.
- `wrap(...)` return-type typing — `reveal_type` in a `py.typed` test fixture confirms Pylance/pyright infers the inner's type (not a runtime test, but a type-check fixture run by `ty` or `pyright` in CI).
- `register_proxy_defaults(CustomComponent, ["prop_a"])` → subsequent `wrap(CustomComponent(id="x"))` picks it up.
- `register_proxy_defaults` is idempotent (re-registering the same type replaces).
- **(N)** `wrap(wrap(graph))` default proxy_props → inherited from inner (graph's defaults, not empty).
- **(N)** `wrap(wrap(graph), proxy_props=["figure"])` → explicit wins over inheritance.
- `is_wrapped(wrap(graph))` → True.
- `is_wrapped(graph)` → False.
- `is_wrapped(html.Div())` → False.
- `is_wrapped(wrap(graph, container=html.Figure))` → True (figure-based wrapper).
- `is_wrapped(object_with_wrapped_attr)` where attr exists but isn't a ComponentWrapper → False (`isinstance`-based check excludes `functools.wraps` / `wrapt.ObjectProxy`).

### `tests/test_factory.py` — `make_wrapper_class`

- `make_wrapper_class(html.Div)` returns `ComponentWrapper` (same cached object).
- `make_wrapper_class(html.Figure)` returns a new class.
- `make_wrapper_class(html.Figure)` called twice returns the same class (cache hit).
- Returned class's `__name__` is `FigureWrapper`.
- Returned class subclasses `html.Figure` and `_WrapperMixin`.
- Returned class is `Generic[T]`-parameterizable: `FigureWrapper[dcc.Graph]` typechecks.
- Instance of returned class renders as `<figure>` (check `to_plotly_json()["type"] == "Figure"`).
- **(N)** Can nest a `FigureWrapper` inside a `ComponentWrapper` and vice versa.

### `tests/test_subclassing.py` — user subclassing

- `class MyCard(ComponentWrapper[dcc.Graph]): ...` works, preserves generic parameterization.
- `self.__wrapped__` on a typed subclass is typed correctly.
- Subclass can override `__init__` and call `super().__init__(...)` — tested with a styled-card example.
- Subclass's `_prop_names` still resolves to html.Div's.
- Tier-2: `class MyCaption(make_wrapper_class(html.Figure)[dcc.Graph]): ...` works.
- Subclass that forgets to call `super().__init__()` raises an informative error (not a silent broken state).

### `tests/test_serialization.py` — Dash layout emission

- `wrapper.to_plotly_json()` returns `{"type": "Div", "namespace": "dash_html_components", "props": {"children": [...]}}`.
- No `id` key in `props` (wrapper itself has no HTML id).
- Inner component appears in `children` with its own `to_plotly_json()` descriptor.
- `wrap(graph, container=html.Figure).to_plotly_json()` → `type: "Figure"`.
- `copy.deepcopy(wrapper)` produces a wrapper with a deepcopied inner; original is unchanged.
- `pickle.loads(pickle.dumps(wrapper))` round-trips.
- **(N)** Nested wrapper's `to_plotly_json()` produces nested Div descriptors, one per layer.

### `tests/test_callbacks.py` — integration (DashDuo + Chrome)

Each test builds a minimal Dash app, starts a real browser, and asserts DOM/callback behavior.

- `Output(wrap(graph), "figure")` + `Input("btn", "n_clicks")` — click button, graph updates.
- `Input(wrap(graph), "clickData")` — click a point on the graph, a sibling's `children` updates.
- `State(wrap(graph), "figure")` — read inside a callback, correct figure returned.
- `Output` on a pattern-matching id inner works.
- DOM assertion: query all elements with an `id` attribute; assert the set size equals the number of user-provided ids (no duplicate-id bleed from wrappers).
- **(N)** `Output(outer_wrapper, "figure")` updates the innermost graph through a 2-level nest.
- **(N)** Mixed-container nest (`wrap(wrap(graph, container=html.Figure), container=html.Section)`) callback still resolves.
- `wrap(graph, container=html.Figure)` callback with `<figcaption>` sibling — caption text updates via its own `Output`.

### `tests/test_dash_internals.py` — regression pin

- Assert `Component._set_random_id` exists on the installed Dash version; fail loudly if not.
- Assert `Component._prop_names` is a class attribute listing prop names.
- Assert our override of `_set_random_id` on a subclass is invoked by Dash's callback resolution (construct a callback, use `Output(wrapper, ...)`, verify `_set_random_id` was called). Uses monkeypatching to observe.
- Assert `dcc.Graph._prop_names` includes `figure`, `config`, `responsive` (our default-registry entries stay accurate).
- Parametrized across `dash>=2.9`, `dash>=2.14`, `dash>=2.17`, `dash>=3.0`.

### `tests/test_typing.py` — static-type contract

Non-executable-at-runtime; run via `ty` (or pyright) in CI as a type-check-only suite.

- `reveal_type(wrap(dcc.Graph(id="x")))` → `dcc.Graph`.
- `reveal_type(wrap(DataTable(id="x")))` → `DataTable`.
- `reveal_type(ComponentWrapper(graph, proxy_props=["figure"]))` → `ComponentWrapper[dcc.Graph]`.
- `reveal_type(chart.__wrapped__)` after `chart = wrap(graph)` → `dcc.Graph`.
- `chart.children` (on inner-typed chart) → type error (dcc.Graph has no `children`).
- `cast(html.Div, chart).children` → OK.

### CI matrix

GitHub Actions — `dash=={2.9, 2.14, 2.17, 3.0.x}` × Python `{3.10, 3.11, 3.12, 3.13}` × `OS={ubuntu-latest}`. Integration tests (Chrome + DashDuo) run only on `ubuntu-latest` to keep the matrix small; unit/factory/subclass/serialization/typing tests run on all combinations.

### Test-fixture conventions

- One pytest fixture `make_graph` that returns a fresh `dcc.Graph(id=..., figure=...)` per test — nothing shared between tests.
- One pytest fixture `app` that returns a fresh `Dash()` — callback registry isolated.
- `dash_duo` from `dash.testing` is the integration-test harness.
- Nested tests parametrize depth (`[1, 2, 3]`) and assert invariants at each level.

## Docs

Single-page mkdocs site, matching `dash-capture`'s convention.

```
dash-wrap/
├── mkdocs.yml          # copied from dash-capture, s/dash-capture/dash-wrap/
└── docs/
    └── index.md
```

`docs/index.md` sections:

1. **Pitch** (2–3 sentences) — what + why.
2. **Install + 30-second example** (`pip install dash-wrap`, one minimal snippet).
3. **API** — generated from docstrings via `mkdocstrings`:
   - `::: dash_wrap.wrap` (documented first)
   - `::: dash_wrap.ComponentWrapper`
   - `::: dash_wrap.is_wrapped`
   - `::: dash_wrap.register_proxy_defaults`
   - `::: dash_wrap.make_wrapper_class`
4. **Recipes** (4–6 short examples):
   - Card-styled graph
   - Semantic `<figure>` + `<figcaption>`
   - Input + error-message sibling
   - DataTable + toolbar header
   - Subclassing for a stable named wrapper
5. **How it works + caveats**: `_set_random_id` aliasing, `__class__` trick, `__wrapped__` convention (nod to `wrapt`/`functools.wraps`). Caveats: `_set_random_id` is undocumented Dash API; `type(wrapper)` is still `ComponentWrapper`; multi-wrapping unsupported; subclass stability caveat ("may change in minor versions — pin your dep if you subclass").

README = trimmed `index.md` (pitch + install + one example + link to full docs).

## Repo / release setup

- Layout: `src/`-based (matches brand-toolkit convention).
- Tooling: `uv`, `ruff`, `ty`, `prek`, `setuptools-scm`.
- License: MIT.
- Author / copyright: Simon Niederberger.
- Versioning: `setuptools-scm` from git tags. Initial `0.0.1`.
- Host: GitHub (public), with GitHub Actions matching dash-capture's CI pattern.
- Publishing: PyPI via OIDC (trusted publisher), triggered on version tag push.
- Docs hosting: GitHub Pages via `mike`.
- **Repo creation and publishing are owned by the user** — scaffold the code + CI configs; the user creates the GitHub repo and does the first PyPI release.

## Integration with dash-capture

Once `dash-wrap` is published and stable:

1. Add `dash-wrap` as a dependency of `dash-capture`.
2. Extend `capture_graph` with opt-in `wrap: bool = False`:
   ```python
   def capture_graph(graph, ..., wrap: bool = False) -> html.Div:
       ...
       if wrap and isinstance(graph, dcc.Graph):
           from dash_wrap import wrap as _wrap
           return _wrap(graph, children=[graph, wizard_div])
       return wizard_div  # existing behavior
   ```
3. `capture_element` gets the same treatment.

No breaking changes to dash-capture.

## Design rationale — pre-scaffold decisions

Non-obvious choices the user made during planning. The *what* is
encoded in the code; these are the *why*, preserved for anyone who
might otherwise try to reverse them.

- **Name `dash-wrap`, not `dash-wrapt`**: the wordplay on `wrapt` sets
  a 100%-transparency expectation we don't deliver (rendering sees
  `html.Div`, not the inner) and risks being read as a typo. We
  borrow conceptual patterns from `wrapt` (`__class__` spoof,
  `__wrapped__` convention) but don't depend on the package.
- **Host on GitHub public, PyPI from v0.0.1**: the research showed
  this semantic slot is empty in the Dash community. Hiding it
  undercuts the rationale for building it.
- **Auto-include `inner` in `children` when `children=None`**:
  ergonomics. `wrap(graph)` should be a true drop-in; requiring
  `children=[inner]` every time defeats the point.
- **`__class__` override is always-on, no opt-out kwarg**: simplest
  mental model, matches `wrapt`. Opt-out can be added later if a
  concrete breakage surfaces.
- **Single-inner only in v1**: "multi-inner" would mean
  `ComponentWrapper(inner={"chart": g, "table": t}, proxy_props={...})`
  for compound components with two addressable sub-components. Deferred
  because the common case is a styling/siblings wrapper, not a
  compound widget; AIO-style multi-inner is a different abstraction
  with its own namespace/id discipline.
- **Custom container tag supported** via
  :func:`make_wrapper_class` (tier-2 API): users who want
  `<figure>` / `<section>` / `<article>` shouldn't have to nest their
  wrapper inside an outer semantic container.
- **`dash >= 2.9`**: widest installed base with stable
  pattern-matching callbacks. Tested on 2.9, 2.14, 2.17, 3.0.x in CI.
- **`python >= 3.10`**: matches dash-capture; enables `X | Y` union
  syntax and `ParamSpec`.
- **MIT license, Simon Niederberger, v0.0.1**: matches the rest of
  brand-toolkit.
- **`proxy_props` vs `div_kwargs` name clash**: silent precedence.
  `div_kwargs['style']` styles the outer div; `inner.style` stays
  accessible via the proxy. They don't actually conflict — different
  props on different objects.
- **`wrap()` is the primary documented entry point**: 95% of users
  stop at `wrap(graph)`. `ComponentWrapper` is the primitive, revealed
  under "how it works".
- **`register_proxy_defaults` is public**: ~10 lines, clear use case
  for third-party component libraries (e.g.
  `dash-mantine-components`) to register their own defaults.

## Implementation notes

Engineering decisions made during the autonomous build. Each one
documents *what* was done, *why*, and how hard it would be to reverse.

### `is_wrapped` checks against `_WrapperMixin`, not `ComponentWrapper`

**Where**: [src/dash_wrap/_wrap.py](src/dash_wrap/_wrap.py) — the
module-internal `_WrapperMixin` import inside `is_wrapped`.

**Ambiguity**: The API sketch earlier in this file says
`is_wrapped(obj) = isinstance(obj, ComponentWrapper)`. But under the
mixin-based factoring, a `FigureWrapper` subclasses
`_WrapperMixin + html.Figure`, not `ComponentWrapper` (which is
`_WrapperMixin + html.Div`). So a `ComponentWrapper` check would
return `False` for a figure-based wrapper — contradicting the
behavioural test case `is_wrapped(wrap(graph, container=html.Figure)) → True`.

**Decision**: Check against `_WrapperMixin` (the common
implementation base) instead of `ComponentWrapper`. Docstring covers
both cases.

**Rationale**: Behavioural test expectation is stronger evidence of
intent than the literal sketch. `_WrapperMixin` is private but is a
valid `isinstance` target from inside `dash_wrap`.

**Alternatives considered**:

- Make `make_wrapper_class` return `ComponentWrapper` subclasses that
  *also* inherit from the requested container — impossible without
  MRO conflict (`html.Div` and `html.Figure` don't share a useful
  ancestor).
- Stamp wrappers with a marker attribute — collides with
  `wrapt.ObjectProxy`-style impostors.

**Cost to switch later**: trivial (one line in `_wrap.py`).

### Allowing `id=` in `div_kwargs`

**Where**: [`ComponentWrapper.__init__`](src/dash_wrap/_wrapper.py)
validation block.

**Ambiguity**: The design says wrapper has "no HTML id → no
`DuplicateIdError`." Should we forbid users from passing
`id="outer-id"` in `div_kwargs`?

**Decision**: Allow it. `_set_random_id` still resolves to the
inner's id (so callbacks work), but the outer div gets an `id` for
CSS/selector purposes.

**Rationale**: Useful for styling the outer wrapper by id selector;
doesn't break the callback contract. The
`test_div_kwargs_with_id_on_outer` unit test pins this behaviour.

**Cost to switch later**: trivial — add an explicit check in
`__init__`.

### Pickle needs a custom `__reduce_ex__`

**Where**:
[`_WrapperMixin.__reduce_ex__`](src/dash_wrap/_wrapper.py) +
`_unpickle_wrapper` module-level factory.

**Ambiguity**: The original edge-case table listed pickle round-trip
as "regular attributes + `Component.__reduce__` handles it." In
practice, Python's default reduce protocol calls `self.__class__`
(our spoof) for the reconstructor and fails the NEWOBJ invariant at
save time.

**Decision**: Added a module-level `_unpickle_wrapper(cls, state)`
factory and routed `__reduce_ex__` through it. Added `__setstate__`
that restores `__dict__` via `object.__setattr__` to bypass the proxy
`__setattr__`.

**Rationale**: Standard pattern for proxy classes that spoof
`__class__`. Keeps the public API unchanged.

**Alternatives considered**: descriptor-based `__class__` that
returns real type for pickle and inner type for `isinstance` (fragile
and complex); drop pickle support (too restrictive).

**Cost to switch later**: trivial.

### Three narrow `# ty: ignore[...]` suppressions

**Where**: [`__init__.py`](src/dash_wrap/__init__.py) (generated
`_version.py` import), [`_factory.py`](src/dash_wrap/_factory.py)
(dynamic-MRO `_Wrapper` class),
[`_wrapper.py`](src/dash_wrap/_wrapper.py)
(`super().__init__(children=...)` under ty's view of the mixin MRO).

**Ambiguity**: `_version.py` doesn't exist until `setuptools-scm`
runs; dynamic class creation with a type-variable base confuses ty's
MRO resolver; and ty sees `super().__init__` in the mixin as
`object.__init__` because the Dash container is mixed in dynamically.

**Decision**: Three narrow `# ty: ignore[...]` comments, each with
an explanatory adjacent comment.

**Rationale**: Any generic-base reformulation would compromise
runtime ergonomics (user-facing `ComponentWrapper[dcc.Graph]` would
gain a second type parameter). Each suppression is scoped to one
line; the runtime invariants are fully exercised by the test suite.

**Alternatives considered**: broaden `_WrapperMixin` to
`Generic[ContainerT, T]` (public-API complexity); disable the
affected rules project-wide (too broad).

**Cost to switch later**: trivial (remove suppressions when ty
learns to handle these).

### Integration tests use a Chrome-availability probe

**Where**:
[tests/dash_wrap/test_callbacks.py](tests/dash_wrap/test_callbacks.py)
`_chrome_available` + `pytestmark = pytest.mark.skipif(...)`.

**Ambiguity**: DashDuo's own failure is coarse — it hangs for ~30s
per test trying to start chromedriver. A pre-flight probe is faster
overall but has a ~30s one-time cost.

**Decision**: Module-level probe that tries to launch headless
Chrome once; total overhead when Chrome is missing is ~30s
(regardless of test count). If the optional dev dep
`chromedriver-autoinstaller` is installed, it also installs a
matching driver before the probe.

**Rationale**: Keeps the unit-test suite fast. CI on `ubuntu-latest`
uses `browser-actions/setup-chrome@v1`, which always matches the
driver and passes the probe.

**Cost to switch later**: trivial.

### DashDuo needs `--no-sandbox` on GitHub runners

**Where**:
[tests/dash_wrap/conftest.py](tests/dash_wrap/conftest.py)
`pytest_setup_options`.

**Ambiguity**: The Chrome-availability probe in
`test_callbacks.py` passes on `ubuntu-latest` (it launches Chrome
with `--no-sandbox`), but DashDuo's own Selenium driver does not
pass that flag by default, so every integration test raised
`SessionNotCreatedException: Chrome instance exited` in CI while
the module was not skipped.

**Decision**: Added a `pytest_setup_options` hook in conftest.py
that returns `ChromeOptions` with `--headless=new`, `--no-sandbox`,
`--disable-gpu`, `--disable-dev-shm-usage`. Dash's pytest plugin
picks up this hook and uses the returned options for every DashDuo
session.

**Rationale**: `--no-sandbox` is required on GitHub's ubuntu
runners (and most container environments) because Chrome's
namespace sandbox needs privileges the runner doesn't grant.
`--disable-dev-shm-usage` avoids crashes on small `/dev/shm`
volumes. Local macOS / desktop Linux runs are unaffected — the
flags are harmless there.

**Cost to switch later**: trivial (delete the function).

### Dash `_prop_names` on instances, not classes, in Dash 4.x

**Where**:
[tests/dash_wrap/test_dash_internals.py](tests/dash_wrap/test_dash_internals.py).

**Ambiguity**: Earlier docs claimed "`Component._prop_names` is a
class attribute listing prop names." In Dash 4.1, `_prop_names` is
set as an **instance** attribute in `Component.__init__`.

**Decision**: The regression-pin test builds an instance first and
asserts against that. Our validator in `_wrapper.py` already did
`getattr(inner, "_prop_names", ())` on an instance, so no code
change was needed.

**Rationale**: Matches real Dash behaviour. If a future Dash moves
`_prop_names` back to the class, `getattr` will still find it.

**Cost to switch later**: trivial.

## Why not depend on wrapt?

`wrapt` (Graham Dumpleton, BSD-2) is the reference Python library for
object proxies — it inspired the `__class__` spoof and
`__wrapped__` attribute convention we use. The obvious question:
why not build on `wrapt.ObjectProxy` instead of hand-rolling?

Because our design has a fundamentally different *shape*:

- **`wrapt` is a fully-transparent proxy.** `wrapt.ObjectProxy` forwards
  every attribute, every operator, every dunder to the wrapped
  object. The point is "be the other thing."
- **dash-wrap is a split-identity, whitelist proxy.** Four identities
  live on one instance: render-time ( `html.Div` — real subclass for
  `_type` / `_namespace` / `_prop_names`), callback-resolution-time
  (inner's id — via `_set_random_id` override), `isinstance`-time
  (both inner and container — via `__class__` property **and** real
  subclassing), and attribute-access-time (selective — only
  `proxy_props` forward). These don't agree; they can't be served by
  a single "be the other thing" proxy.

Mechanically, the conflict shows up immediately. `wrapt.ObjectProxy`
isn't a subclass of `html.Div`, so at render time
`to_plotly_json()` can't find `_type` and the output is malformed.
You could try multi-inheriting from `ObjectProxy + html.Div` to get
both identities, but `ObjectProxy` uses C-level slot tricks that
don't cleanly mix with Dash's `ComponentMeta` metaclass, and even
if the MRO resolved you'd still need to re-implement
`__getattr__` / `__setattr__` with a whitelist — defeating the
reuse.

Cost/benefit check: the `wrapt` machinery we'd actually use
(`__class__` spoof + `__reduce_ex__`) is ~20 lines we already
wrote. In exchange we'd pin users to a C-extension runtime
dependency for code that doesn't need it.

**Decision**: keep the homage (in this doc and in the `__dir__`
docstring where we adopted the pattern), skip the dependency. If a
future dash-wrap maintainer is tempted to refactor onto wrapt: the
answer stays no unless Dash itself adopts a first-class "wrapping"
protocol that changes the shape of the problem.

## Lessons from reading wrapt

When scaffolding this package we did a full read of the
[wrapt source tree](https://github.com/GrahamDumpleton/wrapt)
(~12k lines across src/tests/docs/blog). Notes below so the
next person doesn't repeat the exercise.

### Adopted

- **`__dir__` forwarding** (from `wrapt.ObjectProxy.__dir__`) —
  merges the container's MRO-reachable names with the `proxy_props`
  whitelist so REPL / IDE tab-completion surfaces proxied props
  (`figure`, `config`, …) alongside `children` / `style` /
  `className`. See [`_WrapperMixin.__dir__`](src/dash_wrap/_wrapper.py).
  One subtlety not in wrapt: we can't call `super().__dir__()` because
  it routes through `object.__dir__` which reads `self.__class__`
  (our inner spoof) and returns the wrong class's attributes. Walk
  `type(self).__mro__` explicitly instead — that reads the C-level
  type slot and sees the real container class.

### Considered and rejected

- **Full-transparency `__getattr__` / `__setattr__` forwarding.**
  Our whitelist is the contract, not an accident. Global forwarding
  would silently route `wrapper.style = {...}` to the inner and
  break outer-div styling.
- **`wrapt.CallableObjectProxy` for wrapping callables.** Dash
  components aren't called. Not applicable.
- **`wrapt.PartialCallableObjectProxy` / `wrapt.partial`.** Same
  reason.
- **`wrapt.AutoObjectProxy` (per-instance class creation to inject
  only the dunders the wrapped object supports).** Clever solution
  to wrapt's "some objects are callable, some are iterable, some
  are awaitable" problem. All Dash components have the same dunder
  surface (none of those), so unnecessary complexity.
- **`wrapt.LazyObjectProxy` / `wrapt.lazy_import`.** We don't defer
  object creation anywhere. Dash components are eager by design.
- **`wrapt.synchronized` / the locking in `caching.py`.** No
  thread-sensitive state on the wrapper. Dash's callback model
  already handles concurrency.
- **`wrapt.importer` post-import hooks.** Dash-wrap has no
  monkey-patch story by design; components are composed, not
  mutated.
- **`_ObjectProxyMetaType` metaclass for forwarding `__module__` /
  `__doc__` / `__dict__`.** ~80 lines of subtlety to make the proxy
  look like it lives in the wrapped object's module. We explicitly
  want the opposite — `ComponentWrapper.__module__` should be
  `dash_wrap._wrapper`, `ComponentWrapper.__doc__` should describe
  our class, not inner's. This is the heart of the
  split-identity-vs-full-transparency distinction.
- **`WrapperNotInitializedError` (custom `ValueError` raised when
  `__wrapped__` is missing after init).** Our current `AttributeError`
  is fine; users won't `hasattr(wrapper, 'figure')` in ways that mask
  bugs. Skip unless a real case surfaces.
- **Cycle detection on `__wrapped__`-chain walks.** Cycles are
  structurally impossible in our design (outer is constructed after
  inner; you can't point outer → inner → outer). The defensive
  max-depth check is code for a case that can't happen without
  deliberately mutating `__wrapped__` post-construction.
- **`wrapt`'s C extension (`_wrappers.c`).** Attribute access on
  Dash components is never the hot path.
- **`.pyi` stub packages (wrapt ships `wrapt-stubs` separately).**
  Our `py.typed` marker + inline annotations cover the small API
  surface.

### Confirmed by wrapt's design

These were already in place before the read; wrapt's design just
validates the choices.

- **Custom `__reduce_ex__` for pickle under `__class__` spoofing.**
  wrapt's `ObjectProxy` intentionally raises
  `NotImplementedError("object proxy must define __reduce__()")` to
  force every subclass to decide pickle semantics deliberately. We
  did.
- **`__wrapped__` as the canonical "inner" attribute.** Matches
  `functools.wraps`, `wrapt.ObjectProxy`, and
  `inspect.unwrap`. Users who know one idiom know ours.
- **`_self_` prefix convention for proxy-local state** (we don't
  formally use it; we use `object.__setattr__` for the two attrs
  `__wrapped__` and `_proxy_props`). If we grow to four or five
  proxy-local fields the convention becomes attractive. For two
  fields, not needed.

### Licensing note

wrapt is **BSD-2-Clause**; MIT-compatible in every direction. A
runtime dep would be fine license-wise. Copying verbatim snippets
requires retaining the copyright notice (clause 1), which for
trivial lines like `return dir(self.__wrapped__)` is below the
originality threshold anyway. Our adopted `__dir__` adaptation is
substantially rewritten (we walk MRO explicitly, apply the
whitelist); the docstring notes the pattern's origin as a courtesy.

**Do not ship the `wrapt/` clone inside `dash-wrap/`.**
`dash-wrap/.gitignore` excludes it. When dash-wrap is extracted to
its own repo, the clone should be moved out or deleted — shipping
it would redistribute wrapt source under our package and confuse
users about the license.

## Risks

| Risk | Severity | Mitigation in place |
|---|---|---|
| `_set_random_id` removed/changed in a future Dash | Medium | CI matrix pins Dash versions; [test_dash_internals.py](tests/dash_wrap/test_dash_internals.py) asserts the hook exists and is invoked by the callback registry. |
| `__class__` property breaks in corners of Dash | Low | 256-test suite covers construction, serialisation, pickle, DashDuo round-trip; no breakage observed on Dash 2.9–4.1. Opt-out kwarg available as a fallback if needed later. |
| User duplicates inner in layout → `DuplicateIdError` | Low | `ComponentWrapper.__init__` validates via `_contains(children, inner)` and raises before Dash sees the tree. |
| Scope creep (multi-inner, custom styling helpers) | Medium | `Non-goals` section above + README enumerate what's explicitly out. |
| Dash 3.x / 4.x breaking changes | Covered | CI matrix includes Dash 2.9, 2.14, 2.17, 3.0.x; Dash 4.1 exercised in the monorepo. |
| Subclass API churn | Low | README calls out the subclass stability caveat; `wrap()` is the stable contract. Test `test_subclassing.py` pins current behaviour. |

## Research provenance

Confirmed empty semantic slot via broad search (Nov 2026):

- PyPI names (`dash-wrap`, `dash-proxy`, `dash-component-wrapper`, …): unoccupied or unrelated.
- Closest prior art: Dash All-in-One components — gives up identity transparency (`aio_id` + `.ids.subcomponent(aio_id)`).
- Plotly acknowledges the wrapper-author problem via `_dashprivate_transformFigure` (PR #706) but never shipped a Python primitive.
- `wrapt` (Graham Dumpleton) provides the conceptual patterns (`__class__` override, `__wrapped__` convention) — but is a 100%-transparent proxy; our split-identity need (rendering sees `html.Div`, callbacks see inner) rules out using `wrapt.ObjectProxy` directly.

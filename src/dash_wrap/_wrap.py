"""Primary factory (:func:`wrap`) and the :func:`is_wrapped` helper.

``wrap`` is the ergonomic 95% entry point: it picks default
``proxy_props`` from the registry keyed on ``type(inner)`` (or inherits
from an inner wrapper's ``proxy_props`` when nesting), selects the
wrapper class via :func:`dash_wrap.make_wrapper_class` so non-Div
containers just work, and returns a wrapped component.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, TypeVar

from dash import html
from dash.development.base_component import Component

from ._defaults import get_proxy_defaults
from ._factory import make_wrapper_class
from ._wrapper import ComponentWrapper

T = TypeVar("T", bound=Component)


def wrap(
    inner: T,
    *,
    proxy_props: Iterable[str] | None = None,
    children: Any = None,
    container: type[Component] = html.Div,
    **div_kwargs: Any,
) -> T:
    """Wrap ``inner`` in a callback-transparent container.

    The returned object is a ``ComponentWrapper`` (or a generated subclass
    of ``container``) that proxies selected props to ``inner``. Callbacks
    written against the wrapper resolve to the inner's id, so it behaves
    as a drop-in replacement everywhere Dash inspects a component
    instance. The return type is declared as the inner's type so that
    static type checkers see ``wrap(graph)`` as ``dcc.Graph``.

    Parameters
    ----------
    inner
        The component to wrap. Must have a non-None ``id``.
    proxy_props
        Attribute names that read / write through to ``inner``. When
        ``None`` (the default), looked up by ``type(inner)`` in the
        built-in + user-registered defaults. If ``inner`` is itself a
        wrapper, its ``_proxy_props`` are inherited so chained wraps
        stay transparent.
    children
        Dash ``children`` for the outer container. When ``None`` the
        wrapper auto-includes ``[inner]``; otherwise ``inner`` must
        appear somewhere in the subtree.
    container
        Dash container class for the outer element — ``html.Div`` by
        default. Alternatives such as ``html.Figure`` or
        ``html.Section`` are supported via :func:`make_wrapper_class`,
        whose results are cached.
    **div_kwargs
        Forwarded to the container's ``__init__``, e.g. ``style``,
        ``className``.

    Returns
    -------
    T
        A wrapper whose declared type is ``type(inner)``. At runtime the
        object's ``__class__`` is spoofed to match the inner so
        ``isinstance(result, type(inner))`` is ``True`` while
        ``type(result)`` is still the wrapper class.

    Raises
    ------
    ValueError
        If ``inner`` has no id, if ``proxy_props`` references an attribute
        that isn't on ``inner``, or if ``children`` is provided without
        including ``inner``.
    TypeError
        If ``inner`` is not a Dash Component or ``container`` is not a
        Component subclass.

    Examples
    --------
    >>> from dash import dcc, html
    >>> from dash_wrap import wrap
    >>> graph = dcc.Graph(id="revenue", figure={})
    >>> chart = wrap(graph, children=[graph, html.Small("Source: ABS")])
    >>> isinstance(chart, dcc.Graph)
    True
    """
    if proxy_props is None:
        if isinstance(inner, ComponentWrapper):
            proxy_props = inner._proxy_props
        else:
            proxy_props = get_proxy_defaults(type(inner))
    cls = make_wrapper_class(container)
    wrapper = cls(inner, proxy_props=proxy_props, children=children, **div_kwargs)
    return wrapper  # type: ignore[return-value]


def is_wrapped(obj: Any) -> bool:
    """Return True if ``obj`` is a ``dash-wrap`` wrapper specifically.

    Checks by ``isinstance(obj, ComponentWrapper)`` — so this returns
    ``True`` for both the public ``ComponentWrapper`` and any generated
    subclass from :func:`make_wrapper_class`, because those share the
    ``_WrapperMixin`` base and are registered under the same class chain.
    It deliberately does **not** look at the ``__wrapped__`` attribute,
    so objects produced by ``functools.wraps`` or ``wrapt.ObjectProxy``
    do not match.

    Parameters
    ----------
    obj
        Any object.

    Returns
    -------
    bool
        ``True`` iff ``obj`` was produced by ``dash_wrap``.

    Examples
    --------
    >>> from dash import dcc
    >>> from dash_wrap import wrap, is_wrapped
    >>> graph = dcc.Graph(id="x")
    >>> is_wrapped(wrap(graph))
    True
    >>> is_wrapped(graph)
    False
    """
    from ._wrapper import _WrapperMixin

    return isinstance(obj, _WrapperMixin)

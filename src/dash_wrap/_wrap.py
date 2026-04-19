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

    The returned object is a ``ComponentWrapper`` (or a generated
    subclass of ``container``) that proxies selected props to
    ``inner``. Callbacks written against the wrapper resolve to the
    inner's id, so it behaves as a drop-in replacement everywhere
    Dash inspects a component instance. The return type is declared
    as the inner's type so static type checkers see ``wrap(graph)``
    as ``dcc.Graph``.

    Parameters
    ----------
    inner : T
        The component to wrap. Must have a non-None ``id``.
    proxy_props : Iterable[str] or None, optional
        Attribute names that read / write through to ``inner``.
        When ``None``, looked up by ``type(inner)`` in the built-in +
        user-registered defaults; if ``inner`` is itself a wrapper,
        its ``_proxy_props`` are inherited so chained wraps stay
        transparent. By default None.
    children : Any, optional
        Dash ``children`` for the outer container. When ``None`` the
        wrapper auto-includes ``[inner]``; otherwise ``inner`` must
        appear somewhere in the subtree. By default None.
    container : type[Component], optional
        Dash container class for the outer element. Alternatives
        such as ``html.Figure`` or ``html.Section`` are supported via
        :func:`make_wrapper_class`, whose results are cached. By
        default ``html.Div``.
    **div_kwargs : Any
        Forwarded to the container's ``__init__`` — for example
        ``style``, ``className``, ``id``.

    Returns
    -------
    T
        A wrapper whose declared type is ``type(inner)``. At runtime
        the object's ``__class__`` is spoofed to match the inner so
        ``isinstance(result, type(inner))`` is ``True`` while
        ``type(result)`` is still the wrapper class.

    Raises
    ------
    ValueError
        If ``inner`` has no id, if ``proxy_props`` references an
        attribute that isn't on ``inner``, or if ``children`` is
        provided without including ``inner``.
    TypeError
        If ``inner`` is not a Dash ``Component`` or ``container`` is
        not a ``Component`` subclass.

    See Also
    --------
    ComponentWrapper : The ``html.Div``-based wrapper class;
        subclass this for stable named wrappers.
    make_wrapper_class : Generate / retrieve the cached wrapper
        class for a non-``Div`` container.
    is_wrapped : Check whether an object is a dash-wrap wrapper.
    register_proxy_defaults : Register default ``proxy_props`` for a
        component type so callers no longer need to pass them
        explicitly.

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

    Checks by ``isinstance`` against the internal ``_WrapperMixin``
    base, so this returns ``True`` for the public
    :class:`ComponentWrapper` **and** any generated subclass from
    :func:`make_wrapper_class`. It deliberately does **not** look at
    the ``__wrapped__`` attribute, so objects produced by
    ``functools.wraps`` or ``wrapt.ObjectProxy`` are excluded.

    Parameters
    ----------
    obj : Any
        The object to test.

    Returns
    -------
    bool
        ``True`` iff ``obj`` was produced by ``dash_wrap``.

    See Also
    --------
    wrap : The factory that produces the objects this check matches.
    ComponentWrapper : The ``html.Div``-based wrapper class.

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

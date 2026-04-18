"""Core wrapper primitives.

Defines the ``_WrapperMixin`` that implements all adapter behaviour
(``_set_random_id`` override, ``__class__`` spoof, proxy-prop access and
assignment, construction-time validation) and the public
``ComponentWrapper`` class that composes the mixin with ``html.Div``.

The mixin is kept private in v1 to reserve the option of surfacing it as
a tier-3 public API (for diamond-inheritance use cases) in a later
minor version without churning the v1 surface.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Generic, TypeVar

from dash import html
from dash.development.base_component import Component

T = TypeVar("T", bound=Component)


def _unpickle_wrapper(cls: type, state: dict) -> Any:
    """Reconstruct a wrapper instance during unpickling.

    Creates the object with ``cls.__new__`` (skipping ``__init__``) then
    applies the saved ``__dict__`` via :meth:`_WrapperMixin.__setstate__`.
    Exposed at module level so pickle can resolve it by qualified name.
    """
    obj = object.__new__(cls)
    obj.__setstate__(state)
    return obj


def _contains(tree: Any, target: Component) -> bool:
    """Return True if ``target`` is anywhere in the Dash component subtree.

    Parameters
    ----------
    tree
        A Dash children value: a Component, a list / tuple of children,
        a primitive (str / number), or None.
    target
        The component whose presence is being checked. Match is by object
        identity (``is``), not equality.
    """
    if tree is target:
        return True
    if isinstance(tree, Component):
        return _contains(getattr(tree, "children", None), target)
    if isinstance(tree, (list, tuple)):
        return any(_contains(c, target) for c in tree)
    return False


class _WrapperMixin:
    """Adapter behaviour shared by every ``dash-wrap`` wrapper class.

    Provides:

    - ``__init__`` that validates and installs an inner component,
    - ``_set_random_id`` override that walks the ``__wrapped__`` chain,
    - ``__class__`` property that makes ``isinstance(wrapper, type(inner))``
      return ``True``,
    - proxy-prop ``__getattr__`` and ``__setattr__`` that forward selected
      attribute access to the inner component.

    The mixin is expected to be combined with a Dash container class
    (typically ``dash.html.Div``). All initialisation keyword arguments
    after ``inner`` are forwarded to the container's ``__init__`` via
    ``super().__init__``.
    """

    __wrapped__: Any
    _proxy_props: frozenset[str]

    def __init__(
        self,
        inner: Component,
        *,
        proxy_props: Iterable[str],
        children: Any = None,
        **container_kwargs: Any,
    ) -> None:
        if not isinstance(inner, Component):
            raise TypeError(
                f"inner must be a dash.development.base_component.Component "
                f"instance, got {type(inner).__name__}."
            )

        # When ``inner`` is itself a wrapper, identity (id and available
        # prop names) is carried on the innermost concrete component, not
        # on the intermediate wrapper objects. Walk the chain once.
        _innermost: Component = inner
        while isinstance(_innermost, _WrapperMixin):
            _innermost = _innermost.__wrapped__
        inner_id = getattr(_innermost, "id", None)
        if inner_id is None:
            raise ValueError(
                "ComponentWrapper requires an inner component with an id. "
                "Give the inner component an explicit id= before wrapping it."
            )

        proxy_set = frozenset(proxy_props)
        available = set(getattr(_innermost, "_prop_names", ()) or ())
        if available:
            unknown = proxy_set - available
            if unknown:
                raise ValueError(
                    f"proxy_props {sorted(unknown)} not on "
                    f"{type(_innermost).__name__}; available: "
                    f"{sorted(available)}"
                )

        object.__setattr__(self, "__wrapped__", inner)
        object.__setattr__(self, "_proxy_props", proxy_set)

        if children is None:
            children = [inner]
        elif not _contains(children, inner):
            raise ValueError(
                "children must include the inner component "
                "(pass children=None to auto-include it)."
            )

        # ty cannot follow the Dash container class in our mixin-based
        # MRO, so it sees ``super().__init__`` as ``object.__init__``.
        # At runtime the call resolves to the container class's __init__
        # (e.g. html.Div.__init__), which accepts ``children`` and the
        # other Div props.
        super().__init__(children=children, **container_kwargs)  # ty: ignore[unknown-argument]

    def _set_random_id(self) -> Any:
        """Return the innermost component's id without setting one on self.

        Dash calls this when a dependency (``Output`` / ``Input`` / ``State``)
        references a bare component instance. The default implementation
        would allocate a random UUID and ``setattr`` it onto ``self`` as
        ``self.id``. We deliberately do neither: the wrapper should not
        emit an ``id`` attribute in the rendered DOM (avoiding
        ``DuplicateIdError`` when ``id`` is also proxied), and the id used
        for callback resolution must be the inner component's id so that
        callback updates reach the right target.

        Walks the ``__wrapped__`` chain to the innermost non-wrapper
        component, so this works at any nesting depth.
        """
        node = self.__wrapped__
        while isinstance(node, _WrapperMixin):
            node = node.__wrapped__
        return node.id

    @property
    def __class__(self):  # type: ignore[override]
        """Return the inner component's ``__class__``.

        Makes ``isinstance(wrapper, type(inner))`` return ``True`` while
        leaving ``type(wrapper)`` untouched (the Python builtin reads the
        C-level type slot, not this property). Uses the inner's
        ``__class__`` attribute rather than ``type(inner)`` so the property
        recurses through nested wrappers: each level's ``__class__`` call
        invokes the next level's property until it bottoms out at a
        non-wrapper whose ``__class__`` is its real type.

        Dash rendering is unaffected: ``_type`` and ``_namespace`` are
        class attributes resolved via ``type(self).__mro__``, which
        bypasses this property and therefore still reports the wrapper's
        container class (``html.Div`` etc.).
        """
        return self.__wrapped__.__class__

    def __getattr__(self, name: str) -> Any:
        # __getattr__ is called only when normal lookup fails, so it
        # cannot be used to shadow genuinely-present attributes. We look
        # up through the wrapped chain whenever the missing name is one
        # of this level's proxy_props.
        try:
            proxy = object.__getattribute__(self, "_proxy_props")
        except AttributeError:
            raise AttributeError(name) from None
        if name in proxy:
            return getattr(self.__wrapped__, name)
        raise AttributeError(
            f"{type(self).__name__!r} object has no attribute {name!r}"
        )

    def __setattr__(self, name: str, value: Any) -> None:
        proxy = self.__dict__.get("_proxy_props", ())
        if name in proxy:
            setattr(self.__wrapped__, name, value)
        else:
            super().__setattr__(name, value)

    def __reduce_ex__(self, protocol: Any) -> tuple[Any, ...]:
        # Default reduce looks up ``self.__class__`` for the unpickle
        # reconstructor; our __class__ property returns the inner's
        # class, which would tell pickle to rebuild a ``dcc.Graph`` with
        # ``html.Div`` constructor args. Route through a module-level
        # factory that takes the true runtime type and the object state.
        return _unpickle_wrapper, (type(self), self.__dict__)

    def __setstate__(self, state: dict) -> None:
        # Restore attributes with ``object.__setattr__`` to bypass our
        # proxy __setattr__ — all attributes (including ``_proxy_props``
        # and ``__wrapped__``) must land on the wrapper itself.
        for k, v in state.items():
            object.__setattr__(self, k, v)


class ComponentWrapper(_WrapperMixin, html.Div, Generic[T]):
    """``html.Div``-based component wrapper that proxies to an inner component.

    Callback-transparent: ``Output(wrapper, "prop")`` resolves to the
    inner component's id, so callbacks written against the wrapper update
    the inner. ``isinstance(wrapper, type(inner))`` is ``True``, and
    selected attributes read / write through to ``inner`` via
    ``proxy_props``. ``type(wrapper)`` is still ``ComponentWrapper`` at
    the C level, so Dash serialises the outer DOM as an ``html.Div``.

    Parameters
    ----------
    inner
        The component to wrap. Must be a ``dash.development.base_component.Component``
        instance with a non-None ``id`` (string or pattern-matching dict).
    proxy_props
        Attribute names whose reads and writes forward to ``inner`` via
        ``__getattr__`` / ``__setattr__``. Validated against ``inner._prop_names``.
    children
        The Dash ``children`` of the outer div. When ``None`` (default)
        the wrapper auto-includes ``[inner]``. When provided, the inner
        component must appear somewhere in the subtree — otherwise
        ``ValueError`` is raised.
    **div_kwargs
        Forwarded to ``html.Div.__init__`` — for example ``style``,
        ``className``, ``id``.

    Examples
    --------
    >>> from dash import dcc, html
    >>> from dash_wrap import ComponentWrapper
    >>> graph = dcc.Graph(id="x")
    >>> chart = ComponentWrapper(
    ...     graph,
    ...     proxy_props=["figure", "config"],
    ...     children=[html.H3("Revenue"), graph],
    ...     className="card",
    ... )
    >>> isinstance(chart, dcc.Graph)
    True
    >>> isinstance(chart, html.Div)
    True
    """

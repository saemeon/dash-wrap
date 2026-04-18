"""Default proxy-props registry.

Maps Dash component types to the prop names that the ``wrap()`` factory
should proxy by default. Third-party libraries can extend this via
``register_proxy_defaults``.

Entries are deliberately conservative: they cover the props that users
most commonly update from callbacks for each component type. Users can
always pass ``proxy_props=[...]`` explicitly to override.
"""

from __future__ import annotations

from collections.abc import Iterable

from dash.development.base_component import Component


def _build_default_registry() -> dict[type[Component], tuple[str, ...]]:
    """Build the default proxy-props registry from installed Dash modules.

    ``dash`` is a hard project dependency, so both ``dash.dcc`` and
    ``dash.dash_table`` are expected to import cleanly.
    """
    from dash import dash_table, dcc

    return {
        dcc.Graph: ("figure", "config", "responsive"),
        dcc.Input: ("value", "disabled"),
        dcc.Dropdown: ("value", "options", "disabled"),
        dcc.Textarea: ("value", "disabled"),
        dcc.Slider: ("value", "min", "max", "marks", "disabled"),
        dcc.RangeSlider: ("value", "min", "max", "marks", "disabled"),
        dcc.DatePickerSingle: ("date", "disabled"),
        dcc.DatePickerRange: ("start_date", "end_date", "disabled"),
        dash_table.DataTable: (
            "data",
            "columns",
            "page_current",
            "sort_by",
            "filter_query",
        ),
    }


_DEFAULTS: dict[type[Component], tuple[str, ...]] = _build_default_registry()


def register_proxy_defaults(
    component_type: type[Component],
    proxy_props: Iterable[str],
) -> None:
    """Register default proxy props for ``component_type``.

    ``wrap()`` calls look up defaults by ``type(inner)`` when no explicit
    ``proxy_props`` argument is passed. Re-registering the same type
    replaces the prior entry.

    Parameters
    ----------
    component_type
        A subclass of ``dash.development.base_component.Component``.
    proxy_props
        Iterable of prop names to proxy by default. Stored as a tuple.

    Raises
    ------
    TypeError
        If ``component_type`` is not a subclass of ``Component``.

    Examples
    --------
    >>> from dash_wrap import register_proxy_defaults
    >>> class MyWidget(Component): ...
    >>> register_proxy_defaults(MyWidget, ["value", "status"])
    """
    if not (isinstance(component_type, type) and issubclass(component_type, Component)):
        raise TypeError(
            "component_type must be a subclass of "
            "dash.development.base_component.Component, got "
            f"{component_type!r}."
        )
    _DEFAULTS[component_type] = tuple(proxy_props)


def get_proxy_defaults(component_type: type[Component]) -> tuple[str, ...]:
    """Return the registered default proxy props for ``component_type``.

    Returns an empty tuple when no defaults have been registered for this
    type. Private-ish helper exposed for ``wrap()`` and for tests; not
    part of the documented public API.
    """
    return _DEFAULTS.get(component_type, ())

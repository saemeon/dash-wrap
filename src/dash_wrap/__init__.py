"""dash-wrap — callback-identity-preserving component wrappers for Plotly Dash.

The public surface is a single page's worth of names:

- :func:`wrap` — primary, ergonomic factory. 95% of users stop here.
- :class:`ComponentWrapper` — ``html.Div``-based wrapper class, intended
  for subclassing when you want a stable named wrapper type.
- :func:`is_wrapped` — ``isinstance``-style check specific to dash-wrap.
- :func:`register_proxy_defaults` — extension hook for third-party
  component libraries.
- :func:`make_wrapper_class` — non-Div subclassing target (tier-2).
"""

from __future__ import annotations

try:
    from ._version import __version__
except ImportError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

from ._defaults import register_proxy_defaults
from ._factory import make_wrapper_class
from ._wrap import is_wrapped, wrap
from ._wrapper import ComponentWrapper

__all__ = [
    "ComponentWrapper",
    "__version__",
    "is_wrapped",
    "make_wrapper_class",
    "register_proxy_defaults",
    "wrap",
]

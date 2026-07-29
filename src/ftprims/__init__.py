"""ftprims: FTQC primitives benchmark suite.

Importing ``algorithms`` here resolves the ``ftprims.resource`` <->
``ftprims.algorithms.arithmetic`` import cycle once, so every entry point sees
the same import order.
"""

from ftprims import algorithms  # noqa: F401

__all__ = ["algorithms"]

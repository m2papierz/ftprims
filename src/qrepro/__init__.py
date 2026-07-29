"""qrepro: FTQC primitives benchmark suite.

Importing ``algorithms`` here resolves the ``qrepro.resource`` <->
``qrepro.algorithms.arithmetic`` import cycle once, so every entry point sees
the same import order.
"""

from qrepro import algorithms  # noqa: F401

__all__ = ["algorithms"]

"""ftprims — FTQC primitives benchmark suite.

Importing ``algorithms`` here pins the import order: ``ftprims.resource`` and
``ftprims.algorithms.arithmetic`` are mutually dependent, and resolving the
cycle once here means every entry point behaves the same.
"""

from ftprims import algorithms  # noqa: F401

__all__ = ["algorithms"]

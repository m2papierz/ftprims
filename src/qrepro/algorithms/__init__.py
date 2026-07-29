"""Primitive benchmarks; importing this module populates :data:`registry`."""

from qrepro.algorithms import (  # noqa: F401
    arithmetic,
    qft,
    qpe,
    qrom,
)
from qrepro.algorithms._base import registry

__all__ = ["registry"]

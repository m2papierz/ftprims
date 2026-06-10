"""Benchmark algorithm implementations."""

from ftprims.algorithms import (  # noqa: F401
    arithmetic,
    qft,
    qpe,
    qrom,
)
from ftprims.algorithms._base import registry


__all__ = ["registry"]

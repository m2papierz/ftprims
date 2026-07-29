"""Reproductions of published FTQC resource estimates.

One module per reproduction -- ``beverland``, ``ge19``, ``ge19_windowed``,
``decomposition`` -- each owning the frozen result containers next to the
``reproduce_*()`` function that builds them. ``values`` holds every published
constant; ``_base`` holds the shared ``ReproductionRow``.

This subpackage may import from the core modules; they never import from it.
"""

from __future__ import annotations

from qrepro.references.beverland import reproduce_beverland
from qrepro.references.decomposition import reproduce_2019_to_2025
from qrepro.references.ge19 import reproduce_ge19_logical, reproduce_ge19_physical
from qrepro.references.ge19_windowed import (
    reproduce_ge19_windowed,
    windowed_total_ccz,
)

__all__ = [
    "reproduce_beverland",
    "reproduce_ge19_logical",
    "reproduce_ge19_physical",
    "reproduce_ge19_windowed",
    "reproduce_2019_to_2025",
    "windowed_total_ccz",
]

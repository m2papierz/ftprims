"""Reproductions of published FTQC resource estimates.

Each reproduction computes its comparison rows once (``reproduce_*``) and returns
a frozen result container; tests assert them against the paper targets in
``values.py``, the notebooks render them, and the CLI prints them.

This subpackage may import from the core modules (``physical``, ``algorithms``,
``resource``); the core modules never import from ``ftprims.references``.
"""

from __future__ import annotations

from ftprims.references._base import (
    BeverlandInstance,
    BeverlandReproduction,
    DecompositionReproduction,
    DecompositionRow,
    GE19LogicalReproduction,
    GE19PhysicalReproduction,
    ReproductionRow,
)
from ftprims.references.beverland import (
    BeverlandReferenceCosts,
    beverland_reference_costs,
    reproduce_beverland,
)
from ftprims.references.decomposition import reproduce_2019_to_2025
from ftprims.references.ge19 import (
    ge19_formula_logical_costs,
    reproduce_ge19_logical,
    reproduce_ge19_physical,
)
from ftprims.references.values import BEVERLAND, G2025, GE19

__all__ = [
    # Paper constant tables
    "BEVERLAND",
    "GE19",
    "G2025",
    # Reproduction entry points
    "reproduce_beverland",
    "reproduce_ge19_logical",
    "reproduce_ge19_physical",
    "reproduce_2019_to_2025",
    "ge19_formula_logical_costs",
    "beverland_reference_costs",
    # Result containers
    "ReproductionRow",
    "BeverlandInstance",
    "BeverlandReproduction",
    "BeverlandReferenceCosts",
    "GE19LogicalReproduction",
    "GE19PhysicalReproduction",
    "DecompositionRow",
    "DecompositionReproduction",
]

"""Structural cost breakdown via Qualtran call_graph.

Decomposes a Bloq into a small set of component categories and
reports per-category T-gate, rotation, and Clifford counts. This
gives visibility into where the cost comes from rather than just
a single aggregate number.
"""

from __future__ import annotations

import math
from collections import defaultdict

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, get_cost_value
from qualtran.resource_counting.generalizers import (
    cirq_to_bloqs,
    generalize_rotation_angle,
    ignore_split_join,
)

from ftprims.algorithms._base import BreakdownItem


# Component taxonomy
COMPONENTS = (
    "rotations",
    "qft_qpe_core",
    "qrom_core",
    "arithmetic_core",
    "controlled_nonclifford",
    "clifford_scaffolding",
    "other",
)


def classify_component(leaf: Bloq) -> str:
    """Map a leaf Bloq to one of the fixed component categories.

    Classification is based on the module path and class name of the
    leaf. This is intentionally simple and stable, not a full
    ontology, but good enough for educational breakdown.
    """
    # Unwrap Adjoint to classify the inner bloq.
    if type(leaf).__name__ == "Adjoint" and hasattr(leaf, "subbloq"):
        return classify_component(leaf.subbloq)

    mod = type(leaf).__module__
    name = type(leaf).__name__

    # Module-based rules (most specific first)
    if "data_loading" in mod or "swap_network" in mod:
        return "qrom_core"
    if "phase_estimation" in mod or ".qft" in mod:
        return "qft_qpe_core"
    if ".arithmetic" in mod:
        return "arithmetic_core"

    # Name-based rules for basic gates
    if name in ("And", "Toffoli", "CCZ", "CSwap"):
        return "controlled_nonclifford"
    if name in ("CZPowGate",):
        return "controlled_nonclifford"

    # Rotation gates (by module or name)
    if ".rotation" in mod or "phase_gradient" in mod:
        return "rotations"

    # Clifford basic gates
    if "basic_gates" in mod:
        return "clifford_scaffolding"

    return "other"


def _default_generalizer(bloq: Bloq) -> Bloq | None:
    """Compose the standard generalizers for breakdown analysis."""
    for g in (cirq_to_bloqs, generalize_rotation_angle, ignore_split_join):
        bloq = g(bloq)
        if bloq is None:
            return None
    return bloq


def _rotation_t_cost(epsilon: float) -> int:
    """T-gates to synthesise one rotation to precision *epsilon*."""
    if epsilon <= 0:
        return 0
    return math.ceil(1.149 * math.log2(1.0 / epsilon) + 9.2)


# Some Qualtran bloqs report zero via QECGatesCost but still carry
# non-trivial gate cost (e.g. Toffoli decomposes into 1 And = 4T).
# Map class name => (raw_t, and_count, rotations, cliffords).
_COST_OVERRIDES: dict[str, tuple[int, int, int, int]] = {
    "Toffoli": (0, 1, 0, 0),
}


def _leaf_gate_costs(leaf: Bloq) -> tuple[int, int, int, int]:
    """Return ``(raw_t, and_count, rotations, cliffords)`` for a leaf.

    Checks hardcoded overrides first, then falls back to
    ``QECGatesCost``. Returns all zeros on failure.
    """
    name = type(leaf).__name__
    override = _COST_OVERRIDES.get(name)
    if override is not None:
        return override
    try:
        gates = get_cost_value(leaf, QECGatesCost())
        return (
            int(gates.t),
            int(gates.and_bloq),
            int(gates.rotation),
            int(gates.clifford),
        )
    except Exception:
        return 0, 0, 0, 0


def extract_structural_breakdown(
    bloq: Bloq,
    *,
    depth: int = 1,
    rotation_eps: float = 1e-10,
) -> tuple[BreakdownItem, ...]:
    """Break a Bloq into component categories with per-category costs.

    Parameters
    ----------
    bloq:
        The Bloq to analyse.
    depth:
        ``max_depth`` passed to ``call_graph``. 1 gives the top-level
        decomposition; higher values drill deeper.
    rotation_eps:
        Precision for rotation synthesis T-cost estimation.

    Returns
    -------
    tuple[BreakdownItem, ...]
        One item per component category that has non-zero cost.
        Categories with zero contribution are omitted.
    """
    _, sigma = bloq.call_graph(
        generalizer=_default_generalizer,
        max_depth=depth,
    )

    # Accumulate per-category totals.
    acc: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "invocations": 0,
            "direct_t": 0,
            "clifford_count": 0,
            "rotation_count": 0,
        }
    )

    t_per_rot = _rotation_t_cost(rotation_eps)

    for leaf, count in sigma.items():
        count = int(count)
        category = classify_component(leaf)

        # Extract per-leaf gate costs.
        raw_t, and_count, leaf_rotations, leaf_cliffords = _leaf_gate_costs(leaf)
        leaf_direct_t = raw_t + 4 * and_count

        bucket = acc[category]
        bucket["invocations"] += count
        bucket["direct_t"] += count * leaf_direct_t
        bucket["clifford_count"] += count * leaf_cliffords
        bucket["rotation_count"] += count * leaf_rotations

    # Build items with estimated FTQC cost.
    items: list[BreakdownItem] = []
    for component in COMPONENTS:
        if component not in acc:
            continue
        b = acc[component]
        est_ftqc = b["direct_t"] + b["rotation_count"] * t_per_rot
        items.append(
            BreakdownItem(
                component=component,
                invocations=b["invocations"],
                direct_t=b["direct_t"],
                clifford_count=b["clifford_count"],
                rotation_count=b["rotation_count"],
                est_t_ftqc=est_ftqc,
            )
        )

    return tuple(items)


def summarize_breakdown(
    items: tuple[BreakdownItem, ...],
) -> dict[str, float]:
    """Compute summary statistics from a breakdown.

    Returns a dict with:
    - ``dominant_component``: category with highest ``est_t_ftqc``
    - ``dominant_share``: its share of total ``est_t_ftqc`` (0-1)
    - ``rotation_share``: share of total ``est_t_ftqc`` from rotations
    - Per-component shares keyed as ``{component}_share``
    """
    total_ftqc = sum(item.est_t_ftqc for item in items)

    if total_ftqc == 0:
        dominant = items[0].component if items else "other"
        result: dict[str, float] = {
            "dominant_component": dominant,
            "dominant_share": 0.0,
            "rotation_share": 0.0,
        }
        for item in items:
            result[f"{item.component}_share"] = 0.0
        return result

    shares: dict[str, float] = {}
    for item in items:
        shares[item.component] = item.est_t_ftqc / total_ftqc

    dominant = max(items, key=lambda i: i.est_t_ftqc)

    result = {
        "dominant_component": dominant.component,
        "dominant_share": shares[dominant.component],
        "rotation_share": shares.get("rotations", 0.0),
    }
    for component, share in shares.items():
        result[f"{component}_share"] = share

    return result

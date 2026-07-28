"""Structural cost breakdown via Qualtran call_graph.

Decomposes a Bloq into a small set of component categories and
reports per-category T-gate, rotation, and Clifford counts. This
gives visibility into where the cost comes from rather than just
a single aggregate number.

Structural classification is always performed at depth=1 (the
bloq's immediate children) so that component labels are stable
regardless of how deep the gate-cost extraction goes. Gate costs
for each structural child are extracted via ``QECGatesCost``, which
internally decomposes as deep as necessary, this decouples "where
in the algorithm" from "what gates it costs".
"""

from __future__ import annotations

from collections import defaultdict

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, get_cost_value

from ftprims.algorithms._base import BreakdownItem
from ftprims.resource import (
    _default_generalizer,
    _extract_via_call_graph,
    _leaf_gate_costs,
    _magic_state_counts,
    rotation_synthesis_t_cost,
)

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

    Classification uses module path and class name as primary signals,
    augmented by cost-aware inspection of gate parameters. In
    particular, parameterised ``*PowGate`` bloqs are classified as
    ``rotations`` when their exponent is non-Clifford, rather than
    being lumped into ``controlled_nonclifford`` based on name alone.
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

    # Cost-aware: parameterised gates with non-Clifford exponent are
    # rotations regardless of their name (e.g. CZPowGate(exp=0.3)).
    if _is_parameterized_rotation(leaf):
        return "rotations"

    # Known non-Clifford multi-qubit gates (And/Toffoli always cost T).
    if name in ("And", "Toffoli", "CCZ", "CSwap"):
        return "controlled_nonclifford"

    # Rotation gates (by module or name)
    if ".rotation" in mod or "phase_gradient" in mod:
        return "rotations"

    # Clifford basic gates
    if "basic_gates" in mod:
        return "clifford_scaffolding"

    return "other"


# Exponents that correspond to Clifford gates (mod 2).
_CLIFFORD_EXPONENTS = frozenset({0.0, 0.5, 1.0, 1.5})


def _is_parameterized_rotation(bloq: Bloq) -> bool:
    """True when *bloq* has an ``exponent`` that is not a Clifford angle.

    This catches ``ZPowGate``, ``CZPowGate``, ``XPowGate`` etc. at
    non-Clifford angles — these are rotations that require synthesis,
    not cheap Clifford operations.
    """
    exponent = getattr(bloq, "exponent", None)
    if exponent is None:
        return False
    try:
        exp_mod = float(exponent) % 2.0
        # Small tolerance for floating-point comparison.
        return not any(abs(exp_mod - c) < 1e-12 for c in _CLIFFORD_EXPONENTS)
    except (TypeError, ValueError):
        # Symbolic exponent — conservatively treat as rotation.
        return True


def _child_gate_costs(child: Bloq) -> tuple[int, int, int, int]:
    """Return ``(raw_t, ccz_count, rotations, cliffords)`` for a structural child.

    Tries ``QECGatesCost`` first — it handles internal decomposition
    so that a composite bloq like ``Add`` returns its full gate cost
    without the caller needing to choose a depth.  Falls back to
    call-graph leaf aggregation, then to single-leaf extraction.

    When ``QECGatesCost`` returns only Clifford costs, deeper
    strategies are still attempted to find hidden non-Clifford gates.
    """
    clifford_fallback: tuple[int, int, int, int] | None = None

    # Strategy 1: QECGatesCost on the child (handles composites).
    try:
        gates = get_cost_value(child, QECGatesCost())
        raw_t, ccz = _magic_state_counts(gates)
        vals = (raw_t, ccz, int(gates.rotation), int(gates.clifford))
        if sum(vals) > 0:
            if vals[0] + vals[1] + vals[2] > 0:
                return vals
            clifford_fallback = vals
    except Exception:
        pass

    # Strategy 2: call_graph leaf aggregation.
    try:
        vals = _extract_via_call_graph(child)
        if sum(vals) > 0:
            if clifford_fallback is not None:
                # Merge: non-Clifford from call_graph, best Clifford from either.
                merged_cliff = max(vals[3], clifford_fallback[3])
                return (vals[0], vals[1], vals[2], merged_cliff)
            return vals
    except Exception:
        pass

    # Strategy 3: treat as a single leaf.
    leaf_vals = _leaf_gate_costs(child)
    if clifford_fallback is not None and sum(leaf_vals) == 0:
        return clifford_fallback
    return leaf_vals


def extract_structural_breakdown(
    bloq: Bloq,
    *,
    rotation_eps: float = 1e-10,
) -> tuple[BreakdownItem, ...]:
    """Break a Bloq into component categories with per-category costs.

    Structural classification is always done at ``max_depth=1``
    (immediate children) so that component labels are stable.  Gate
    costs for each child are extracted via ``QECGatesCost`` which
    internally decomposes as deep as needed — this decouples the
    structural "where" from the gate-level "what".

    Parameters
    ----------
    bloq:
        The Bloq to analyse.
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
        max_depth=1,
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

    t_per_rot = rotation_synthesis_t_cost(rotation_eps)

    for child, count in sigma.items():
        count = int(count)
        category = classify_component(child)

        # Extract full gate costs for this child.
        raw_t, ccz_count, child_rotations, child_cliffords = _child_gate_costs(child)
        child_direct_t = raw_t + 4 * ccz_count

        bucket = acc[category]
        bucket["invocations"] += count
        bucket["direct_t"] += count * child_direct_t
        bucket["clifford_count"] += count * child_cliffords
        bucket["rotation_count"] += count * child_rotations

    # Cost-aware reclassification: if a category classified as "rotations"
    # by module path actually contains zero rotation gates and only
    # non-Clifford T-gates (e.g. AddIntoPhaseGrad which decomposes to
    # Toffoli gates), merge it into "controlled_nonclifford".
    if "rotations" in acc:
        rot_bucket = acc["rotations"]
        if rot_bucket["rotation_count"] == 0 and rot_bucket["direct_t"] > 0:
            target = acc["controlled_nonclifford"]
            target["invocations"] += rot_bucket["invocations"]
            target["direct_t"] += rot_bucket["direct_t"]
            target["clifford_count"] += rot_bucket["clifford_count"]
            target["rotation_count"] += rot_bucket["rotation_count"]
            del acc["rotations"]

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

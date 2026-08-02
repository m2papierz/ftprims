"""Per-component cost attribution over the Qualtran call graph.

Structural classification runs at depth 1 so component labels stay stable; each
child's gate cost comes from ``QECGatesCost``, which decomposes as deep as needed.
"""

from __future__ import annotations

from collections import defaultdict

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, get_cost_value

from qrepro.algorithms._base import BreakdownItem
from qrepro.resource import (
    _default_generalizer,
    _extract_via_call_graph,
    _leaf_gate_costs,
    _magic_state_counts,
    rotation_synthesis_t_cost,
)

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
    """Map a leaf bloq to one of :data:`COMPONENTS`.

    Module path and class name are the primary signals. Parameterised
    ``*PowGate`` bloqs are classified by exponent rather than by name, so a
    non-Clifford ``CZPowGate`` lands in ``rotations``.
    """
    if type(leaf).__name__ == "Adjoint" and hasattr(leaf, "subbloq"):
        return classify_component(leaf.subbloq)

    mod = type(leaf).__module__
    name = type(leaf).__name__

    # Most specific module first.
    if "data_loading" in mod or "swap_network" in mod:
        return "qrom_core"
    if "phase_estimation" in mod or ".qft" in mod:
        return "qft_qpe_core"
    if ".arithmetic" in mod:
        return "arithmetic_core"

    if _is_parameterized_rotation(leaf):
        return "rotations"

    if name in ("And", "Toffoli", "CCZ", "CSwap"):
        return "controlled_nonclifford"

    if ".rotation" in mod or "phase_gradient" in mod:
        return "rotations"

    if "basic_gates" in mod:
        return "clifford_scaffolding"

    return "other"


# Exponents that correspond to Clifford gates (mod 2).
_CLIFFORD_EXPONENTS = frozenset({0.0, 0.5, 1.0, 1.5})


def _is_parameterized_rotation(bloq: Bloq) -> bool:
    """True when *bloq* has an ``exponent`` that is not a Clifford angle.

    A symbolic exponent counts as a rotation.
    """
    exponent = getattr(bloq, "exponent", None)
    if exponent is None:
        return False
    try:
        exp_mod = float(exponent) % 2.0
        return not any(abs(exp_mod - c) < 1e-12 for c in _CLIFFORD_EXPONENTS)
    except (TypeError, ValueError):
        return True


def _child_gate_costs(child: Bloq) -> tuple[int, int, int, int]:
    """Return ``(raw_t, ccz_count, rotations, cliffords)`` for one child.

    ``QECGatesCost`` handles internal decomposition, so a composite like ``Add``
    reports its full cost without the caller picking a depth. A Clifford-only
    result falls through to the deeper strategies, which may find non-Clifford
    gates it missed.
    """
    clifford_fallback: tuple[int, int, int, int] | None = None

    # 1. QECGatesCost on the child.
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

    # 2. call_graph leaf aggregation.
    try:
        vals = _extract_via_call_graph(child)
        if sum(vals) > 0:
            if clifford_fallback is not None:
                merged_cliff = max(vals[3], clifford_fallback[3])
                return (vals[0], vals[1], vals[2], merged_cliff)
            return vals
    except Exception:
        pass

    # 3. Treat the child as a single leaf.
    leaf_vals = _leaf_gate_costs(child)
    if clifford_fallback is not None and sum(leaf_vals) == 0:
        return clifford_fallback
    return leaf_vals


def extract_structural_breakdown(
    bloq: Bloq,
    *,
    rotation_eps: float = 1e-10,
) -> tuple[BreakdownItem, ...]:
    """One :class:`BreakdownItem` per component category with non-zero cost,
    in :data:`COMPONENTS` order.

    *rotation_eps* is the precision used to convert rotation counts to a
    T-equivalent.
    """
    _, sigma = bloq.call_graph(
        generalizer=_default_generalizer,
        max_depth=1,
    )

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
        raw_t, ccz_count, child_rotations, child_cliffords = _child_gate_costs(child)
        child_direct_t = raw_t + 4 * ccz_count

        bucket = acc[category]
        bucket["invocations"] += count
        bucket["direct_t"] += count * child_direct_t
        bucket["clifford_count"] += count * child_cliffords
        bucket["rotation_count"] += count * child_rotations

    # A "rotations" bucket with no rotation gates and non-zero T is really
    # controlled non-Clifford work: AddIntoPhaseGrad decomposes to Toffolis.
    if "rotations" in acc:
        rot_bucket = acc["rotations"]
        if rot_bucket["rotation_count"] == 0 and rot_bucket["direct_t"] > 0:
            target = acc["controlled_nonclifford"]
            target["invocations"] += rot_bucket["invocations"]
            target["direct_t"] += rot_bucket["direct_t"]
            target["clifford_count"] += rot_bucket["clifford_count"]
            target["rotation_count"] += rot_bucket["rotation_count"]
            del acc["rotations"]

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
    """Summary statistics over a breakdown.

    Keys: ``dominant_component``, ``dominant_share`` and ``rotation_share``
    (shares of total ``est_t_ftqc``, 0-1), plus ``{component}_share`` per
    category present.
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

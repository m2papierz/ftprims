"""Logical-cost extraction from Qualtran's ``QECGatesCost``.

Raw-T and CCZ counts stay separated; the FTQC T-count adds rotation synthesis
at the Ross-Selinger cost. Physical estimation lives in ``ftprims.physical``.
"""

from __future__ import annotations

import math

from qualtran import Bloq
from qualtran.resource_counting import (
    QECGatesCost,
    QubitCount,
    get_cost_value,
)
from qualtran.resource_counting.generalizers import (
    cirq_to_bloqs,
    generalize_rotation_angle,
    ignore_split_join,
)

from ftprims.algorithms._base import LogicalCosts
from ftprims.config import DEFAULT_CONFIG


def rotation_synthesis_t_cost(epsilon: float) -> int:
    """T-gates to synthesise one arbitrary rotation to precision *epsilon*.

    ``T = ceil(3·log2(1/eps))``, the leading term of Ross & Selinger
    (arXiv:1403.2975) Theorem 1.1; the ``O(log log(1/eps))`` remainder is
    dropped. Non-positive *epsilon* means skip synthesis and returns 0.
    """
    if epsilon <= 0:
        return 0
    return math.ceil(3.0 * math.log2(1.0 / epsilon))


_CALL_GRAPH_MAX_DEPTH = 4

# Bloqs whose QECGatesCost returns zero but have known non-trivial cost.
_COST_OVERRIDES: dict[str, tuple[int, int, int, int]] = {
    "Toffoli": (0, 1, 0, 0),  # (raw_t, ccz_count, rotations, cliffords)
}


def _default_generalizer(bloq: Bloq) -> Bloq | None:
    """Compose the generalizers used for every call-graph traversal."""
    for g in (cirq_to_bloqs, generalize_rotation_angle, ignore_split_join):
        bloq = g(bloq)
        if bloq is None:
            return None
    return bloq


def _magic_state_counts(gates) -> tuple[int, int]:
    """Return ``(raw_t, ccz_count)`` from a Qualtran ``GateCounts``.

    Magic-state and rotation conventions: ASSUMPTIONS.md §3.
    """
    counts = gates.total_t_and_ccz_count(ts_per_rotation=0)
    return int(counts["n_t"]), int(counts["n_ccz"])


def _leaf_gate_costs(leaf: Bloq) -> tuple[int, int, int, int]:
    """Return ``(raw_t, ccz_count, rotations, cliffords)`` for a leaf.

    Checks ``_COST_OVERRIDES`` first, then ``QECGatesCost``; zeros on failure.
    """
    override = _COST_OVERRIDES.get(type(leaf).__name__)
    if override is not None:
        return override
    try:
        gates = get_cost_value(leaf, QECGatesCost())
        raw_t, ccz = _magic_state_counts(gates)
        return (raw_t, ccz, int(gates.rotation), int(gates.clifford))
    except Exception:
        return 0, 0, 0, 0


def _extract_via_call_graph(bloq: Bloq) -> tuple[int, int, int, int]:
    """Sum ``(raw_t, ccz_count, rotation_count, clifford_count)`` over the
    call-graph leaves. Raises on failure so the caller can fall back."""
    _, sigma = bloq.call_graph(
        generalizer=_default_generalizer,
        max_depth=_CALL_GRAPH_MAX_DEPTH,
    )

    raw_t = 0
    ccz_count = 0
    rotation_count = 0
    clifford_count = 0

    for leaf, count in sigma.items():
        n = int(count)
        t, a, r, c = _leaf_gate_costs(leaf)
        raw_t += n * t
        ccz_count += n * a
        rotation_count += n * r
        clifford_count += n * c

    return raw_t, ccz_count, rotation_count, clifford_count


def _is_nontrivial(raw_t: int, ccz: int, rot: int, cliff: int) -> bool:
    return (raw_t + ccz + rot + cliff) > 0


def _has_nonclifford(raw_t: int, ccz: int, rot: int, cliff: int) -> bool:
    return (raw_t + ccz + rot) > 0


def _try_extract_gates(bloq: Bloq) -> tuple[int, int, int, int, int]:
    """Extract at progressively greater depth until the costs are non-zero.

    Returns ``(raw_t, ccz_count, rotation_count, clifford_count, qubits)``.
    A Clifford-only result does not stop the ladder: ``ApproximateQFT`` hides
    Toffolis inside ``AddIntoPhaseGrad`` that top-level ``QECGatesCost`` does
    not see. The qubit count falls back to the decomposed bloq when the
    top-level count is zero.
    """
    qubits = get_cost_value(bloq, QubitCount())

    # Merged with non-Clifford costs if a deeper strategy finds any.
    clifford_fallback: tuple[int, int, int, int] | None = None

    # 1. QECGatesCost on the top-level bloq.
    try:
        gates = get_cost_value(bloq, QECGatesCost())
        raw_t, ccz = _magic_state_counts(gates)
        vals = (raw_t, ccz, int(gates.rotation), int(gates.clifford))
        if _is_nontrivial(*vals):
            if _has_nonclifford(*vals):
                return (*vals, int(qubits))
            clifford_fallback = vals
    except Exception:
        pass

    # 2. One level of decomposition.
    try:
        decomposed = bloq.decompose_bloq()
        gates = get_cost_value(decomposed, QECGatesCost())
        raw_t, ccz = _magic_state_counts(gates)
        vals = (raw_t, ccz, int(gates.rotation), int(gates.clifford))
        if _is_nontrivial(*vals):
            q = get_cost_value(decomposed, QubitCount()) if int(qubits) == 0 else qubits
            if _has_nonclifford(*vals):
                return (*vals, int(q))
            if clifford_fallback is None:
                clifford_fallback = vals
    except Exception:
        pass

    # 3. call_graph leaf aggregation, for deeply nested bloqs.
    try:
        vals = _extract_via_call_graph(bloq)
        if _is_nontrivial(*vals):
            if clifford_fallback is not None and not _has_nonclifford(
                *clifford_fallback
            ):
                merged_cliff = max(vals[3], clifford_fallback[3])
                return (vals[0], vals[1], vals[2], merged_cliff, int(qubits))
            return (*vals, int(qubits))
    except Exception:
        pass

    if clifford_fallback is not None:
        return (*clifford_fallback, int(qubits))

    return 0, 0, 0, 0, int(qubits)


def extract_logical_costs(
    bloq: Bloq,
    *,
    rotation_synthesis_epsilon: float | None = None,
) -> LogicalCosts:
    """Qubit count and gate costs for *bloq*.

    *rotation_synthesis_epsilon* defaults to ``DEFAULT_CONFIG``; pass 0 or a
    negative value to skip synthesis costing. Extraction ladder:
    :func:`_try_extract_gates`.
    """
    if rotation_synthesis_epsilon is None:
        rotation_synthesis_epsilon = (
            DEFAULT_CONFIG.surface_code.rotation_synthesis_epsilon
        )

    raw_t, ccz_count, rotation_count, clifford_count, qubits = _try_extract_gates(bloq)

    t_count_direct = raw_t + 4 * ccz_count

    if rotation_synthesis_epsilon and rotation_count > 0:
        t_per_rot = rotation_synthesis_t_cost(rotation_synthesis_epsilon)
        t_count_ftqc = t_count_direct + rotation_count * t_per_rot
    else:
        t_count_ftqc = t_count_direct

    return LogicalCosts(
        logical_qubits_estimate=qubits,
        t_count_direct=t_count_direct,
        t_count_ftqc=t_count_ftqc,
        raw_t=raw_t,
        magic_state_count=ccz_count,
        clifford_count=clifford_count,
        rotation_count=rotation_count,
        rotation_synthesis_epsilon=rotation_synthesis_epsilon,
    )

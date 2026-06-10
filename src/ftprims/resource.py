"""Resource estimation — logical costs and physical delegation.

Logical costs are extracted from Qualtran's ``QECGatesCost``, keeping
the raw-T / CCZ (And) breakdown so that downstream consumers get the
correct separated values.

The FTQC T-count additionally includes the cost of compiling arbitrary
rotations via the Ross-Selinger (Gridsynth) model.

Physical estimation is delegated to ``ftprims.physical``.
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

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts
from ftprims.config import DEFAULT_CONFIG, SurfaceCodeConfig


def rotation_synthesis_t_cost(epsilon: float) -> int:
    """T-gates needed to synthesise one arbitrary rotation to precision *ε*.

    Uses the Ross-Selinger / Gridsynth approximation for ancilla-free
    Clifford+T synthesis:

        T ≈ 3·log₂(1/ε)

    This is the dominant term from Theorem 1.1 of Ross & Selinger
    (arXiv:1403.2975). The full bound is 3·log₂(1/ε) + O(log log(1/ε));
    the sub-leading term is omitted here.

    Returns 0 when *epsilon* is non-positive (meaning "skip synthesis").
    """
    if epsilon <= 0:
        return 0
    return math.ceil(3.0 * math.log2(1.0 / epsilon))


_CALL_GRAPH_MAX_DEPTH = 4

# Bloqs whose QECGatesCost returns zero but have known non-trivial cost.
_COST_OVERRIDES: dict[str, tuple[int, int, int, int]] = {
    "Toffoli": (0, 1, 0, 0),  # (raw_t, and_count, rotations, cliffords)
}


def _default_generalizer(bloq: Bloq) -> Bloq | None:
    """Compose the standard generalizers for call-graph traversal."""
    for g in (cirq_to_bloqs, generalize_rotation_angle, ignore_split_join):
        bloq = g(bloq)
        if bloq is None:
            return None
    return bloq


def _leaf_gate_costs(leaf: Bloq) -> tuple[int, int, int, int]:
    """Return ``(raw_t, and_count, rotations, cliffords)`` for a leaf.

    Checks hardcoded overrides first, then falls back to
    ``QECGatesCost``. Returns all zeros on failure.
    """
    override = _COST_OVERRIDES.get(type(leaf).__name__)
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


def _extract_via_call_graph(bloq: Bloq) -> tuple[int, int, int, int]:
    """Sum gate costs over the call-graph leaves.

    Returns ``(raw_t, ccz_count, rotation_count, clifford_count)``.
    Raises on failure so the caller can fall back to zeros.
    """
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
    """True when the costs include at least one non-Clifford gate."""
    return (raw_t + ccz + rot) > 0


def _try_extract_gates(bloq: Bloq) -> tuple[int, int, int, int, int]:
    """Try progressively deeper extraction until we get non-zero costs.

    Returns ``(raw_t, ccz_count, rotation_count, clifford_count, qubits)``.
    The qubit count is updated from a decomposed bloq when the
    top-level returns zero.

    When an early strategy returns only Clifford costs (no T-gates,
    CCZ, or rotations), extraction continues to deeper strategies
    that may uncover non-Clifford costs hidden in sub-bloqs — e.g.
    ``ApproximateQFT`` where Toffoli gates inside
    ``AddIntoPhaseGrad`` are invisible to top-level ``QECGatesCost``.
    """
    qubits = get_cost_value(bloq, QubitCount())

    # Stash the first Clifford-only result so we can merge it with
    # non-Clifford costs found by a deeper strategy.
    clifford_fallback: tuple[int, int, int, int] | None = None

    # Strategy 1: QECGatesCost on the top-level bloq.
    try:
        gates = get_cost_value(bloq, QECGatesCost())
        vals = (
            int(gates.t),
            int(gates.and_bloq),
            int(gates.rotation),
            int(gates.clifford),
        )
        if _is_nontrivial(*vals):
            if _has_nonclifford(*vals):
                return (*vals, int(qubits))
            clifford_fallback = vals
    except Exception:
        pass

    # Strategy 2: one level of decomposition.
    try:
        decomposed = bloq.decompose_bloq()
        gates = get_cost_value(decomposed, QECGatesCost())
        vals = (
            int(gates.t),
            int(gates.and_bloq),
            int(gates.rotation),
            int(gates.clifford),
        )
        if _is_nontrivial(*vals):
            q = get_cost_value(decomposed, QubitCount()) if int(qubits) == 0 else qubits
            if _has_nonclifford(*vals):
                return (*vals, int(q))
            if clifford_fallback is None:
                clifford_fallback = vals
    except Exception:
        pass

    # Strategy 3: call_graph leaf aggregation (handles Product,
    # ApproximateQFT, and other deeply-nested bloqs).
    try:
        vals = _extract_via_call_graph(bloq)
        if _is_nontrivial(*vals):
            if clifford_fallback is not None and not _has_nonclifford(
                *clifford_fallback
            ):
                # Merge: non-Clifford from call_graph, best Clifford from either.
                merged_cliff = max(vals[3], clifford_fallback[3])
                return (vals[0], vals[1], vals[2], merged_cliff, int(qubits))
            return (*vals, int(qubits))
    except Exception:
        pass

    # Only Cliffords found — return that rather than zeros.
    if clifford_fallback is not None:
        return (*clifford_fallback, int(qubits))

    return 0, 0, 0, 0, int(qubits)


def extract_logical_costs(
    bloq: Bloq,
    *,
    rotation_synthesis_epsilon: float | None = None,
) -> LogicalCosts:
    """Pull qubit count and gate costs from a Qualtran Bloq.

    Extraction strategy (first non-zero result wins):
      1. ``QECGatesCost`` on the top-level bloq.
      2. ``QECGatesCost`` after one level of ``decompose_bloq()``.
      3. Leaf-level aggregation via ``call_graph`` — handles bloqs
         like ``Product`` and ``ApproximateQFT`` whose costs only
         emerge after deep decomposition.

    Parameters
    ----------
    bloq:
        The bloq to analyse.
    rotation_synthesis_epsilon:
        Precision for rotation synthesis. When ``None`` the default
        from ``DEFAULT_CONFIG`` is used. Pass ``0`` or a negative
        value to skip synthesis costing entirely.
    """
    if rotation_synthesis_epsilon is None:
        rotation_synthesis_epsilon = (
            DEFAULT_CONFIG.surface_code.rotation_synthesis_epsilon
        )

    raw_t, ccz_count, rotation_count, clifford_count, qubits = _try_extract_gates(bloq)

    t_count_direct = raw_t + 4 * ccz_count

    # FTQC total: direct T-gates + synthesised rotations.
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
        and_count=ccz_count,
        clifford_count=clifford_count,
        rotation_count=rotation_count,
        rotation_synthesis_epsilon=rotation_synthesis_epsilon,
    )


def estimate_physical(
    bloq: Bloq | None = None,
    logical: LogicalCosts | None = None,
    *,
    cfg: SurfaceCodeConfig | None = None,
) -> PhysicalCosts:
    """Estimate physical costs using the surface-code model.

    This is a backward-compatible wrapper. For full control over
    profile, data block, and factory variants, use
    ``ftprims.physical.estimate_physical`` with a ``PhysicalModelSpec``.

    Parameters
    ----------
    bloq:
        If provided, logical costs are extracted first.
    logical:
        Pre-computed logical costs. At least one of *bloq* or
        *logical* must be given.
    cfg:
        Legacy surface-code config. Falls back to ``DEFAULT_CONFIG``.
    """
    from ftprims.physical import PhysicalModelSpec
    from ftprims.physical import estimate_physical as _estimate

    if bloq is None and logical is None:
        raise ValueError("Provide at least one of bloq or logical")

    if logical is None:
        assert bloq is not None
        logical = extract_logical_costs(bloq)

    cfg = cfg or DEFAULT_CONFIG.surface_code

    spec = PhysicalModelSpec(
        data_d=cfg.data_d,
        error_budget=cfg.error_budget,
        physical_error=cfg.physical_error,
        cycle_time_us=cfg.cycle_time_us,
    )

    return _estimate(logical, spec=spec)

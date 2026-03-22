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

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts
from ftprims.config import DEFAULT_CONFIG, SurfaceCodeConfig


def rotation_synthesis_t_cost(epsilon: float) -> int:
    """T-gates needed to synthesise one arbitrary rotation to precision *ε*.

    Uses the Ross-Selinger / Gridsynth approximation:

        T ≈ 1.149·log₂(1/ε) + 9.2

    Returns 0 when *epsilon* is non-positive (meaning "skip synthesis").
    """
    if epsilon <= 0:
        return 0
    return math.ceil(1.149 * math.log2(1.0 / epsilon) + 9.2)


def extract_logical_costs(
    bloq: Bloq,
    *,
    rotation_synthesis_epsilon: float | None = None,
) -> LogicalCosts:
    """Pull qubit count and gate costs from a Qualtran Bloq.

    Parameters
    ----------
    bloq:
        The bloq to analyse.
    rotation_synthesis_epsilon:
        Precision for rotation synthesis.  When ``None`` the default
        from ``DEFAULT_CONFIG`` is used.  Pass ``0`` or a negative
        value to skip synthesis costing entirely.
    """
    if rotation_synthesis_epsilon is None:
        rotation_synthesis_epsilon = (
            DEFAULT_CONFIG.surface_code.rotation_synthesis_epsilon
        )

    qubits = get_cost_value(bloq, QubitCount())
    gates = get_cost_value(bloq, QECGatesCost())

    raw_t = int(gates.t)
    ccz_count = int(gates.and_bloq)
    rotation_count = int(gates.rotation)
    clifford_count = int(gates.clifford)

    t_count_direct = raw_t + 4 * ccz_count

    # FTQC total: direct T-gates + synthesised rotations.
    if rotation_synthesis_epsilon and rotation_count > 0:
        t_per_rot = rotation_synthesis_t_cost(rotation_synthesis_epsilon)
        t_count_ftqc = t_count_direct + rotation_count * t_per_rot
    else:
        t_count_ftqc = t_count_direct

    return LogicalCosts(
        logical_qubits_estimate=int(qubits),
        t_count_direct=t_count_direct,
        t_count_ftqc=t_count_ftqc,
        raw_t=raw_t,
        ccz_count=ccz_count,
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

    This is a backward-compatible wrapper.  For full control over
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

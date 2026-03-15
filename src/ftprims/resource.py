"""Resource estimation — logical & physical layers.

Logical costs are extracted from Qualtran's ``QECGatesCost``, keeping
the raw-T / CCZ (And) breakdown so that downstream consumers get the
correct separated values.

The FTQC T-count additionally includes the cost of compiling arbitrary
rotations via the Ross-Selinger (Gridsynth) model.

Physical costs use the Gidney-Fowler surface-code model. When a Bloq
is available the estimator calls ``AlgorithmSummary.from_bloq``;
otherwise it falls back to a manual ``AlgorithmSummary`` constructed
from ``LogicalCosts``.
"""

from __future__ import annotations

import math

from qualtran import Bloq
from qualtran.resource_counting import (
    QECGatesCost,
    QubitCount,
    get_cost_value,
)
from qualtran.surface_code import (
    AlgorithmSummary,
    CCZ2TFactory,
    PhysicalCostModel,
    PhysicalParameters,
    QECScheme,
    SimpleDataBlock,
)

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts
from ftprims.config import DEFAULT_CONFIG, SurfaceCodeConfig


# ── Rotation synthesis cost ──────────────────────────────────────────


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
    ccz_count = int(gates.and_bloq)  # And bloqs, each ~ 4 T
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
        qubits=int(qubits),
        t_count_direct=t_count_direct,
        t_count_ftqc=t_count_ftqc,
        raw_t=raw_t,
        ccz_count=ccz_count,
        clifford_count=clifford_count,
        rotation_count=rotation_count,
        rotation_synthesis_epsilon=rotation_synthesis_epsilon,
    )


def _build_physical_model(
    data_d: int,
    cfg: SurfaceCodeConfig,
) -> PhysicalCostModel:
    """Construct an explicit ``PhysicalCostModel`` from config parameters.

    Mirrors the reference notebook construction instead of relying on
    ``make_gidney_fowler`` (whose hidden defaults may diverge).
    """
    return PhysicalCostModel(
        physical_params=PhysicalParameters(
            physical_error=cfg.physical_error,
            cycle_time_us=cfg.cycle_time_us,
        ),
        data_block=SimpleDataBlock(
            data_d=data_d,
            routing_overhead=cfg.routing_overhead,
        ),
        factory=CCZ2TFactory(),
        qec_scheme=QECScheme(
            error_rate_scaler=cfg.error_rate_scaler,
            error_rate_threshold=cfg.error_rate_threshold,
        ),
    )


def _physical_from_model(
    model: PhysicalCostModel,
    summary: AlgorithmSummary,
    data_d: int,
    error_budget: float,
) -> PhysicalCosts:
    return PhysicalCosts(
        physical_qubits=model.n_phys_qubits(summary),
        wall_time_us=model.duration_hr(summary) * 3_600_000_000,
        code_distance=data_d,
        error_budget=error_budget,
    )


def estimate_physical(
    bloq: Bloq | None = None,
    logical: LogicalCosts | None = None,
    *,
    cfg: SurfaceCodeConfig | None = None,
) -> PhysicalCosts:
    """Estimate physical costs using the surface-code model.

    Parameters
    ----------
    bloq:
        If provided, ``AlgorithmSummary.from_bloq`` is used.
    logical:
        Fallback when no *bloq* is available. At least one of *bloq*
        or *logical* must be given.
    cfg:
        Surface-code parameters.  Falls back to ``DEFAULT_CONFIG``.
    """
    if bloq is None and logical is None:
        raise ValueError("Provide at least one of bloq or logical")

    cfg = cfg or DEFAULT_CONFIG.surface_code

    # Build the AlgorithmSummary when a bloq is available;
    # otherwise reconstruct manually.
    if bloq is not None:
        summary = AlgorithmSummary.from_bloq(bloq)
    else:
        assert logical is not None
        summary = AlgorithmSummary(
            n_algo_qubits=logical.qubits,
            # Pass separated counts - do NOT feed t_equivalent into
            # GateCounts.t; that would double-count CCZ.
            n_logical_gates=summary_gate_counts(logical),
        )

    # Fixed distance from config, or search for minimum.
    if cfg.data_d is not None:
        model = _build_physical_model(cfg.data_d, cfg)
        return _physical_from_model(model, summary, cfg.data_d, cfg.error_budget)

    # Auto-search: sweep odd distances until error <= budget.
    for d in range(3, 100, 2):
        model = _build_physical_model(d, cfg)
        if model.error(summary) <= cfg.error_budget:
            return _physical_from_model(model, summary, d, cfg.error_budget)

    # Fallback at d=99 for extremely tight budgets.
    model = _build_physical_model(99, cfg)
    return _physical_from_model(model, summary, 99, cfg.error_budget)


def summary_gate_counts(logical: LogicalCosts):
    """Build a ``GateCounts`` from separated logical cost fields."""
    from qualtran.resource_counting import GateCounts

    return GateCounts(
        t=logical.raw_t,
        and_bloq=logical.ccz_count,
        rotation=logical.rotation_count,
    )

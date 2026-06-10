"""Surface-code physical resource estimation layer.

Constructs ``PhysicalCostModel`` instances from a declarative
``PhysicalModelSpec`` and sweeps code distance to find the minimum
that satisfies the error budget.

Supported configurations:
    profiles:    gidney_fowler, beverland
    data_blocks: simple, compact, fast
    factories:   ccz2t, fifteen_to_one
"""

from __future__ import annotations

import warnings

import attrs
from qualtran.resource_counting import GateCounts
from qualtran.surface_code import (
    AlgorithmSummary,
    CCZ2TFactory,
    CompactDataBlock,
    FastDataBlock,
    FifteenToOne,
    PhysicalCostModel,
    PhysicalParameters,
    QECScheme,
    SimpleDataBlock,
)

from ftprims.algorithms._base import LogicalCosts, PhysicalCosts


_MAX_AUTO_DISTANCE = 99


@attrs.define(frozen=True)
class PhysicalModelSpec:
    """Declarative specification for a surface-code physical model.

    Provides named presets via *profile* while allowing per-parameter
    overrides. The ``data_d`` field pins the code distance; when
    ``None`` the estimator auto-searches for the minimum feasible
    distance.
    """

    profile: str = "gidney_fowler"
    data_block: str = "simple"
    factory: str = "ccz2t"
    data_d: int | None = None
    error_budget: float = 1e-3
    physical_error: float | None = None
    cycle_time_us: float | None = None


_PROFILES = ("gidney_fowler", "beverland")
_DATA_BLOCKS = ("simple", "compact", "fast")
_FACTORIES = ("ccz2t", "fifteen_to_one")


def make_qec_scheme(profile: str) -> QECScheme:
    """Return the QEC scheme for the named profile."""
    if profile == "gidney_fowler":
        return QECScheme.make_gidney_fowler()
    if profile == "beverland":
        return QECScheme.make_beverland_et_al()
    raise ValueError(f"Unknown profile {profile!r}; choose from {_PROFILES}")


def make_physical_params(
    profile: str,
    *,
    physical_error: float | None = None,
    cycle_time_us: float | None = None,
) -> PhysicalParameters:
    """Return physical parameters for the named profile.

    Explicit *physical_error* or *cycle_time_us* override the preset.
    """
    if profile == "gidney_fowler":
        base = PhysicalParameters.make_gidney_fowler()
    elif profile == "beverland":
        base = PhysicalParameters.make_beverland_et_al()
    else:
        raise ValueError(f"Unknown profile {profile!r}; choose from {_PROFILES}")

    if physical_error is not None or cycle_time_us is not None:
        return PhysicalParameters(
            physical_error=(
                physical_error if physical_error is not None else base.physical_error
            ),
            cycle_time_us=(
                cycle_time_us if cycle_time_us is not None else base.cycle_time_us
            ),
        )
    return base


def make_data_block(
    kind: str, data_d: int
) -> SimpleDataBlock | CompactDataBlock | FastDataBlock:
    """Construct a data block of the requested kind."""
    if kind == "simple":
        return SimpleDataBlock(data_d=data_d)
    if kind == "compact":
        return CompactDataBlock(data_d=data_d)
    if kind == "fast":
        return FastDataBlock(data_d=data_d)
    raise ValueError(f"Unknown data_block {kind!r}; choose from {_DATA_BLOCKS}")


def make_factory(kind: str, data_d: int) -> CCZ2TFactory | FifteenToOne:
    """Construct a magic-state factory of the requested kind."""
    if kind == "ccz2t":
        return CCZ2TFactory()
    if kind == "fifteen_to_one":
        return FifteenToOne(d_X=data_d, d_Z=data_d, d_m=data_d)
    raise ValueError(f"Unknown factory {kind!r}; choose from {_FACTORIES}")


def make_model(spec: PhysicalModelSpec, data_d: int) -> PhysicalCostModel:
    """Assemble a ``PhysicalCostModel`` from a spec at a given distance."""
    return PhysicalCostModel(
        qec_scheme=make_qec_scheme(spec.profile),
        physical_params=make_physical_params(
            spec.profile,
            physical_error=spec.physical_error,
            cycle_time_us=spec.cycle_time_us,
        ),
        data_block=make_data_block(spec.data_block, data_d),
        factory=make_factory(spec.factory, data_d),
    )


# ── Estimation ────────────────────────────────────────────────────────


def _algo_summary_from_logical(logical: LogicalCosts) -> AlgorithmSummary:
    """Build ``AlgorithmSummary`` from separated logical cost fields."""
    return AlgorithmSummary(
        n_algo_qubits=logical.logical_qubits_estimate,
        n_logical_gates=GateCounts(
            t=logical.raw_t,
            and_bloq=logical.and_count,
            rotation=logical.rotation_count,
        ),
    )


def estimate_physical(
    logical: LogicalCosts,
    *,
    spec: PhysicalModelSpec | None = None,
) -> PhysicalCosts:
    """Estimate physical costs for a surface-code deployment.

    Parameters
    ----------
    logical:
        Logical-level resource counts.
    spec:
        Physical model configuration. Uses default Gidney-Fowler
        preset when ``None``.

    Returns
    -------
    PhysicalCosts
        Always includes ``failure_prob`` and ``budget_satisfied``.
        When auto-search cannot meet the error budget, returns the
        best result at d=99 with ``budget_satisfied=False``.
    """
    spec = spec or PhysicalModelSpec()
    summary = _algo_summary_from_logical(logical)

    if spec.data_d is not None:
        return _evaluate(spec, summary, spec.data_d)

    # Auto-search: sweep odd distances until error ≤ budget.
    best: PhysicalCosts | None = None
    for d in range(3, _MAX_AUTO_DISTANCE + 1, 2):
        candidate = _evaluate(spec, summary, d)
        if candidate.budget_satisfied:
            return candidate
        best = candidate

    assert best is not None
    warnings.warn(
        f"Auto-search exhausted (d ≤ {_MAX_AUTO_DISTANCE}) without meeting "
        f"error_budget={spec.error_budget:.2e}. Returning result at "
        f"d={_MAX_AUTO_DISTANCE} with budget_satisfied=False.",
        stacklevel=2,
    )
    return best


def _evaluate(
    spec: PhysicalModelSpec,
    summary: AlgorithmSummary,
    data_d: int,
) -> PhysicalCosts:
    """Run the physical model at a single code distance."""
    model = make_model(spec, data_d)
    failure_prob = float(model.error(summary))
    return PhysicalCosts(
        physical_qubits=int(model.n_phys_qubits(summary)),
        wall_time_us=float(model.duration_hr(summary)) * 3_600_000_000,
        code_distance=data_d,
        error_budget=spec.error_budget,
        failure_prob=failure_prob,
        budget_satisfied=failure_prob <= spec.error_budget,
        profile=spec.profile,
        data_block=spec.data_block,
        factory=spec.factory,
    )

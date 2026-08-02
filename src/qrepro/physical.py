"""Surface-code physical resource estimation.

Builds ``PhysicalCostModel`` instances from a :class:`PhysicalModelSpec` and
sweeps code distance for the minimum that meets the error budget. Supported:
profiles ``gidney_fowler`` / ``beverland``, data blocks ``simple`` / ``compact``
/ ``fast``, factories ``ccz2t`` / ``fifteen_to_one``.
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
    get_ccz2t_costs_from_grid_search,
    iter_ccz2t_factories,
)

from qrepro.algorithms._base import LogicalCosts, PhysicalCosts

_MAX_AUTO_DISTANCE = 99


@attrs.define(frozen=True)
class PhysicalModelSpec:
    """Surface-code model configuration.

    *profile* names a preset; the remaining fields override it. ``data_d`` pins
    the code distance, or ``None`` to auto-search the minimum feasible one.
    """

    profile: str = "gidney_fowler"
    data_block: str = "simple"
    factory: str = "ccz2t"
    data_d: int | None = None
    error_budget: float = 1e-3
    physical_error: float | None = None
    cycle_time_us: float | None = None
    factory_l1_d: int | None = None
    factory_l2_d: int | None = None


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
    """Physical parameters for *profile*, with per-field overrides."""
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


def make_factory(
    kind: str,
    data_d: int,
    *,
    l1_d: int | None = None,
    l2_d: int | None = None,
) -> CCZ2TFactory | FifteenToOne:
    """Construct a magic-state factory of the requested kind.

    ``data_d`` applies to ``fifteen_to_one`` only; the CCZ2T factory's
    distillation distances are independent of the data-block distance. Unset
    ``l1_d`` / ``l2_d`` gives Qualtran's default (15, 31); :func:`estimate_physical`
    searches them instead.
    """
    if kind == "ccz2t":
        if l1_d is not None and l2_d is not None:
            return CCZ2TFactory(distillation_l1_d=l1_d, distillation_l2_d=l2_d)
        return CCZ2TFactory()
    if kind == "fifteen_to_one":
        return FifteenToOne(d_X=data_d, d_Z=data_d, d_m=data_d)
    raise ValueError(f"Unknown factory {kind!r}; choose from {_FACTORIES}")


def make_model(
    spec: PhysicalModelSpec,
    data_d: int,
    *,
    l1_d: int | None = None,
    l2_d: int | None = None,
) -> PhysicalCostModel:
    """Assemble a ``PhysicalCostModel`` from *spec* at code distance *data_d*.

    *l1_d* / *l2_d* override ``spec.factory_l1_d`` / ``spec.factory_l2_d``, as
    the distillation-distance search in :func:`_evaluate` does.
    """
    return PhysicalCostModel(
        qec_scheme=make_qec_scheme(spec.profile),
        physical_params=make_physical_params(
            spec.profile,
            physical_error=spec.physical_error,
            cycle_time_us=spec.cycle_time_us,
        ),
        data_block=make_data_block(spec.data_block, data_d),
        factory=make_factory(
            spec.factory,
            data_d,
            l1_d=spec.factory_l1_d if l1_d is None else l1_d,
            l2_d=spec.factory_l2_d if l2_d is None else l2_d,
        ),
    )


def _algo_summary_from_logical(logical: LogicalCosts) -> AlgorithmSummary:
    """Build ``AlgorithmSummary`` from separated logical cost fields."""
    return AlgorithmSummary(
        n_algo_qubits=logical.logical_qubits_estimate,
        n_logical_gates=GateCounts(
            t=logical.raw_t,
            and_bloq=logical.magic_state_count,
            rotation=logical.rotation_count,
        ),
    )


def estimate_physical(
    logical: LogicalCosts,
    *,
    spec: PhysicalModelSpec | None = None,
) -> PhysicalCosts:
    """Estimate physical costs for a surface-code deployment.

    *spec* defaults to the Gidney-Fowler preset. The result always carries
    ``failure_prob`` and ``budget_satisfied``; when the auto-search cannot meet
    the budget it returns the d=99 result with ``budget_satisfied=False``.
    """
    spec = spec or PhysicalModelSpec()
    summary = _algo_summary_from_logical(logical)

    if spec.data_d is not None:
        return _evaluate(spec, summary, spec.data_d)

    # Sweep odd distances until failure_prob <= budget.
    best: PhysicalCosts | None = None
    for d in range(3, _MAX_AUTO_DISTANCE + 1, 2):
        candidate = _evaluate(spec, summary, d)
        if candidate.budget_satisfied:
            return candidate
        best = candidate

    assert best is not None
    warnings.warn(
        f"Auto-search exhausted (d <= {_MAX_AUTO_DISTANCE}) without meeting "
        f"error_budget={spec.error_budget:.2e}. Returning result at "
        f"d={_MAX_AUTO_DISTANCE} with budget_satisfied=False.",
        stacklevel=2,
    )
    return best


def _evaluate_at(
    spec: PhysicalModelSpec,
    summary: AlgorithmSummary,
    data_d: int,
    l1_d: int | None,
    l2_d: int | None,
) -> PhysicalCosts:
    """Run the physical model at one (data_d, l1_d, l2_d) point."""
    model = make_model(spec, data_d, l1_d=l1_d, l2_d=l2_d)
    failure_prob = float(model.error(summary))
    factory = model.factory
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
        factory_l1_d=getattr(factory, "distillation_l1_d", None),
        factory_l2_d=getattr(factory, "distillation_l2_d", None),
        n_factories=1,
    )


def _evaluate(
    spec: PhysicalModelSpec,
    summary: AlgorithmSummary,
    data_d: int,
) -> PhysicalCosts:
    """Run the model at *data_d*, searching CCZ2T distillation distances.

    Returns the smallest-footprint factory meeting the error budget, or the
    lowest achieved failure probability when none does.
    """
    pinned = spec.factory_l1_d is not None and spec.factory_l2_d is not None
    if spec.factory != "ccz2t" or pinned:
        return _evaluate_at(spec, summary, data_d, spec.factory_l1_d, spec.factory_l2_d)

    best: PhysicalCosts | None = None
    best_unsatisfied: PhysicalCosts | None = None
    for factory in iter_ccz2t_factories():
        candidate = _evaluate_at(
            spec,
            summary,
            data_d,
            factory.distillation_l1_d,
            factory.distillation_l2_d,
        )
        if candidate.budget_satisfied:
            if best is None or candidate.physical_qubits < best.physical_qubits:
                best = candidate
        elif best_unsatisfied is None or (
            candidate.failure_prob < best_unsatisfied.failure_prob
        ):
            best_unsatisfied = candidate

    assert best is not None or best_unsatisfied is not None
    return best if best is not None else best_unsatisfied  # type: ignore[return-value]


def estimate_physical_grid_search(
    logical: LogicalCosts,
    *,
    n_factories: int = 1,
    error_budget: float = 0.01,
    phys_err: float = 1e-3,
    cycle_time_us: float = 1.0,
) -> PhysicalCosts:
    """Estimate physical costs via Qualtran's CCZ2T grid search.

    Wraps ``get_ccz2t_costs_from_grid_search`` with
    ``iter_ccz2t_factories(n_factories=N)``, co-optimising *n_factories*
    parallel factories against the data block. :func:`estimate_physical` uses a
    single ``CCZ2TFactory`` and so covers only the distillation-limited row.

    ``logical.magic_state_count`` drives the gate budget and
    ``logical.logical_qubits_estimate`` sets ``n_algo_qubits``. *phys_err* is the
    physical gate error rate, *cycle_time_us* the surface-code cycle time.
    """
    if n_factories < 1:
        raise ValueError(f"n_factories must be >= 1, got {n_factories}")

    # 4 T = 1 Toffoli, so the single-number grid search sees the full
    # non-Clifford cost.
    toffoli_equiv = logical.magic_state_count + logical.raw_t // 4
    summary, factory, data_block = get_ccz2t_costs_from_grid_search(
        n_logical_gates=GateCounts(toffoli=toffoli_equiv),
        n_algo_qubits=int(logical.logical_qubits_estimate),
        phys_err=phys_err,
        error_budget=error_budget,
        cycle_time_us=cycle_time_us,
        factory_iter=list(iter_ccz2t_factories(n_factories=n_factories)),
    )
    failure_prob = float(summary.failure_prob)
    base = getattr(factory, "base_factory", factory)
    return PhysicalCosts(
        physical_qubits=int(summary.footprint),
        wall_time_us=float(summary.duration_hr) * 3_600_000_000,
        code_distance=int(data_block.data_d),
        error_budget=error_budget,
        failure_prob=failure_prob,
        budget_satisfied=failure_prob <= error_budget,
        profile="gidney_fowler",
        data_block="simple",
        factory="ccz2t",
        factory_l1_d=getattr(base, "distillation_l1_d", None),
        factory_l2_d=getattr(base, "distillation_l2_d", None),
        n_factories=n_factories,
    )

"""Integration tests: building bloqs and running the full extraction pipeline."""

from __future__ import annotations

from typing import NamedTuple

import pytest

from qrepro.algorithms import registry
from qrepro.breakdown import extract_structural_breakdown, summarize_breakdown
from qrepro.physical import PhysicalModelSpec, estimate_physical


class Case(NamedTuple):
    """A pinned known-good benchmark case.

    Each test asserts the fields it is about; grouping them in one record keeps
    the parametrisation from carrying values a test never looks at.
    """

    name: str
    params: dict
    t_direct: int
    t_ftqc: int
    qubits: int
    rotations: int
    dominant: str

    @property
    def id(self) -> str:
        return f"{self.name}_{'_'.join(str(v) for v in self.params.values())}"


REFERENCE_CASES = [
    Case("qft", dict(n=32, variant="textbook"), 2014, 45514, 33, 435, "rotations"),
    Case(
        "qft", dict(n=32, variant="approx"), 2632, 2632, 48, 0, "controlled_nonclifford"
    ),
    Case("qft", dict(n=8, variant="approx"), 88, 88, 12, 0, "controlled_nonclifford"),
    Case("qpe", dict(m=8, phi=0.25), 1138, 2638, 10, 15, "qft_qpe_core"),
    Case("arithmetic", dict(n=16, op="add"), 60, 60, 47, 0, "controlled_nonclifford"),
    Case(
        "arithmetic", dict(n=16, op="add_oop"), 64, 64, 49, 0, "controlled_nonclifford"
    ),
    Case("arithmetic", dict(n=16, op="leq"), 124, 124, 80, 0, "arithmetic_core"),
    Case(
        "arithmetic", dict(n=16, op="mul"), 1984, 1984, 64, 0, "controlled_nonclifford"
    ),
    Case("arithmetic", dict(n=8, op="modadd"), 124, 124, 34, 0, "arithmetic_core"),
    Case(
        "qrom",
        dict(data_size=256, variant="basic"),
        1012,
        1012,
        23,
        0,
        "controlled_nonclifford",
    ),
    Case(
        "qrom", dict(data_size=256, variant="selectswap"), 880, 880, 53, 0, "qrom_core"
    ),
]

_REF_IDS = [c.id for c in REFERENCE_CASES]

PHYSICAL_CASES = [
    ("qft", dict(n=32, variant="textbook")),
    ("qft", dict(n=32, variant="approx")),
    ("qpe", dict(m=8, phi=0.25)),
    ("arithmetic", dict(n=16, op="add")),
    ("arithmetic", dict(n=16, op="mul")),
    ("qrom", dict(data_size=256, variant="basic")),
]

VERIFY_CASES = [
    ("qft", dict(n=4, variant="textbook")),
    ("qft", dict(n=4, variant="approx")),
    ("arithmetic", dict(n=4, op="add")),
    ("arithmetic", dict(n=4, op="add_oop")),
    ("arithmetic", dict(n=4, op="leq")),
    ("arithmetic", dict(n=4, op="modadd")),
    ("qrom", dict(data_size=8, target_bitsize=4, variant="basic")),
    ("qrom", dict(data_size=8, target_bitsize=4, variant="selectswap")),
]


def _pair_id(pair) -> str:
    name, params = pair
    return f"{name}_{'_'.join(str(v) for v in params.values())}"


# ── Logical costs ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize("case", REFERENCE_CASES, ids=_REF_IDS)
def test_logical_costs_match_reference(case):
    """Logical costs must match pinned known-good values.

    These are what *our code* computes against the pinned Qualtran, so a
    dependency bump that moves any of them has to surface here.
    """
    bench = registry[case.name]
    costs = bench.logical_costs(bench.build_bloq(**case.params))

    assert costs.t_count_direct == case.t_direct, (
        f"t_count_direct: {costs.t_count_direct} != {case.t_direct}"
    )
    assert costs.t_count_ftqc == case.t_ftqc, (
        f"t_count_ftqc: {costs.t_count_ftqc} != {case.t_ftqc}"
    )
    assert costs.logical_qubits_estimate == case.qubits, (
        f"qubits: {costs.logical_qubits_estimate} != {case.qubits}"
    )
    assert costs.rotation_count == case.rotations, (
        f"rotation_count: {costs.rotation_count} != {case.rotations}"
    )


@pytest.mark.parametrize("case", REFERENCE_CASES, ids=_REF_IDS)
def test_logical_breakdown_consistency(case):
    """Logical t_count_ftqc must agree with the sum of breakdown est_t_ftqc.

    Two independent extraction paths over the same bloq; they diverge when one
    misses non-Clifford cost hidden below the top level.
    """
    bench = registry[case.name]
    bloq = bench.build_bloq(**case.params)
    costs = bench.logical_costs(bloq)
    items = extract_structural_breakdown(bloq)
    breakdown_total = sum(i.est_t_ftqc for i in items)

    denom = max(costs.t_count_ftqc, breakdown_total, 1)
    delta = abs(costs.t_count_ftqc - breakdown_total) / denom

    assert delta < 0.01, (
        f"logical t_count_ftqc={costs.t_count_ftqc:,} vs "
        f"breakdown total={breakdown_total:,} (delta={delta:.1%})"
    )


@pytest.mark.parametrize("case", REFERENCE_CASES, ids=_REF_IDS)
def test_breakdown_dominant_component(case):
    """Breakdown must identify the correct dominant cost component.

    Catches misclassification like AddIntoPhaseGrad tagged as "rotations"
    when it is actually controlled_nonclifford.
    """
    bench = registry[case.name]
    items = extract_structural_breakdown(bench.build_bloq(**case.params))
    summary = summarize_breakdown(items)

    if sum(i.est_t_ftqc for i in items) == 0:
        pytest.skip("total FTQC cost is 0 — dominant label undefined")

    assert summary["dominant_component"] == case.dominant, (
        f"dominant: {summary['dominant_component']} != {case.dominant}"
    )


# ── Physical layer ────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "name,params", PHYSICAL_CASES, ids=map(_pair_id, PHYSICAL_CASES)
)
def test_physical_estimation_sane(name, params):
    """Physical estimates must be positive and meet the error budget.

    A zero wall_time with the floor code distance means the logical costs
    reaching the physical layer were empty.
    """
    bench = registry[name]
    costs = bench.logical_costs(bench.build_bloq(**params))

    if costs.t_count_ftqc == 0 and costs.rotation_count == 0:
        pytest.skip("zero non-Clifford cost")

    phys = estimate_physical(costs)

    assert phys.wall_time_us > 0, "wall_time_us must be > 0"
    assert phys.code_distance >= 3, "code_distance must be >= 3"
    assert phys.budget_satisfied, (
        f"error budget not met: failure_prob={phys.failure_prob:.2e} "
        f"> {phys.error_budget:.2e}"
    )


@pytest.mark.parametrize(
    "profile,factory",
    [
        ("gidney_fowler", "ccz2t"),
        ("gidney_fowler", "fifteen_to_one"),
        ("beverland", "ccz2t"),
        ("beverland", "fifteen_to_one"),
    ],
)
def test_physical_profiles_all_satisfy_budget(profile, factory):
    """Every supported physical config must satisfy the error budget for
    a standard workload (QFT textbook n=16)."""
    bench = registry["qft"]
    costs = bench.logical_costs(bench.build_bloq(n=16, variant="textbook"))
    phys = estimate_physical(
        costs, spec=PhysicalModelSpec(profile=profile, factory=factory)
    )

    assert phys.budget_satisfied, (
        f"{profile}/{factory}: budget not satisfied "
        f"(failure_prob={phys.failure_prob:.2e})"
    )
    assert phys.wall_time_us > 0


def test_ccz2t_distillation_distances_are_searched():
    """estimate_physical must search CCZ2T distillation distances, not accept
    Qualtran's construction default (15, 31).

    On QFT n=32 textbook the default costs 184,004 physical qubits against the
    search's (13, 17) at 119,492, a 35% difference. The selected distances are
    recorded on the result.
    """
    bench = registry["qft"]
    costs = bench.logical_costs(bench.build_bloq(n=32, variant="textbook"))

    searched = estimate_physical(costs)
    pinned = estimate_physical(
        costs, spec=PhysicalModelSpec(factory_l1_d=15, factory_l2_d=31)
    )

    assert pinned.factory_l1_d == 15 and pinned.factory_l2_d == 31, (
        "explicit distances must be honoured, not overridden by the search"
    )
    assert searched.factory_l1_d is not None and searched.factory_l2_d is not None, (
        "the search must record which factory it chose"
    )
    assert searched.budget_satisfied
    assert searched.physical_qubits < pinned.physical_qubits, (
        f"search={searched.physical_qubits:,} did not beat "
        f"default(15,31)={pinned.physical_qubits:,}"
    )


# ── Correctness and scaling ───────────────────────────────────────────────────


@pytest.mark.parametrize("name,params", VERIFY_CASES, ids=map(_pair_id, VERIFY_CASES))
def test_verify_small_passes(name, params):
    """Small-scale Cirq/classical verification must pass (not fail or error)."""
    bench = registry[name]
    result = bench.verify_small(**params)
    assert result.status in ("pass", "skip"), f"verify_small failed: {result.detail}"
    if result.status == "skip":
        pytest.skip(result.detail)


@pytest.mark.parametrize(
    "name,param_key,sizes,fixed",
    [
        ("qft", "n", [4, 8, 16, 32], dict(variant="textbook")),
        ("qft", "n", [8, 16, 32], dict(variant="approx")),
        ("arithmetic", "n", [8, 16, 32, 64], dict(op="add")),
        ("arithmetic", "n", [8, 16, 32, 64], dict(op="mul")),
        ("qrom", "data_size", [16, 64, 256], dict(variant="basic")),
        ("qrom", "data_size", [16, 64, 256], dict(variant="selectswap")),
    ],
    ids=[
        "qft_textbook_n",
        "qft_approx_n",
        "arith_add_n",
        "arith_mul_n",
        "qrom_basic_N",
        "qrom_selectswap_N",
    ],
)
def test_t_count_monotonic(name, param_key, sizes, fixed):
    """T-count must be non-decreasing as the problem size grows.

    Covers sizes outside the pinned reference table, where a Qualtran change
    would otherwise go unnoticed.
    """
    bench = registry[name]
    prev_t = -1
    for size in sizes:
        params = {param_key: size, **fixed}
        costs = bench.logical_costs(bench.build_bloq(**params))
        assert costs.t_count_ftqc >= prev_t, (
            f"{name}({params}): t_count_ftqc={costs.t_count_ftqc} < "
            f"previous={prev_t} — scaling not monotonic"
        )
        prev_t = costs.t_count_ftqc


def test_approx_qft_cheaper_than_textbook():
    """Approximate QFT must cost strictly less than textbook for n >= 8.

    The approximate variant truncates small-angle rotations, so the ratio is
    rotation-synthesis cost alone.
    """
    bench = registry["qft"]
    for n in [8, 16, 32, 64]:
        tb = bench.logical_costs(bench.build_bloq(n=n, variant="textbook"))
        ap = bench.logical_costs(bench.build_bloq(n=n, variant="approx"))
        assert ap.t_count_ftqc < tb.t_count_ftqc, (
            f"n={n}: approx T_ftqc={ap.t_count_ftqc} >= "
            f"textbook T_ftqc={tb.t_count_ftqc}"
        )


def test_selectswap_qrom_cheaper_at_large_n():
    """SelectSwapQROM must have fewer T-gates than basic QROM for large N."""
    bench = registry["qrom"]
    for data_size in [512, 1024]:
        basic = bench.logical_costs(
            bench.build_bloq(data_size=data_size, variant="basic")
        )
        swap = bench.logical_costs(
            bench.build_bloq(data_size=data_size, variant="selectswap")
        )
        assert swap.t_count_ftqc < basic.t_count_ftqc, (
            f"N={data_size}: selectswap T_ftqc={swap.t_count_ftqc} >= "
            f"basic T_ftqc={basic.t_count_ftqc}"
        )

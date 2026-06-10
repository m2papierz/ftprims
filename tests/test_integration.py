"""Integration tests: building bloqs and runs the full extraction pipeline."""

from __future__ import annotations

import pytest

from ftprims.algorithms import registry
from ftprims.breakdown import extract_structural_breakdown, summarize_breakdown
from ftprims.physical import PhysicalModelSpec, estimate_physical


# Known-good reference values
# Format: (primitive, params, t_direct, t_ftqc, qubits, rotation_count, dominant)
REFERENCE_CASES = [
    ("qft", dict(n=32, variant="textbook"), 2014, 45514, 33, 435, "rotations"),
    ("qft", dict(n=32, variant="approx"), 2632, 2632, 48, 0, "controlled_nonclifford"),
    ("qft", dict(n=8, variant="approx"), 88, 88, 12, 0, "controlled_nonclifford"),
    ("qpe", dict(m=8, phi=0.25), 1138, 2638, 10, 15, "qft_qpe_core"),
    ("arithmetic", dict(n=16, op="add"), 60, 60, 47, 0, "controlled_nonclifford"),
    ("arithmetic", dict(n=16, op="add_oop"), 64, 64, 49, 0, "controlled_nonclifford"),
    ("arithmetic", dict(n=16, op="leq"), 124, 124, 80, 0, "arithmetic_core"),
    ("arithmetic", dict(n=16, op="mul"), 1984, 1984, 64, 0, "controlled_nonclifford"),
    ("arithmetic", dict(n=8, op="modadd"), 124, 124, 34, 0, "arithmetic_core"),
    (
        "qrom",
        dict(data_size=256, variant="basic"),
        1012,
        1012,
        23,
        0,
        "controlled_nonclifford",
    ),
    ("qrom", dict(data_size=256, variant="selectswap"), 880, 880, 53, 0, "qrom_core"),
]


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


def _case_id(case):
    name, params = case[0], case[1]
    slug = "_".join(f"{v}" for v in params.values())
    return f"{name}_{slug}"


@pytest.mark.parametrize(
    "name,params,exp_direct,exp_ftqc,exp_qubits,exp_rot,exp_dom",
    REFERENCE_CASES,
    ids=[_case_id(c) for c in REFERENCE_CASES],
)
def test_logical_costs_match_reference(
    name,
    params,
    exp_direct,
    exp_ftqc,
    exp_qubits,
    exp_rot,
    exp_dom,
):
    """Logical costs must match pinned known-good values."""
    bench = registry[name]
    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    assert (
        costs.t_count_direct == exp_direct
    ), f"t_count_direct: {costs.t_count_direct} != {exp_direct}"
    assert (
        costs.t_count_ftqc == exp_ftqc
    ), f"t_count_ftqc: {costs.t_count_ftqc} != {exp_ftqc}"
    assert (
        costs.logical_qubits_estimate == exp_qubits
    ), f"qubits: {costs.logical_qubits_estimate} != {exp_qubits}"
    assert (
        costs.rotation_count == exp_rot
    ), f"rotation_count: {costs.rotation_count} != {exp_rot}"


@pytest.mark.parametrize(
    "name,params",
    [(c[0], c[1]) for c in REFERENCE_CASES],
    ids=[_case_id(c) for c in REFERENCE_CASES],
)
def test_logical_breakdown_consistency(name, params):
    """Logical t_count_ftqc must agree with sum of breakdown est_t_ftqc.

    This is the exact check that would have caught the ApproximateQFT bug:
    logical=0 vs breakdown=2632.
    """
    bench = registry[name]
    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)
    items = extract_structural_breakdown(bloq)
    breakdown_total = sum(i.est_t_ftqc for i in items)

    denom = max(costs.t_count_ftqc, breakdown_total, 1)
    delta = abs(costs.t_count_ftqc - breakdown_total) / denom

    assert delta < 0.01, (
        f"logical t_count_ftqc={costs.t_count_ftqc:,} vs "
        f"breakdown total={breakdown_total:,} (delta={delta:.1%})"
    )


@pytest.mark.parametrize(
    "name,params,exp_direct,exp_ftqc,exp_qubits,exp_rot,exp_dom",
    REFERENCE_CASES,
    ids=[_case_id(c) for c in REFERENCE_CASES],
)
def test_breakdown_dominant_component(
    name,
    params,
    exp_direct,
    exp_ftqc,
    exp_qubits,
    exp_rot,
    exp_dom,
):
    """Breakdown must identify the correct dominant cost component.

    Catches misclassification like AddIntoPhaseGrad tagged as "rotations"
    when it's actually controlled_nonclifford.
    """
    bench = registry[name]
    bloq = bench.build_bloq(**params)
    items = extract_structural_breakdown(bloq)
    summary = summarize_breakdown(items)

    # Skip when total cost is zero (dominant label is meaningless).
    total = sum(i.est_t_ftqc for i in items)
    if total == 0:
        pytest.skip("total FTQC cost is 0 — dominant label undefined")

    assert (
        summary["dominant_component"] == exp_dom
    ), f"dominant: {summary['dominant_component']} != {exp_dom}"


@pytest.mark.parametrize(
    "name,params",
    PHYSICAL_CASES,
    ids=[_case_id(c) for c in PHYSICAL_CASES],
)
def test_physical_estimation_sane(name, params):
    """Physical estimates must have positive wall time, reasonable distance,
    and meet the error budget.

    Would have caught the approx QFT bug: wall_time=0, code_distance=3.
    """
    bench = registry[name]
    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    # Skip if the circuit has zero non-Clifford cost (nothing to estimate).
    if costs.t_count_ftqc == 0 and costs.rotation_count == 0:
        pytest.skip("zero non-Clifford cost")

    phys = estimate_physical(costs)

    assert phys.wall_time_us > 0, "wall_time_us must be > 0"
    assert phys.code_distance >= 3, "code_distance must be >= 3"
    assert phys.physical_qubits > 0, "physical_qubits must be > 0"
    assert (
        phys.budget_satisfied
    ), f"error budget not met: failure_prob={phys.failure_prob:.2e} > {phys.error_budget:.2e}"


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
    bloq = bench.build_bloq(n=16, variant="textbook")
    costs = bench.logical_costs(bloq)
    spec = PhysicalModelSpec(profile=profile, factory=factory)
    phys = estimate_physical(costs, spec=spec)

    assert phys.budget_satisfied, (
        f"{profile}/{factory}: budget not satisfied "
        f"(failure_prob={phys.failure_prob:.2e})"
    )
    assert phys.wall_time_us > 0


@pytest.mark.parametrize(
    "name,params",
    VERIFY_CASES,
    ids=[_case_id(c) for c in VERIFY_CASES],
)
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
    """T-count must be non-decreasing as the problem size grows."""
    bench = registry[name]
    prev_t = -1
    for size in sizes:
        params = {param_key: size, **fixed}
        bloq = bench.build_bloq(**params)
        costs = bench.logical_costs(bloq)
        assert costs.t_count_ftqc >= prev_t, (
            f"{name}({params}): t_count_ftqc={costs.t_count_ftqc} < "
            f"previous={prev_t} — scaling not monotonic"
        )
        prev_t = costs.t_count_ftqc


def test_approx_qft_cheaper_than_textbook():
    """Approximate QFT must have strictly lower FTQC T-count than textbook
    for n >= 8 (where the phase-gradient trick kicks in)."""
    bench = registry["qft"]
    for n in [8, 16, 32, 64]:
        tb = bench.logical_costs(bench.build_bloq(n=n, variant="textbook"))
        ap = bench.logical_costs(bench.build_bloq(n=n, variant="approx"))
        assert (
            ap.t_count_ftqc < tb.t_count_ftqc
        ), f"n={n}: approx T_ftqc={ap.t_count_ftqc} >= textbook T_ftqc={tb.t_count_ftqc}"


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
        assert (
            swap.t_count_ftqc < basic.t_count_ftqc
        ), f"N={data_size}: selectswap T_ftqc={swap.t_count_ftqc} >= basic T_ftqc={basic.t_count_ftqc}"


def test_mul_more_expensive_than_add():
    """Multiplier must cost strictly more T-gates than adder at same bitsize."""
    bench = registry["arithmetic"]
    for n in [8, 16, 32]:
        add = bench.logical_costs(bench.build_bloq(n=n, op="add"))
        mul = bench.logical_costs(bench.build_bloq(n=n, op="mul"))
        assert (
            mul.t_count_ftqc > add.t_count_ftqc
        ), f"n={n}: mul T_ftqc={mul.t_count_ftqc} <= add T_ftqc={add.t_count_ftqc}"


def test_ftqc_overhead_for_rotation_heavy():
    """For rotation-heavy circuits (textbook QFT), t_count_ftqc must be
    significantly larger than t_count_direct due to synthesis cost."""
    bench = registry["qft"]
    costs = bench.logical_costs(bench.build_bloq(n=32, variant="textbook"))

    assert costs.rotation_count > 0, "textbook QFT should have rotations"
    assert (
        costs.t_count_ftqc > costs.t_count_direct
    ), f"t_ftqc={costs.t_count_ftqc} should be > t_direct={costs.t_count_direct}"
    overhead = costs.t_count_ftqc / max(costs.t_count_direct, 1)
    assert (
        overhead > 5
    ), f"FTQC overhead {overhead:.1f}x is suspiciously low for 435 rotations at eps=1e-10"


def test_no_rotation_no_overhead():
    """For rotation-free circuits, t_count_ftqc must equal t_count_direct."""
    bench = registry["arithmetic"]
    for op in ["add", "add_oop", "mul"]:
        costs = bench.logical_costs(bench.build_bloq(n=16, op=op))
        assert costs.rotation_count == 0, f"{op} should have no rotations"
        assert (
            costs.t_count_ftqc == costs.t_count_direct
        ), f"{op}: t_ftqc={costs.t_count_ftqc} != t_direct={costs.t_count_direct}"

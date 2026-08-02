"""GE19 reproduction (arXiv:1905.09749v3).

Logical-count reconciliation and the physical rows, asserted against targets in
``qrepro.references.values``. Sources, conventions and achieved deviations:
ASSUMPTIONS.md.
"""

from __future__ import annotations

import math

import pytest

from qrepro.algorithms.windowed_factoring import windowed_term_breakdown
from qrepro.references import (
    reproduce_ge19_logical,
    reproduce_ge19_physical,
    reproduce_ge19_windowed,
)
from qrepro.references.values import (
    GE19,
    GE19_QREPRO,
    GE19_QREPRO_ACHIEVED,
    GE19_TOL,
    GE19_WINDOWED,
    GE19_WINDOWED_ACHIEVED,
    GE19_WINDOWED_TOL,
)


@pytest.fixture(scope="module")
def logical():
    return reproduce_ge19_logical()


@pytest.fixture(scope="module")
def physical():
    return reproduce_ge19_physical()


@pytest.fixture(scope="module")
def windowed():
    return reproduce_ge19_windowed()


def test_ge19_logical_qubits_formula(logical):
    """3n + 0.002*n*lg n rounds to the abstract's 6189 at n=2048."""
    assert round(logical.logical_qubits_formula) == GE19["logical_qubits"]


def test_ge19_toffoli_formula_matches_table1(logical):
    """The abstract formula evaluates 2.81% below Table 1's rounded 2.7e9."""
    assert logical.toffoli_formula == pytest.approx(GE19["toffoli_count"], rel=0.05)


def test_modexp_call_graph_count_pinned(logical):
    """Regression literal: a dependency bump that moves it must surface."""
    assert logical.modexp_ccz_count == GE19["modexp_qualtran_toffoli"]


def test_modexp_and_only_count_pinned():
    """The and_bloq-only count, pinned so the two currencies cannot drift.

    Aggregation rule and both literals: ASSUMPTIONS.md sec. 3 and 4.
    """
    from qualtran.resource_counting import QECGatesCost, get_cost_value

    from qrepro.algorithms.factoring import make_shor_modexp

    gates = get_cost_value(make_shor_modexp(GE19["n"]), QECGatesCost())
    assert int(gates.and_bloq) == GE19["modexp_qualtran_and_only"]
    assert int(gates.cswap) == 2 * GE19["n"] * GE19["n"]  # ne*n, ne = 2n
    assert (
        GE19["modexp_qualtran_and_only"] + int(gates.cswap)
        == GE19["modexp_qualtran_toffoli"]
    )


@pytest.mark.parametrize("n", [1024, 2048, 3072])
def test_factoring_bloqs_build_at_every_tabulated_size(n):
    """Both factories must build at every n GE19 tabulates.

    The placeholder ``2^n - 1`` is divisible by ``2^d - 1`` for every ``d | n``,
    so the default base 7 shares a factor with it whenever ``3 | n`` and
    ``make_shor_modexp(3072)`` fails ModExp's coprimality assertion.
    ``placeholder_modulus`` steps down until coprime.
    """
    import math

    from qrepro.algorithms.factoring import make_shor_modexp, placeholder_modulus
    from qrepro.algorithms.windowed_factoring import make_ge19_windowed_modexp

    mod = placeholder_modulus(n, 7)
    assert mod.bit_length() == n
    assert mod % 2 == 1
    assert math.gcd(7, mod) == 1
    assert make_shor_modexp(n).mod == mod
    assert make_ge19_windowed_modexp(n).mod == mod


def test_placeholder_modulus_does_not_move_the_pinned_count():
    """The n=2048 modulus is unchanged, so the pinned literals cannot shift."""
    from qrepro.algorithms.factoring import placeholder_modulus

    assert placeholder_modulus(GE19["n"], 7) == (1 << GE19["n"]) - 1


def test_modexp_coefficient_converges(logical):
    """n_ccz/(ne*n^2) converges to a constant, identifying the reference regime.

    A windowed construction would fall like 1/lg^2 n across this range.
    """
    coeffs = [c for _, c in sorted(logical.coefficient_series)]
    assert coeffs, "coefficient series must be populated"
    assert all(a >= b for a, b in zip(coeffs, coeffs[1:])), coeffs
    assert coeffs[-1] == pytest.approx(10.0, rel=0.01), coeffs
    assert (coeffs[0] - coeffs[-1]) / coeffs[-1] < 0.02, coeffs


def test_modexp_matches_fitted_half_reference(logical):
    """Regression pin on the fitted 10*ne*n^2 coefficient.

    Not evidence, since the coefficient is fitted; attribution rests on
    test_modexp_coefficient_converges.
    """
    assert logical.modexp_ccz_count == pytest.approx(
        logical.half_reference_fitted, rel=0.02
    )
    assert logical.measured_coefficient == pytest.approx(
        logical.ge19_reference_coefficient / 2, rel=0.01
    )


def test_modexp_vs_formula_divergence(logical):
    """The ~64x logical divergence, in a band wide enough to absorb the choice
    of denominator convention."""
    assert (
        GE19_TOL["divergence_lo"]
        <= logical.divergence_ratio
        <= GE19_TOL["divergence_hi"]
    )


# Windowed logical (sec. 2.3-2.5, the optimized construction)
# Targets, tolerances, achieved deviations and the named cause of every gap:
# ASSUMPTIONS.md sec. 6.

WINDOWED_N = (1024, 2048, 3072)


@pytest.mark.parametrize("n", WINDOWED_N)
def test_windowed_count_pinned(windowed, n):
    """Pin the total and all three terms, so a shift between terms cannot hide
    inside a matching total."""
    inst = windowed.by_n(n)
    achieved = GE19_WINDOWED_ACHIEVED[f"n{n}"]
    assert (inst.exp_window, inst.mul_window) == achieved["window"]
    assert inst.total_ccz == achieved["total_ccz"]
    assert inst.adder_ccz == achieved["adder_ccz"]
    assert inst.lookup_ccz == achieved["lookup_ccz"]
    assert inst.unlookup_ccz == achieved["unlookup_ccz"]
    assert inst.bridged_ccz == achieved["bridged_ccz"]


@pytest.mark.parametrize("n", WINDOWED_N)
def test_windowed_terms_sum_to_total(windowed, n):
    """The term attribution covers the whole count, with no unattributed remainder."""
    inst = windowed.by_n(n)
    assert inst.adder_ccz + inst.lookup_ccz + inst.unlookup_ccz == inst.total_ccz
    assert inst.bridged_ccz == inst.total_ccz + inst.adder_ccz


@pytest.mark.parametrize("n", WINDOWED_N)
def test_windowed_vs_table1_band(windowed, n):
    """Unbridged vs Table 1, in bands declared in advance."""
    ratio = windowed.by_n(n).table1_ratio
    lo = GE19_WINDOWED_TOL["table1_lo"][f"n{n}"]
    hi = GE19_WINDOWED_TOL["table1_hi"][f"n{n}"]
    assert lo <= ratio <= hi, f"n={n}: {ratio}"


@pytest.mark.parametrize("n", WINDOWED_N)
def test_windowed_bridged_matches_table1(windowed, n):
    """Bridging only the adder term recovers Table 1."""
    ratio = windowed.by_n(n).bridged_table1_ratio
    lo = GE19_WINDOWED_TOL["bridged_table1_lo"][f"n{n}"]
    hi = GE19_WINDOWED_TOL["bridged_table1_hi"][f"n{n}"]
    assert lo <= ratio <= hi, f"n={n}: {ratio}"


@pytest.mark.parametrize("n", WINDOWED_N)
def test_windowed_bridged_vs_anc_model(windowed, n):
    """Bridged vs GE19's own ancillary cost model.

    Looser than the Table 1 band: the anc literals include carry runways this
    construction excludes, and carry weaker provenance.
    """
    ratio = windowed.by_n(n).bridged_anc_ratio
    assert (
        GE19_WINDOWED_TOL["bridged_anc_lo"]
        <= ratio
        <= GE19_WINDOWED_TOL["bridged_anc_hi"]
    ), f"n={n}: {ratio}"


@pytest.mark.parametrize("n", WINDOWED_N)
def test_windowed_vs_closed_form_16(windowed, n):
    """Count vs 16*ne*n^2/lg^2n -- L602's 24 in Qualtran's adder currency."""
    inst = windowed.by_n(n)
    assert inst.total_ccz == pytest.approx(
        inst.closed_form_16, rel=GE19_WINDOWED_TOL["rel_closed_form_16"]
    )


def test_windowed_falloff_is_one_over_lg_squared_n(windowed):
    """total/(ne*n^2) falls like 1/lg^2 n; a non-windowed construction is constant.

    Uses no external number. Compare test_modexp_coefficient_converges.
    """
    series = sorted(windowed.coefficient_series)
    assert len(series) >= 5, series
    coeffs = [c for _, c in series]
    assert all(a > b for a, b in zip(coeffs, coeffs[1:])), series
    by_n = dict(series)
    scaled = by_n[GE19["n"]] * math.log2(GE19["n"]) ** 2
    assert (
        GE19_WINDOWED_TOL["falloff_lg2_lo"]
        <= scaled
        <= GE19_WINDOWED_TOL["falloff_lg2_hi"]
    ), scaled


def test_windowed_window_sweep_minimum(windowed):
    """The cost minimum over the grid equals GE19 L690's published (5, 5)."""
    assert windowed.window_argmin == GE19_WINDOWED_ACHIEVED["window_argmin_n2048"]
    assert windowed.window_argmin == (
        GE19_WINDOWED["exp_window"],
        GE19_WINDOWED["mul_window"],
    )


def test_windowed_cost_is_convex_in_window_area(windowed):
    """Cost is U-shaped in k = w_e + w_m: small k pays adder, large k lookup.

    A monotone curve would mean one term stopped scaling.
    """
    best_by_k: dict[int, int] = {}
    for we, wm, total in windowed.window_grid:
        k = we + wm
        best_by_k[k] = min(best_by_k.get(k, total), total)
    ks = sorted(best_by_k)
    totals = [best_by_k[k] for k in ks]
    argmin = totals.index(min(totals))
    assert 0 < argmin < len(totals) - 1, dict(zip(ks, totals))
    assert all(a > b for a, b in zip(totals[: argmin + 1], totals[1 : argmin + 1]))
    assert all(a < b for a, b in zip(totals[argmin:], totals[argmin + 1 :]))


def test_windowed_adder_share_dominates(windowed):
    """The adder term dominates the count, so the single-term bridge applies."""
    share = windowed.by_n(GE19["n"]).adder_share
    assert (
        GE19_WINDOWED_TOL["adder_share_lo"]
        <= share
        <= GE19_WINDOWED_TOL["adder_share_hi"]
    ), share


# Windowed construction: gate-field and structural guards


def test_windowed_emits_no_cswap():
    """Guards the uncontrolled-multiplication decision (ASSUMPTIONS.md sec. 6)."""
    from qualtran.resource_counting import QECGatesCost, get_cost_value

    from qrepro.algorithms.windowed_factoring import make_ge19_windowed_modexp

    gates = get_cost_value(make_ge19_windowed_modexp(GE19["n"]), QECGatesCost())
    assert int(gates.cswap) == 0


def test_windowed_uses_both_gate_fields():
    """Guards the n_ccz extraction decision: the unlookup term lives in
    ``toffoli``, so and_bloq-only extraction must fail loudly."""
    from qualtran.resource_counting import QECGatesCost, get_cost_value

    from qrepro.algorithms.windowed_factoring import make_ge19_windowed_modexp

    gates = get_cost_value(make_ge19_windowed_modexp(GE19["n"]), QECGatesCost())
    assert int(gates.and_bloq) > 0
    assert int(gates.toffoli) > 0
    total = int(gates.total_t_and_ccz_count(ts_per_rotation=0)["n_ccz"])
    assert int(gates.and_bloq) < total
    assert int(gates.and_bloq) + int(gates.toffoli) == total


def test_windowed_call_graph_stays_collapsed():
    """The call graph must stay O(10) nodes, not O(n_e).

    Built from data instead of bitsize, every lookup addition would be a
    distinct bloq and the count would never terminate.
    """
    from qrepro.algorithms.windowed_factoring import make_ge19_windowed_modexp

    graph, _ = make_ge19_windowed_modexp(GE19["n"]).call_graph()
    assert graph.number_of_nodes() < 30, graph.number_of_nodes()


def test_windowed_logical_costs_use_full_magic_state_count():
    """modexp_logical_costs must aggregate n_ccz, not and_bloq, on the
    windowed construction whose unlookup term lives in ``toffoli``."""
    from qrepro.algorithms.factoring import modexp_logical_costs
    from qrepro.algorithms.windowed_factoring import make_ge19_windowed_modexp

    n = GE19["n"]
    costs = modexp_logical_costs(
        make_ge19_windowed_modexp(n), logical_qubits=GE19["logical_qubits"]
    )
    assert costs.magic_state_count == GE19_WINDOWED_ACHIEVED[f"n{n}"]["total_ccz"]
    assert costs.t_count_direct == 4 * costs.magic_state_count
    assert costs.logical_qubits_estimate == GE19["logical_qubits"]


def test_windowed_is_far_cheaper_than_stock_modexp():
    """Windowed is ~100x below stock ModExp, same currency and pinned Qualtran."""
    n = GE19["n"]
    windowed_total = GE19_WINDOWED_ACHIEVED[f"n{n}"]["total_ccz"]
    assert windowed_total * 50 < GE19["modexp_qualtran_toffoli"]


# Windowed construction: toy-size correctness
# These use the exact non-padded variant (coset_padding=0 with ModAdd); the
# coset representation itself is not simulated -- see ASSUMPTIONS.md sec. 6.


def test_windowed_lookup_addition_classical_action():
    """y -> y + table[addr], address restored, no junk left."""
    from qrepro.algorithms.windowed_factoring import LookupAddition

    bloq = LookupAddition(lookup_bitsize=2, width=5, table=(3, 1, 4, 2))
    decomposed = bloq.decompose_bloq()
    for addr in range(4):
        for y in range(4):
            assert bloq.call_classically(addr=addr, y=y) == (
                addr,
                (y + bloq.table[addr]) % 32,
            )
            assert decomposed.call_classically(addr=addr, y=y) == bloq.call_classically(
                addr=addr, y=y
            )


def test_windowed_multiply_add_classical_action():
    """y -> y + x*(multiplier^addr) mod N through the real decomposition."""
    from qrepro.algorithms.windowed_factoring import WindowedMultiplyAdd

    mod, multiplier = 15, 7
    bloq = WindowedMultiplyAdd(
        multiplier=multiplier,
        mod=mod,
        width=4,
        exp_window=2,
        mul_window=2,
        input_slack_bits=0,
        exact_modular=True,
    )
    decomposed = bloq.decompose_bloq()
    for addr in range(4):
        k = pow(multiplier, addr, mod)
        for x in range(mod):
            for y in range(mod):
                assert decomposed.call_classically(addr=addr, x=x, y=y) == (
                    addr,
                    x,
                    (y + x * k) % mod,
                )


def test_windowed_mod_mul_clears_its_source_register():
    """x -> x*k mod N by two passes; the source must end at |0>.

    ``bb.free`` raises if the unmultiply left anything behind.
    """
    from qrepro.algorithms.windowed_factoring import WindowedModMul

    mod, base_power = 15, 7
    bloq = WindowedModMul(
        base_power=base_power,
        mod=mod,
        width=4,
        exp_window=2,
        mul_window=2,
        input_slack_bits=0,
        exact_modular=True,
    )
    decomposed = bloq.decompose_bloq()
    for addr in range(4):
        for x in range(1, mod):
            assert decomposed.call_classically(addr=addr, x=x) == (
                addr,
                (x * pow(base_power, addr, mod)) % mod,
            )


@pytest.mark.parametrize(
    ("mod", "base", "n", "ne"),
    [(15, 7, 4, 4), (21, 5, 5, 4), (33, 7, 6, 6)],
)
def test_windowed_modexp_classical_action(mod, base, n, ne):
    """x -> base^e mod N for every exponent, through the decomposition.

    Window-indexing errors show up here as a wrong residue at some exponent.
    """
    from qrepro.algorithms.windowed_factoring import WindowedModExp

    bloq = WindowedModExp(
        base=base,
        mod=mod,
        exp_bitsize=ne,
        x_bitsize=n,
        exp_window=2,
        mul_window=2,
        coset_padding=0,
        input_slack_bits=0,
        exact_modular=True,
    )
    decomposed = bloq.decompose_bloq()
    for e in range(2**ne):
        assert decomposed.call_classically(exponent=e) == (e, pow(base, e, mod))
        assert bloq.call_classically(exponent=e) == (e, pow(base, e, mod))


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (dict(base=5, mod=15), "coprime"),  # gcd(5, 15) = 5
        (dict(base=7, mod=16), "odd"),
        (dict(base=0, mod=15), "base must lie"),
        (dict(base=7, mod=15, exp_window=0), "exp_window"),
    ],
)
def test_windowed_modexp_rejects_bad_parameters(kwargs, message):
    """Fail closed at the boundary with an actionable message."""
    from qrepro.algorithms.windowed_factoring import WindowedModExp

    params = dict(exp_bitsize=4, x_bitsize=4, exp_window=2, mul_window=2)
    params.update(kwargs)
    with pytest.raises(ValueError, match=message):
        WindowedModExp(**params)


def test_windowed_exact_modular_requires_zero_padding():
    """Coset padding and exact ModAdd are alternatives, not composable."""
    from qrepro.algorithms.windowed_factoring import WindowedModExp

    with pytest.raises(ValueError, match="coset_padding=0"):
        WindowedModExp(
            base=7,
            mod=15,
            exp_bitsize=4,
            x_bitsize=4,
            exp_window=2,
            mul_window=2,
            coset_padding=8,
            exact_modular=True,
        )


def test_windowed_lookup_addition_rejects_wrong_table_size():
    from qrepro.algorithms.windowed_factoring import LookupAddition

    with pytest.raises(ValueError, match="2\\^lookup_bitsize"):
        LookupAddition(lookup_bitsize=2, width=5, table=(1, 2, 3))


def test_windowed_refuses_to_decompose_without_table_data():
    """At scale the data-free call graph is the costing path."""
    from qualtran import DecomposeTypeError

    from qrepro.algorithms.windowed_factoring import LookupAddition

    with pytest.raises(DecomposeTypeError, match="table"):
        LookupAddition(lookup_bitsize=3, width=8).decompose_bloq()


def test_windowed_runway_exclusion_is_measurable(windowed):
    """Runways are off by default and turning them on costs count.

    The uplift diverges from GE19's own model; ASSUMPTIONS.md sec. 6.
    """
    from qrepro.algorithms.windowed_factoring import make_ge19_windowed_modexp
    from qrepro.references.ge19_windowed import windowed_total_ccz

    n = GE19["n"]
    assert make_ge19_windowed_modexp(n).runway_sep is GE19_WINDOWED["runway_sep"]
    off = windowed_total_ccz(n, 5, 5)
    with_runways = windowed_term_breakdown(
        make_ge19_windowed_modexp(n, runway_sep=GE19_WINDOWED["ge19_runway_sep"])
    ).total_ccz
    uplift = (with_runways - off) / off
    assert uplift == pytest.approx(
        GE19_WINDOWED_ACHIEVED["runway_uplift_n2048"], abs=0.002
    )


def test_ge19_uses_papers_own_inputs(physical):
    """Both free parameters are GE19's published values, not choices."""
    assert physical.error_budget == GE19_QREPRO["error_budget"] == 0.31
    assert physical.retry_risk == GE19["physical_rows"]["table3_authoritative"]["retry"]
    assert physical.one_factory.n_factories == 1
    assert physical.parallel.n_factories == 28


def test_ge19_grid_search_finds_papers_own_factory(physical):
    """At GE19's own budget and factory count the search picks GE19's factory."""
    t3 = GE19["physical_rows"]["table3_authoritative"]
    assert physical.parallel.factory_l1_d == t3["d1"] == 15
    assert physical.parallel.factory_l2_d == t3["d2"] == 27


def test_ge19_one_factory_qubits(physical):
    """1-factory qubits vs Table 2's 16 M (+12.3%)."""
    ph = physical.one_factory
    achieved = GE19_QREPRO_ACHIEVED["one_factory"]
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19["physical_rows"]["one_factory"]["qubits_M"], rel=GE19_TOL["rel_qubits"]
    )
    assert ph.physical_qubits / 1e6 == pytest.approx(achieved["qubits_M"], rel=0.02)
    assert ph.code_distance == achieved["code_distance"]


def test_ge19_one_factory_runtime(physical):
    """1-factory runtime vs Table 2's 6 days (-11.2%).

    Conventions cannot be matched here: GE19 publishes only an *expected*
    runtime for this scenario. See ASSUMPTIONS.md sec. 4.
    """
    assert physical.one_factory_runtime_hr == pytest.approx(
        physical.one_factory_target_runtime_hr_expected, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_parallel_qubits(physical):
    """28-factory qubits vs Table 2/3's 20 M (-13.7%)."""
    ph = physical.parallel
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19["physical_rows"]["parallel"]["qubits_M"], rel=GE19_TOL["rel_qubits"]
    )
    assert ph.physical_qubits / 1e6 == pytest.approx(
        GE19_QREPRO_ACHIEVED["parallel"]["qubits_M"], rel=0.02
    )


def test_ge19_parallel_runtime_per_run(physical):
    """Per run vs Table 3's 5.1 hr/run (-10.5%) - the like-for-like comparison."""
    assert physical.parallel_runtime_hr == pytest.approx(
        physical.parallel_target_runtime_hr_per_run, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_parallel_runtime_expected(physical):
    """Converted to GE19's expected convention vs Table 2's 0.31 day (-11.0%)."""
    assert physical.parallel_runtime_hr_expected == pytest.approx(
        physical.parallel_target_runtime_hr_expected, rel=GE19_TOL["rel_runtime"]
    )


def test_ge19_tables_2_and_3_are_consistent():
    """Table 2 and Table 3 reconcile exactly via the published retry risk."""
    t3 = GE19["physical_rows"]["table3_authoritative"]
    t2 = GE19["physical_rows"]["parallel"]
    assert t3["runtime_hr_per_run"] / (1 - t3["retry"]) / 24 == pytest.approx(
        t2["runtime_days"], rel=0.01
    )
    assert t3["vol_megaqubitdays_per_run"] / (1 - t3["retry"]) == pytest.approx(
        t2["vol_mqd"], rel=0.01
    )

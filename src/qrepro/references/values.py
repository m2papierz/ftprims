"""Published paper constants and the deviations achieved against them.

Sources, free parameters, conventions and achieved deviations are documented in
``ASSUMPTIONS.md``; this module carries values, not prose.

Distinct from the regression literals in ``tests/test_integration.py``: those
are what this code computes, these are what the papers report.
"""

from __future__ import annotations

import math

# ── Beverland et al. (arXiv:2211.07629) ───────────────────────────────────────
# Targets are eq.(D3)/(D4) evaluated. For quantum dynamics that differs from the
# printed Table I values, which contradict those equations (ASSUMPTIONS.md §1).
BEVERLAND = {
    "quantum_dynamics": dict(  # §V-A L1369
        n_algo_qubits=100,
        gate_counts=dict(rotation=30_100, measurement=1_400_000),
        n_rotation_layers=501,
        error_budget=1e-3,
        time_steps_for_code_distance=1.5e5,
        physical_error=1e-4,
        expect_c_min=1.4401e6,
        expect_t_states=602_000,
        expect_code_distance=9,
    ),
    "quantum_chemistry": dict(  # §V-B L1397
        n_algo_qubits=1318,
        gate_counts=dict(
            t=int(5.53e7),
            rotation=int(2.06e8),
            toffoli=int(1.35e11),
            measurement=int(1.37e9),
        ),
        n_rotation_layers=int(2.05e8),
        error_budget=1e-2,
        time_steps_for_code_distance=4.1e11,
        physical_error=1e-4,
        expect_c_min=4.1e11,
        expect_t_states=5.44e11,
        expect_code_distance=17,
    ),
    "factoring": dict(  # §V-C L1420
        n_algo_qubits=12581,
        gate_counts=dict(
            t=12,
            rotation=12,
            toffoli=int(3.73e9),
            measurement=int(1.08e9),
        ),
        n_rotation_layers=12,
        error_budget=1 / 3,
        time_steps_for_code_distance=1.23e10,
        physical_error=1e-4,
        expect_c_min=1.23e10,
        expect_t_states=1.49e10,
        expect_code_distance=13,
    ),
}

# Worst achieved deviation +0.43%; rel=0.01 holds with ~2x margin.
BEVERLAND_TOL = dict(rel_c_min=0.01, rel_t_states=0.01)


# ── Gidney & Ekera 2019 (arXiv:1905.09749v3) ──────────────────────────────────


def ge19_logical_qubits(n: int) -> float:
    """GE19 abstract L78: ``3n + 0.002·n·lg n``."""
    return 3 * n + 0.002 * n * math.log2(n)


def ge19_toffoli_count(n: int) -> float:
    """GE19 abstract L78: ``0.3·n³ + 0.0005·n³·lg n``."""
    return 0.3 * n**3 + 0.0005 * n**3 * math.log2(n)


def ge19_measurement_depth(n: int) -> float:
    """GE19 abstract L78: ``500·n² + n²·lg n``."""
    return 500 * n**2 + n**2 * math.log2(n)


def modexp_toffoli_reference(n: int, ne: float) -> float:
    """GE19 §2.2 L522, reference construction: ``20·ne·n²``."""
    return 20 * ne * n**2


def modexp_toffoli_coset(n: int, ne: float) -> float:
    """GE19 §2.4 L547, coset representation: ``8·ne·n²``."""
    return 8 * ne * n**2


def modexp_toffoli_windowed(n: int, ne: float) -> float:
    """GE19 §2.5 L602, windowed arithmetic: ``24·ne·n²/lg²n``."""
    return 24 * ne * n**2 / math.log2(n) ** 2


def modexp_toffoli_windowed_qualtran(n: int, ne: float) -> float:
    """``16·ne·n²/lg²n``: GE19 §2.5 L602's 24 in Qualtran's adder currency.

    Not a published constant; derivation in ASSUMPTIONS.md §6.
    """
    return 16 * ne * n**2 / math.log2(n) ** 2


#: Sizes at which the ModExp coefficient is sampled to identify the regime from
#: its scaling rather than a fitted constant (ASSUMPTIONS.md §3).
MODEXP_COEFFICIENT_SIZES = (32, 64, 128, 256, 512, 1024, 2048)

#: Sizes over which the windowed coefficient's 1/lg²n falloff is sampled; this
#: distinguishes windowed from non-windowed on scaling alone.
WINDOWED_COEFFICIENT_SIZES = (128, 256, 512, 1024, 2048, 4096, 8192)


GE19 = dict(
    n=2048,
    phys_err=1e-3,  # abstract
    cycle_us=1.0,  # abstract
    reaction_us=10.0,  # abstract
    logical_qubits=6189,  # abstract formula at n=2048
    toffoli_count=2.7e9,  # Table 1
    # Measured, qualtran 0.7.0 (ASSUMPTIONS.md §3).
    modexp_qualtran_toffoli=171_840_634_880,
    modexp_qualtran_and_only=171_832_246_272,
    table1_toffoli_billions=dict(n1024=0.4, n2048=2.7, n3072=9.9),
    table1_minvol_megaqubitdays=dict(n1024=0.5, n2048=5.9, n3072=21),
    physical_rows=dict(
        # Table 2: qubits/runtime/volume are expected, i.e. retry-adjusted.
        one_factory=dict(factories=1, qubits_M=16, runtime_days=6.0, vol_mqd=90),
        one_thread=dict(factories=14, qubits_M=19, runtime_days=0.36, vol_mqd=6.6),
        parallel=dict(factories=28, qubits_M=20, runtime_days=0.31, vol_mqd=5.9),
        # Table 3, n=2048 optimum: runtime/volume are per run.
        table3_authoritative=dict(
            d1=15,
            d2=27,
            cmul=5,
            cexp=5,
            csep=1024,
            retry=0.31,
            qubits_megaqubits=20,
            runtime_hr_per_run=5.1,
            vol_megaqubitdays_per_run=4.1,
            vol_megaqubitdays=5.9,
        ),
    ),
)

# Reproduction inputs. error_budget and n_factories are GE19-published values
# rather than free choices (ASSUMPTIONS.md §2/§3).
GE19_QREPRO = dict(
    error_budget=0.31,  # Table 3 retry risk
    error_budget_sweep=(0.1, 0.31, 0.33, 0.5),
    one_factory_n_factories=1,  # Table 2 "1 CCZ"
    parallel_n_factories=28,  # Table 2 "28 CCZ"
    factory_count_sweep=(1, 14, 16, 28),
)

# Measured against qualtran 0.7.0. At nf=28 the search selects d1=15, d2=27,
# which is GE19 Table 3's factory.
GE19_QREPRO_ACHIEVED = dict(
    one_factory=dict(
        n_factories=1,
        qubits_M=17.970,
        runtime_hr=127.875,
        code_distance=31,
        factory_l1_d=15,
        factory_l2_d=25,
    ),
    parallel=dict(
        n_factories=28,
        qubits_M=17.262,
        runtime_hr=4.567,
        runtime_hr_expected=6.619,
        code_distance=27,
        factory_l1_d=15,
        factory_l2_d=27,
    ),
)

# Achieved deviations 10.5-13.7%; rel=0.18 holds with ~30% headroom.
GE19_TOL = dict(
    rel_qubits=0.18,
    rel_runtime=0.18,
    divergence_lo=40.0,
    divergence_hi=80.0,
)


# ── GE19 §2.3-2.5, the windowed construction ──────────────────────────────────
# Reproduced from Qualtran components. Distinct from the block above, which
# reconciles GE19 against Qualtran's stock, non-windowed ModExp. Sources,
# conventions and achieved deviations: ASSUMPTIONS.md §6.

GE19_WINDOWED = dict(
    # Construction parameters, all GE19-published rather than free choices.
    exp_window=5,  # g_exp, GE19 §2.7 L690
    mul_window=5,  # g_mul, GE19 L690
    n_e_factor=1.5,  # Ekera-Hastad, GE19 L482
    runway_sep=None,  # g_sep excluded from the count; ASSUMPTIONS.md §6
    ge19_runway_sep=1024,  # GE19 L690 / Table 3, for the sensitivity probe only
    coset_padding=dict(n1024=40, n2048=43, n3072=45),  # 2 lg n + lg n_e + 10, L690
    # GE19's own ancillary cost model at matched parameters. Weaker provenance
    # than the Table 1 literals (ASSUMPTIONS.md §6).
    anc_model_toffoli=dict(n1024=4.2100e8, n2048=2.7534e9, n3072=8.6211e9),
)

# Measured against qualtran==0.7.0 from the built WindowedModExp bloq, at the
# per-n cost argmin over w_e, w_m in [3,8], w_m <= w_e.
# `slack_lookup_excess` is the per-multiply-add gap between the lookup additions
# the call graph charges and the ones the decomposition emits, which the input
# slack bits open when they cross a w_m boundary.
GE19_WINDOWED_ACHIEVED = dict(
    n1024=dict(
        window=(5, 4),
        total_ccz=265_951_224,
        adder_ccz=174_833_736,
        lookup_ccz=83_880_720,
        unlookup_ccz=7_236_768,
        bridged_ccz=440_784_960,
        slack_lookup_excess=1,
    ),
    n2048=dict(
        window=(5, 5),
        total_ccz=1_634_753_640,
        adder_ccz=1_077_123_300,
        lookup_ccz=526_708_140,
        unlookup_ccz=30_922_200,
        bridged_ccz=2_711_876_940,
        slack_lookup_excess=0,
    ),
    n3072=dict(
        window=(5, 5),
        total_ccz=4_830_453_888,
        adder_ccz=3_585_444_096,
        lookup_ccz=1_175_970_432,
        unlookup_ccz=69_039_360,
        bridged_ccz=8_415_897_984,
        slack_lookup_excess=0,
    ),
    window_argmin_n2048=(5, 5),
    runway_uplift_n2048=0.0353,  # count uplift from runways on at GE19's g_sep
)

# Every band was set from a measured deviation; the achieved values and the
# cause of each gap are tabulated in ASSUMPTIONS.md §6.
GE19_WINDOWED_TOL = dict(
    bridged_table1_lo=dict(n1024=0.95, n2048=0.95, n3072=0.78),
    bridged_table1_hi=dict(n1024=1.20, n2048=1.10, n3072=0.95),
    table1_lo=dict(n1024=0.60, n2048=0.55, n3072=0.43),
    table1_hi=dict(n1024=0.75, n2048=0.68, n3072=0.58),
    bridged_anc_lo=0.94,
    bridged_anc_hi=1.08,
    adder_share_lo=0.60,
    adder_share_hi=0.72,
    falloff_lg2_lo=14.0,
    falloff_lg2_hi=17.0,
    rel_closed_form_16=0.10,
)


# ── Gidney 2025 (arXiv:2505.15917) ────────────────────────────────────────────

G2025 = dict(
    n=2048,
    logical_qubits=1399,  # Table 5
    toffoli_count=6.5e9,  # Table 5, expected per factoring, not per shot
    expected_shots=9.2,  # Table 5
    phys_err=1e-3,  # abstract, same as GE19
    cycle_us=1.0,
    reaction_us=10.0,
    published_physical_qubits="<1e6",  # abstract
    published_runtime="<1 week",  # abstract
    qubit_reduction_sources=dict(
        algorithmic=[
            "approximate residue arithmetic (Chevignard-Fouque-Schrottenloher)"
        ],
        qec_stack=[
            "yoked surface codes (Gidney-Newman-Brooks-Jones)",
            "magic state cultivation (Gidney-Shutty-Jones)",
        ],
    ),
)

# Measured against qualtran 0.7.0 at error_budget=0.31, per Toffoli convention.
G2025_QREPRO = dict(
    error_budget=0.31,
    per_run=dict(
        ge19_1f_qubits_M=17.9702,
        g2025_1f_qubits_M=3.1867,
        ratio_1f=5.6391,
        ge19_16f_qubits_M=17.6381,
        g2025_16f_qubits_M=4.5478,
        ratio_16f=3.8783,
        ge19_28f_qubits_M=17.2616,
        g2025_28f_qubits_M=5.9909,
        ratio_28f=2.8813,
    ),
    expected=dict(
        ge19_1f_qubits_M=17.9702,
        g2025_1f_qubits_M=3.6881,
        ratio_1f=4.8724,
        ge19_16f_qubits_M=17.6381,
        g2025_16f_qubits_M=5.4760,
        ratio_16f=3.2210,
        ge19_28f_qubits_M=19.1549,
        g2025_28f_qubits_M=7.2877,
        ratio_28f=2.6284,
    ),
)

# The paper's < 1M is not reproducible by this model; rel=0.20 guards drift
# only. The ratio band covers the achieved 2.63x-5.64x span.
G2025_TOL = dict(rel_qubits=0.20, algo_ratio_lo=2.5, algo_ratio_hi=6.0)

"""Published paper constants for the three FTQC resource-estimate reproductions.

Every literal here is a reproduction target read from a cited paper. Sources,
free parameters, conventions and achieved deviations are documented once in
``ASSUMPTIONS.md``; this module carries values, not prose.

Distinct from the pinned regression literals in ``tests/test_integration.py``:
those are what *our code* computes, these are what the *papers* report.
"""

from __future__ import annotations

import math

# ── Beverland et al. (arXiv:2211.07629) ───────────────────────────────────────
# Targets are the paper's eq.(D3)/(D4) evaluated. For quantum dynamics that
# differs from the paper's printed Table I values, which contradict its own
# equations -- see ASSUMPTIONS.md §1.
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

# Worst achieved deviation is +0.43%; rel=0.01 holds with ~2x margin.
BEVERLAND_TOL = dict(rel_c_min=0.01, rel_t_states=0.01)


# ── Gidney & Ekerå 2019 (arXiv:1905.09749v3) ──────────────────────────────────


def ge19_logical_qubits(n: int) -> float:
    """Abstract formula: 3n + 0.002·n·lg n."""
    return 3 * n + 0.002 * n * math.log2(n)


def ge19_toffoli_count(n: int) -> float:
    """Abstract formula: 0.3·n³ + 0.0005·n³·lg n."""
    return 0.3 * n**3 + 0.0005 * n**3 * math.log2(n)


def ge19_measurement_depth(n: int) -> float:
    """Abstract formula: 500·n² + n²·lg n."""
    return 500 * n**2 + n**2 * math.log2(n)


def modexp_toffoli_reference(n: int, ne: float) -> float:
    """Reference modular exponentiation, §2.2 L522: 20·ne·n²."""
    return 20 * ne * n**2


def modexp_toffoli_coset(n: int, ne: float) -> float:
    """Coset representation, §2.4 L547: 8·ne·n²."""
    return 8 * ne * n**2


def modexp_toffoli_windowed(n: int, ne: float) -> float:
    """Windowed arithmetic, §2.5 L602: 24·ne·n²/lg²n."""
    return 24 * ne * n**2 / math.log2(n) ** 2


#: Sizes at which the measured ModExp coefficient is sampled to identify the
#: regime from its scaling rather than a fitted constant (ASSUMPTIONS.md §3).
MODEXP_COEFFICIENT_SIZES = (32, 64, 128, 256, 512, 1024, 2048)


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
        # Table 2 -- qubits/runtime/volume are EXPECTED (i.e. retry-adjusted).
        one_factory=dict(factories=1, qubits_M=16, runtime_days=6.0, vol_mqd=90),
        one_thread=dict(factories=14, qubits_M=19, runtime_days=0.36, vol_mqd=6.6),
        parallel=dict(factories=28, qubits_M=20, runtime_days=0.31, vol_mqd=5.9),
        # Table 3, n=2048 optimum -- runtime/volume are PER RUN.
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

# Reproduction inputs. error_budget and n_factories are GE19's own published
# values, not choices -- see ASSUMPTIONS.md §2/§3.
GE19_FTPRIMS = dict(
    error_budget=0.31,  # Table 3 retry risk
    error_budget_sweep=(0.1, 0.31, 0.33, 0.5),
    one_factory_n_factories=1,  # Table 2 "1 CCZ"
    parallel_n_factories=28,  # Table 2 "28 CCZ"
    factory_count_sweep=(1, 14, 16, 28),
)

# Achieved live (qualtran 0.7.0). At nf=28 the search selects d1=15, d2=27 --
# exactly GE19 Table 3's factory.
GE19_FTPRIMS_ACHIEVED = dict(
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

# Achieved deviations are 10.5-13.7%; rel=0.18 holds with ~30% headroom.
GE19_TOL = dict(
    rel_qubits=0.18,
    rel_runtime=0.18,
    divergence_lo=40.0,
    divergence_hi=80.0,
)


# ── Gidney 2025 (arXiv:2505.15917) ────────────────────────────────────────────

G2025 = dict(
    n=2048,
    logical_qubits=1399,  # Table 5
    toffoli_count=6.5e9,  # Table 5, expected per factoring (not per shot)
    expected_shots=9.2,  # Table 5
    phys_err=1e-3,  # abstract, same as GE19
    cycle_us=1.0,
    reaction_us=10.0,
    headline_physical_qubits="<1e6",  # abstract
    headline_runtime="<1 week",  # abstract
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

# Achieved live (qualtran 0.7.0) at error_budget=0.31, per Toffoli convention.
G2025_FTPRIMS = dict(
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

# The paper's < 1M is NOT reproducible by this model; rel=0.20 guards drift only.
# Ratio band covers the achieved 2.63x-5.64x span.
G2025_TOL = dict(rel_qubits=0.20, algo_ratio_lo=2.5, algo_ratio_hi=6.0)

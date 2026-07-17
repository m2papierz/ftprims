"""Published paper constants for the three FTQC resource-estimate reproductions.

Every literal in this module is a *reproduction target* taken from a cited
paper, carried with an inline citation (arXiv id + version + table/figure/
section). Notebooks, ``tests/test_references_*.py``, and the reproduction
modules import from here and never write a paper number inline. A value without
a citation is a defect, not a value.

This is distinct from the pinned regression literals in ``tests/test_integration.py``
and ``tests/test_export_breakdown.py``: those are what *our code* computes against
the pinned Qualtran; the values here are what the *papers report*. The two are
compared, never merged.

Papers:
  - Beverland et al., arXiv:2211.07629 (as encoded by Qualtran 0.7.0's
    ``beverland_et_al_model``).
  - Gidney & Ekerå, arXiv:1905.09749v3 ("GE19"): factor 2048-bit RSA with
    20 million qubits.
  - Gidney, arXiv:2505.15917 ("G2025"): factor 2048-bit RSA with < 1 million
    qubits.

All ``expect_*`` targets and ``achieved_*`` notes below were produced by a live
run of the pinned qualtran==0.7.0 stack (see the notebooks); the ``achieved``
comments exist so the test tolerances can be justified from real deviations
rather than guessed.
"""

from __future__ import annotations

import math

# ── Beverland et al. (arXiv:2211.07629) ───────────────────────────────────────
#
# The three application instances Qualtran 0.7.0 encodes from Beverland et al.
# in ``beverland_et_al_model_test.py``. code_distance is evaluated at
# physical_error=1e-4. For the quantum-dynamics point, code_distance is asked
# at the paper's tabulated time_steps (1.5e5), NOT at the computed c_min.
#
# Achieved (live, qualtran 0.7.0):
#   quantum_dynamics : c_min=1.4401e6  t_states=6.0200e5   d=9
#   quantum_chemistry: c_min=4.1176e11 t_states=5.4521e11  d=17
#   factoring        : c_min=1.2270e10 t_states=1.4920e10  d=13
BEVERLAND = {
    "quantum_dynamics": dict(
        n_algo_qubits=100,  # Table encoded in beverland_et_al_model_test.py
        gate_counts=dict(rotation=30_100, measurement=1_400_000),
        n_rotation_layers=501,
        error_budget=1e-3,
        time_steps_for_code_distance=1.5e5,  # ask d at tabulated steps, not c_min
        physical_error=1e-4,
        expect_c_min=1.5e6,  # arXiv:2211.07629 quantum-dynamics instance
        expect_t_states=602_000,
        expect_code_distance=9,
    ),
    "quantum_chemistry": dict(
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
        expect_c_min=4.1e11,  # arXiv:2211.07629 quantum-chemistry instance
        expect_t_states=5.44e11,
        expect_code_distance=17,
    ),
    "factoring": dict(
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
        expect_c_min=1.23e10,  # arXiv:2211.07629 factoring instance
        expect_t_states=1.49e10,
        expect_code_distance=13,
    ),
}

# Tolerances for Beverland, justified from the achieved deviations above.
#   c_min / t_states: worst achieved deviation is quantum_dynamics c_min
#   (1.44e6 vs 1.5e6 = 4.0%). rel=0.10 matches the band Qualtran's own
#   beverland_et_al_model_test.py asserts these at, and comfortably covers 4%.
#   code_distance: exact for quantum_chemistry (17) and factoring (13); the
#   dynamics point lands exactly on 9 when d is asked at time_steps=1.5e5.
BEVERLAND_TOL = dict(rel_c_min=0.10, rel_t_states=0.10)


# ── Gidney & Ekerå 2019 (arXiv:1905.09749v3, "GE19") ──────────────────────────


def ge19_logical_qubits(n: int) -> float:
    """GE19 abstract logical-qubit formula: 3n + 0.002·n·log2(n)."""
    return 3 * n + 0.002 * n * math.log2(n)


def ge19_toffoli_count(n: int) -> float:
    """GE19 abstract Toffoli+T/2 formula: 0.3·n^3 + 0.0005·n^3·log2(n)."""
    return 0.3 * n**3 + 0.0005 * n**3 * math.log2(n)


def ge19_measurement_depth(n: int) -> float:
    """GE19 abstract measurement-depth formula: 500·n^2 + n^2·log2(n)."""
    return 500 * n**2 + n**2 * math.log2(n)


# Alternative modular-exponentiation cost regimes, for the divergence story
# (arXiv:1905.09749v3). ne = number of exponent qubits: 2n for Shor's original,
# 1.5n for Ekerå-Håstad. Toffoli count of the modular exponentiation:
#   reference (textbook, standard rep, §2 baseline): 20·ne·n^2
#   coset representation (§2.4):                       8·ne·n^2
#   windowed arithmetic (§2.5, dominant saving):      24·ne·n^2 / log2(n)^2
def modexp_toffoli_reference(n: int, ne: float) -> float:
    """Textbook / reference modular-exponentiation Toffoli count: 20·ne·n^2."""
    return 20 * ne * n**2


def modexp_toffoli_coset(n: int, ne: float) -> float:
    """Coset-representation modular-exponentiation Toffoli count: 8·ne·n^2."""
    return 8 * ne * n**2


def modexp_toffoli_windowed(n: int, ne: float) -> float:
    """Windowed-arithmetic modular-exponentiation Toffoli count: 24·ne·n^2/log2(n)^2."""
    return 24 * ne * n**2 / math.log2(n) ** 2


GE19 = dict(
    n=2048,
    # Physical assumptions — arXiv:1905.09749v3, abstract + §2.10–2.14.
    phys_err=1e-3,  # gate error rate (abstract)
    cycle_us=1.0,  # surface-code cycle time (abstract)
    reaction_us=10.0,  # control-system reaction time (abstract)
    # Logical counts at n=2048.
    logical_qubits=6189,  # 3n + 0.002 n lg n -> 6189.06 (abstract formula)
    toffoli_count=2.7e9,  # Table 1: Toffoli+T/2 at n=2048 (billions). formula -> 2.62e9
    # Measured over the qualtran 0.7.0 ModExp call graph (QECGatesCost.and_bloq),
    # non-windowed textbook construction (2n·CModMulK, ne=2n, standard rep):
    modexp_qualtran_toffoli=171_832_246_272,  # ~1.72e11; ~10·ne·n^2 with ne=2n
    # Table 1: Toffoli+T/2 count in billions, by modulus size.
    table1_toffoli_billions=dict(n1024=0.4, n2048=2.7, n3072=9.9),
    # Table 1: minimum-spacetime-volume in megaqubit·days, by modulus size.
    table1_minvol_megaqubitdays=dict(n1024=0.5, n2048=5.9, n3072=21),
    # Physical rows — Table 2 (headline scenarios) + Table 3 (authoritative n=2048).
    physical_rows=dict(
        one_factory=dict(factories=1, qubits_M=16, runtime_days=6.0, vol_mqd=90),
        one_thread=dict(factories=14, qubits_M=19, runtime_days=0.36, vol_mqd=6.6),
        parallel=dict(factories=28, qubits_M=20, runtime_days=0.31, vol_mqd=5.9),
        # Table 3, authoritative (from GE19's own estimate_costs.py), n=2048:
        table3_authoritative=dict(
            d1=15,  # level-1 distillation code distance
            d2=27,  # level-2 distillation code distance
            cmul=5,  # multiplication code-distance factor
            cexp=5,  # exponentiation code-distance factor
            csep=1024,  # separation
            retry=0.31,  # ~31% per-run retry probability
            qubits_megaqubits=20,  # 20 Mqubits
            runtime_hr_per_run=5.1,  # 5.1 hours/run
            vol_megaqubitdays=5.9,
        ),
    ),
)

# ftprims reproductions of GE19's physical rows, fed the GE19 *formula* Toffoli
# count (2.7e9), n_algo_qubits=6189, phys_err=1e-3, cycle=1.0. See the
# error_budget=0.5 proxy decision in the physical component brief.
# Achieved (live, qualtran 0.7.0):
#   1-factory  (estimate_physical, auto d, eb=0.5): 18.0M qubits, 127.9 hr, d=31
#   16-factory (grid search, eb=0.5):               15.6M qubits,   8.0 hr
GE19_FTPRIMS = dict(
    error_budget_proxy=0.5,  # documented proxy for GE19's ~31% retry / skewed volume
    error_budget_sweep=(0.1, 0.33, 0.5),  # documented anti-tuning sensitivity sweep
    one_factory=dict(n_factories=1, qubits_M=18.0, runtime_hr=127.9, code_distance=31),
    parallel=dict(n_factories=16, qubits_M=15.6, runtime_hr=8.0),
)

# Tolerances for GE19, justified from achieved deviations.
#   qubits: 1-factory 18.0M vs GE19 16M = +12.5%; parallel 15.6M vs GE19 20M
#     = -22%. rel=0.25 covers both with margin and is defensible for an
#     order-of-magnitude physical reproduction with a proxy error budget.
#   runtime: 1-factory 127.9 hr vs GE19 6 days (144 hr) = -11%; parallel 8.0 hr
#     vs GE19 Table 3 5.1 hr/run = +57% (but 8.0 hr vs Table 2 0.31 day = 7.4 hr
#     = +8%). rel=0.30 on the mapped Table-2 runtime covers the 1-factory case;
#     the parallel runtime is reported as a divergence rather than asserted tight.
#   logical divergence: ModExp 1.72e11 / formula 2.7e9 = 63.6x (or /2.62e9
#     formula-evaluated = 65.5x). Assert the ratio in [40, 80]: wide enough to
#     be robust to which formula count (Table-1 2.7e9 vs evaluated 2.62e9) is
#     used as the denominator, tight enough to pin the "reference-regime, not
#     optimized-regime" finding.
GE19_TOL = dict(
    rel_qubits=0.25,
    rel_runtime=0.30,
    divergence_lo=40.0,
    divergence_hi=80.0,
)


# ── Gidney 2025 (arXiv:2505.15917, "G2025") ───────────────────────────────────
#
# Logical counts RE-CONFIRMED against Table 5 of the primary PDF (not secondary
# sources): the n=2048 row is Toffolis=6.5e9, Qubits=1399. §3.2 states each shot
# is "roughly 12 hours" and involves "fewer than 1600 logical qubits". The
# abstract gives < 1 million physical qubits and < 1 week.
G2025 = dict(
    n=2048,
    logical_qubits=1399,  # Table 5, n=2048 row ("Qubits" column)
    toffoli_count=6.5e9,  # Table 5, n=2048 row ("Toffolis" column, expected/factoring)
    # Same physical assumptions as GE19 (abstract): 0.1% error, 1 us cycle,
    # 10 us reaction.
    phys_err=1e-3,
    cycle_us=1.0,
    reaction_us=10.0,
    headline_physical_qubits="<1e6",  # abstract: less than a million noisy qubits
    headline_runtime="<1 week",  # abstract
    # Qubit-reduction sources. Only the algorithmic one is captured by the
    # ftprims CCZ2T model (via fewer logical qubits). The QEC-stack items are
    # OUT OF SCOPE for this cost model — it has no yoked-code or cultivation
    # representation (confirmed by §3.2 of 2505.15917).
    qubit_reduction_sources=dict(
        algorithmic=[
            "approximate residue arithmetic "
            "(Chevignard-Fouque-Schrottenloher 2024, [CFS24])",
        ],
        qec_stack=[
            "yoked surface codes (Gidney-Newman-Brooks-Jones 2023, [Gid+25])",
            "magic state cultivation (Gidney-Shutty-Jones 2024, [GSJ24])",
        ],
    ),
)

# ftprims decomposition of the 2019->2025 improvement. Both GE19 and G2025
# logical counts are run through the SAME CCZ2T grid search at a fixed factory
# count (apples-to-apples: grid-for-both, not estimate_physical-vs-grid), eb=0.5.
# Achieved (live, qualtran 0.7.0):
#   16-factory grid: GE19 15.56M -> G2025 5.19M  (algorithmic ~3.0x)
#    1-factory grid: GE19 15.77M -> G2025 3.68M  (algorithmic ~4.3x)
#   G2025 1-factory grid runtime ~347.6 hr (distillation-limited).
# The residual gap from the ftprims G2025 number down to the published < 1M is
# the QEC stack (yoked codes + cultivation), which this model cannot represent.
G2025_FTPRIMS = dict(
    error_budget=0.5,
    ge19_through_model_16f_qubits_M=15.56,
    g2025_through_model_16f_qubits_M=5.19,
    ge19_through_model_1f_qubits_M=15.77,
    g2025_through_model_1f_qubits_M=3.68,
    g2025_through_model_1f_runtime_hr=347.6,
    # Reported decomposition (see the 2019->2025 decomposition decision):
    #   algorithmic (captured):     ~3.0x (16-factory) .. ~4.3x (1-factory)
    #   QEC-stack (not captured):   remaining factor down to < 1M
    algorithmic_ratio_16f=15.56 / 5.19,  # ~3.0x
    algorithmic_ratio_1f=15.77 / 3.68,  # ~4.3x
)

# Tolerance for the 2019->2025 decomposition: the G2025-through-model
# reproduction is asserted only loosely (rel=0.20 on the achieved 16-factory
# 5.19M and 1-factory 3.68M) — it guards against gross drift, not a paper
# target, because the paper's < 1M is explicitly NOT reproducible by this model.
# The algorithmic ratio is asserted to sit in [2.5, 6.0], the honest range
# spanned by the factory-count sweep.
G2025_TOL = dict(rel_qubits=0.20, algo_ratio_lo=2.5, algo_ratio_hi=6.0)

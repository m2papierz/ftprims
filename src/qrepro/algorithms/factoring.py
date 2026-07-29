"""Shor ``ModExp`` construction and logical-cost extraction.

Costs come from ``QECGatesCost`` over the call graph. ``QubitCount`` /
``AlgorithmSummary.from_bloq`` / ``decompose_bloq`` walk the wires (O(gates)) and
hang at n >= 128, so the logical-qubit count is supplied analytically instead.
"""

from __future__ import annotations

import math

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, get_cost_value

from qrepro.algorithms._base import LogicalCosts


def placeholder_modulus(n_bits: int, base: int) -> int:
    """Largest odd *n_bits*-bit integer coprime to *base*.

    The magic-state count depends only on the register bitsizes, so a
    placeholder of the right bit length serves for costing.

    ``2^n_bits - 1`` is divisible by ``2^d - 1`` for every ``d`` dividing
    ``n_bits``, so the default base 7 shares a factor with it whenever
    ``3 | n_bits`` -- including n=3072, where ``ModExp`` fails its coprimality
    assertion. Stepping down by 2 finds a usable modulus in a few iterations.
    """
    if n_bits < 2:
        raise ValueError(f"n_bits must be ≥ 2, got {n_bits}")
    mod = (1 << n_bits) - 1
    while math.gcd(base, mod) != 1:
        mod -= 2
        if mod.bit_length() != n_bits:  # pragma: no cover - unreachable for n>=2
            raise ValueError(f"no {n_bits}-bit odd modulus coprime to base {base}")
    return mod


def make_shor_modexp(n_bits: int, *, base: int = 7):
    """Build a Shor ``ModExp`` for an *n_bits*-bit RSA modulus.

    Constructs the bloq directly (``exp_bitsize = 2·n_bits``,
    ``x_bitsize = n_bits``) rather than via ``ModExp.make_for_shor``, whose
    float ``ceil(log2(N))`` rounds down for thousand-bit integers and yields an
    ``x_bitsize`` one bit too small to hold residues mod N, raising
    "Too-large classical value" at n=2048.

    The modulus is a :func:`placeholder_modulus`; the gate count does not
    depend on its value.
    """
    from qualtran.bloqs.cryptography.rsa.rsa_mod_exp import ModExp

    mod = placeholder_modulus(n_bits, base)
    return ModExp(base=base, mod=mod, exp_bitsize=2 * n_bits, x_bitsize=n_bits)


def modexp_logical_costs(
    modexp_bloq: Bloq,
    *,
    logical_qubits: int,
) -> LogicalCosts:
    """Logical costs for a modular-exponentiation bloq, without tracing qubits.

    Covers both Qualtran's stock ``ModExp`` and ``WindowedModExp``. Magic-state
    and raw-T totals come from ``QECGatesCost`` over the call graph, aggregated
    as ``n_ccz`` (ASSUMPTIONS.md §3); *logical_qubits* is the paper's analytic
    count. ``resource.extract_logical_costs`` cannot be used here: it calls
    ``QubitCount``, which hangs on these bloqs at n >= 128.

    The ``n_ccz`` aggregate is load-bearing for the windowed construction, whose
    cost spans two ``GateCounts`` fields -- the lookup lands in ``and_bloq``,
    the whole unlookup term in ``toffoli`` (ASSUMPTIONS.md §6).
    """
    gates = get_cost_value(modexp_bloq, QECGatesCost())
    counts = gates.total_t_and_ccz_count(ts_per_rotation=0)
    return LogicalCosts.from_magic_state_count(
        int(counts["n_ccz"]),
        logical_qubits=logical_qubits,
        raw_t=int(counts["n_t"]),
    )

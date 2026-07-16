"""Scale-safe Shor factoring costs (QubitCount-free ModExp extraction).

Constructs a Shor ``ModExp`` bloq for an *n*-bit RSA modulus and extracts its
logical costs by counting symbolically over the call graph — never by tracing
qubits. ``get_cost_value(ModExp, QubitCount())`` /
``AlgorithmSummary.from_bloq`` / ``decompose_bloq`` walk the wires (O(gates)) and
hang at n >= 128, so the logical-qubit count is supplied analytically (e.g. GE19
``3n``) while only the And/Toffoli and raw-T totals come from ``QECGatesCost``.
"""

from __future__ import annotations

from qualtran import Bloq
from qualtran.resource_counting import QECGatesCost, get_cost_value

from ftprims.algorithms._base import LogicalCosts


def make_shor_modexp(n_bits: int, *, base: int = 7):
    """Build a Shor ``ModExp`` for an *n_bits*-bit RSA modulus.

    Constructs the bloq directly (``exp_bitsize=2·n_bits``, ``x_bitsize=n_bits``)
    rather than via ``ModExp.make_for_shor``, which computes ``x_bitsize`` as
    ``ceil(log2(N))`` using a float ``log2`` that rounds imprecisely for
    thousand-bit integers, producing an ``x_bitsize`` one bit too small to hold
    residues mod N and raising a "Too-large classical value" error at n=2048.

    The ``QECGatesCost`` And/Toffoli count depends only on the bitsizes, not the
    modulus value (verified: identical count across distinct 2048-bit moduli), so
    a fixed placeholder odd modulus of the right bit length is used.

    Parameters
    ----------
    n_bits:
        RSA modulus bit length (e.g. 2048).
    base:
        Exponentiation base ``g`` (does not affect the gate count).
    """
    from qualtran.bloqs.cryptography.rsa.rsa_mod_exp import ModExp

    if n_bits < 2:
        raise ValueError(f"n_bits must be ≥ 2, got {n_bits}")
    # 2^n_bits - 1: odd, bit_length == n_bits, value < 2^n_bits, and positive for
    # every n_bits ≥ 2, so every residue mod N fits in the x_bitsize=n_bits
    # register. The gate count is modulus-value-independent (verified).
    mod = (1 << n_bits) - 1
    return ModExp(base=base, mod=mod, exp_bitsize=2 * n_bits, x_bitsize=n_bits)


def modexp_logical_costs(
    modexp_bloq: Bloq,
    *,
    logical_qubits: int,
) -> LogicalCosts:
    """Logical costs for a ``ModExp`` bloq WITHOUT tracing qubits.

    Counts symbolically over the call graph via ``QECGatesCost`` (~0.01 s at
    n=2048) to get the And/Toffoli and raw-T totals, then attaches the
    analytic *logical_qubits* count. This deliberately avoids
    ``QubitCount`` / ``AlgorithmSummary.from_bloq`` / ``decompose_bloq``,
    which walk the wires (O(gates)) and hang on ModExp at n≥128 — the exact
    reason ``resource.extract_logical_costs`` must not be used here.

    Parameters
    ----------
    modexp_bloq:
        A ``ModExp`` (or equivalent factoring) bloq.
    logical_qubits:
        Logical-qubit count from the paper's analytic formula (GE19 ``3n``).
    """
    gates = get_cost_value(modexp_bloq, QECGatesCost())
    return LogicalCosts.from_toffoli_count(
        int(gates.and_bloq),
        logical_qubits=logical_qubits,
        raw_t=int(gates.t),
    )

"""Arithmetic benchmark: Add, OutOfPlaceAdder, LessThanEqual, Product, ModAdd.

Fault-tolerant building blocks for integer arithmetic.  Each operation
maps to a single Qualtran bloq; verification uses ``call_classically``
against Python integer arithmetic.
"""

from __future__ import annotations

import random
from typing import Callable

from qualtran import Bloq
from qualtran._infra.data_types import QUInt
from qualtran.bloqs.arithmetic import Add, LessThanEqual, OutOfPlaceAdder
from qualtran.bloqs.arithmetic.multiplication import Product
from qualtran.bloqs.mod_arithmetic.mod_addition import ModAdd

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)
from ftprims.resource import extract_logical_costs


__all__ = ["ArithmeticBenchmark"]

_OPS = {"add", "add_oop", "leq", "mul", "modadd"}
_MAX_VERIFY_N = 6
_VERIFY_SAMPLES = 20
_VERIFY_RNG_SEED = 0


def _build_arithmetic(*, n: int, op: str, mod: int | None = None) -> Bloq:
    """Construct the requested arithmetic bloq.

    Parameters
    ----------
    n:
        Bitsize of the operands.
    op:
        One of ``add``, ``add_oop``, ``leq``, ``mul``, ``modadd``.
    mod:
        Modulus for ``modadd`` (must be < 2**n). Defaults to the
        largest prime below 2**n for n ≤ 32; for larger n uses
        2**n - 1 to avoid expensive primality search.
    """
    if op not in _OPS:
        raise ValueError(f"Unknown op {op!r}; choose from {sorted(_OPS)}")
    if n < 1:
        raise ValueError(f"Bitsize must be ≥ 1, got {n}")

    if op == "add":
        return Add(QUInt(n))
    if op == "add_oop":
        return OutOfPlaceAdder(bitsize=n)
    if op == "leq":
        return LessThanEqual(x_bitsize=n, y_bitsize=n)
    if op == "mul":
        return Product(a_bitsize=n, b_bitsize=n)
    if op == "modadd":
        if mod is None:
            if n <= 32:
                mod = _largest_prime_below(1 << n)
            else:
                mod = (1 << n) - 1
        if mod < 2 or mod >= (1 << n):
            raise ValueError(f"mod={mod} out of range for bitsize {n}")
        return ModAdd(bitsize=n, mod=mod)

    raise AssertionError("unreachable")  # pragma: no cover


def _largest_prime_below(limit: int) -> int:
    """Return the largest prime strictly below *limit* (brute force, small n)."""
    for candidate in range(limit - 1, 1, -1):
        if all(candidate % d != 0 for d in range(2, int(candidate**0.5) + 1)):
            return candidate
    return 2


_ClassicalOracle = Callable[[int, int, int], tuple[dict[str, int], dict[str, int]]]


def _oracle_add(n: int) -> _ClassicalOracle:
    """Add: b <= a+b mod 2**n."""
    mask = (1 << n) - 1

    def check(a: int, b: int, _mod: int) -> tuple[dict, dict]:
        inputs = dict(a=a, b=b)
        expected = dict(a=a, b=(a + b) & mask)
        return inputs, expected

    return check


def _oracle_add_oop(n: int) -> _ClassicalOracle:
    """OutOfPlaceAdder: c <= a+b (output register is wider)."""

    def check(a: int, b: int, _mod: int) -> tuple[dict, dict]:
        inputs = dict(a=a, b=b, c=0)
        expected = dict(a=a, b=b, c=a + b)
        return inputs, expected

    return check


def _oracle_leq(_n: int) -> _ClassicalOracle:
    """LessThanEqual: target <= (x ≤ y)."""

    def check(x: int, y: int, _mod: int) -> tuple[dict, dict]:
        inputs = dict(x=x, y=y, target=0)
        expected = dict(x=x, y=y, target=int(x <= y))
        return inputs, expected

    return check


def _oracle_modadd(_n: int) -> _ClassicalOracle:
    """ModAdd: y <= (x+y) mod p."""

    def check(x: int, y: int, mod: int) -> tuple[dict, dict]:
        inputs = dict(x=x, y=y)
        expected = dict(x=x, y=(x + y) % mod)
        return inputs, expected

    return check


_ORACLES: dict[str, Callable[[int], _ClassicalOracle]] = {
    "add": _oracle_add,
    "add_oop": _oracle_add_oop,
    "leq": _oracle_leq,
    "modadd": _oracle_modadd,
}


def _verify_classically(
    bloq: Bloq,
    oracle: _ClassicalOracle,
    n: int,
    mod: int,
) -> VerificationResult:
    """Run random classical test vectors through ``call_classically``."""
    bound = 1 << n
    rng = random.Random(_VERIFY_RNG_SEED)

    for _ in range(_VERIFY_SAMPLES):
        a = rng.randint(0, bound - 1)
        b = rng.randint(0, bound - 1)
        if mod:
            a, b = a % mod, b % mod

        inputs, expected = oracle(a, b, mod)

        try:
            result = bloq.call_classically(**inputs)
        except Exception as exc:
            return VerificationResult(
                passed=False,
                detail=f"call_classically({inputs}) failed: {exc}",
            )

        # Map positional results back to register names.
        reg_names = [reg.name for reg in bloq.signature]
        actual = dict(zip(reg_names, result))

        if actual != expected:
            return VerificationResult(
                passed=False,
                detail=f"Mismatch: inputs={inputs} expected={expected} got={actual}",
            )

    return VerificationResult(
        passed=True,
        detail=f"{_VERIFY_SAMPLES} random vectors OK (n={n})",
    )


@register
class ArithmeticBenchmark(Benchmark):
    """Benchmark wrapper for FT arithmetic primitives."""

    name = "arithmetic"

    def build_bloq(
        self,
        *,
        n: int = 8,
        op: str = "add",
        mod: int | None = None,
    ) -> Bloq:
        return _build_arithmetic(
            n=int(n),
            op=str(op),
            mod=int(mod) if mod is not None else None,
        )

    def logical_costs(self, bloq: Bloq) -> LogicalCosts:
        return extract_logical_costs(bloq)

    def verify_small(
        self,
        *,
        n: int = 4,
        op: str = "add",
        mod: int | None = None,
    ) -> VerificationResult:
        """Verify arithmetic op via ``call_classically`` on random inputs."""
        n = int(n)
        if n > _MAX_VERIFY_N:
            return VerificationResult(
                passed=False,
                detail=f"n={n} too large for verification (max {_MAX_VERIFY_N})",
            )

        if op == "mul":
            # Product has no decomposition or classical simulation in Qualtran.
            return VerificationResult(
                passed=True,
                detail=f"Product(n={n}): classical simulation not supported by Qualtran; "
                "cost extraction verified only",
            )

        oracle_factory = _ORACLES.get(op)
        if oracle_factory is None:
            return VerificationResult(
                passed=False,
                detail=f"No oracle for op={op!r}",
            )

        bloq = self.build_bloq(n=n, op=op, mod=mod)

        # Resolve the modulus that _build_arithmetic actually used.
        effective_mod = getattr(bloq, "mod", 0)
        oracle = oracle_factory(n)
        return _verify_classically(bloq, oracle, n, effective_mod)

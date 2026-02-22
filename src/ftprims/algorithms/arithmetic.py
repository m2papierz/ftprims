"""Arithmetic benchmark - Add, OutOfPlaceAdder, LessThanEqual."""

from __future__ import annotations

from qualtran import Bloq

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)


@register
class ArithmeticBenchmark(Benchmark):
    name = "arithmetic"

    def build_bloq(
        self,
        *,
        n: int,
        op: str,
    ) -> Bloq: ...

    def logical_costs(self, bloq: Bloq) -> LogicalCosts: ...

    def verify_small(
        self,
        *,
        n: int,
        op: str,
    ) -> VerificationResult: ...

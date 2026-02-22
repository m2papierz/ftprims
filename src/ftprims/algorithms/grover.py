"""Grover benchmark with pluggable oracle."""

from __future__ import annotations

from qualtran import Bloq

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)


__all__ = ["GroverBenchmark"]


@register
class GroverBenchmark(Benchmark):
    name = "grover"

    def build_bloq(
        self,
        *,
        n: int,
        k: int | None = None,
        oracle: str = "bitstring",
    ) -> Bloq: ...

    def logical_costs(self, bloq: Bloq) -> LogicalCosts: ...

    def verify_small(
        self,
        *,
        n: int,
    ) -> VerificationResult: ...

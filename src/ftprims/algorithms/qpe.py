"""QPE benchmark."""

from __future__ import annotations

from qualtran import Bloq

from ftprims.algorithms._base import (
    Benchmark,
    LogicalCosts,
    VerificationResult,
    register,
)


__all__ = ["QPEBenchmark"]


@register
class QPEBenchmark(Benchmark):
    name = "qpe"

    def build_bloq(
        self,
        *,
        m: int,
        phi: float,
    ) -> Bloq: ...

    def logical_costs(self, bloq: Bloq) -> LogicalCosts: ...

    def verify_small(
        self,
        *,
        m: int,
        phi: float,
    ) -> VerificationResult: ...

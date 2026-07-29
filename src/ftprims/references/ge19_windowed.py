"""GE19 §2.3-2.5 windowed construction, reproduced.

Derives GE19's logical layer through Qualtran components
(``ftprims.algorithms.windowed_factoring``) rather than the paper's closed
forms. Separate from ``ftprims.references.ge19``, which reconciles the paper
against Qualtran's stock, non-windowed ``ModExp``.

Sources, counting conventions and the measured divergences: ASSUMPTIONS.md §6.
"""

from __future__ import annotations

import attrs

from ftprims.algorithms.windowed_factoring import (
    ge19_exponent_bitsize,
    make_ge19_windowed_modexp,
    windowed_term_breakdown,
)
from ftprims.references._base import ReproductionRow
from ftprims.references.values import (
    GE19,
    GE19_WINDOWED,
    WINDOWED_COEFFICIENT_SIZES,
    modexp_toffoli_windowed,
    modexp_toffoli_windowed_qualtran,
)

#: Window grid swept for the cost minimum (ASSUMPTIONS.md §6).
WINDOW_GRID = tuple((we, wm) for we in range(3, 9) for wm in range(3, we + 1))


def windowed_total_ccz(n: int, we: int, wm: int) -> int:
    """Magic-state count of the windowed construction at *n*, ``(we, wm)``."""
    return windowed_term_breakdown(
        make_ge19_windowed_modexp(n, exp_window=we, mul_window=wm)
    ).total_ccz


def windowed_best_window(n: int) -> tuple[int, int]:
    """Cost-minimising ``(w_e, w_m)`` over :data:`WINDOW_GRID` at size *n*.

    A check on GE19 L690's published default, not its justification.
    """
    return min(WINDOW_GRID, key=lambda w: windowed_total_ccz(n, *w))


def windowed_coefficient_series(
    sizes: tuple[int, ...] = WINDOWED_COEFFICIENT_SIZES,
) -> tuple[tuple[int, float], ...]:
    """Measured ``n_ccz / (ne·n²)`` at the best window for each n.

    Falls like ``1/lg²n``; a non-windowed construction gives a constant.
    """
    out = []
    for n in sizes:
        ne = ge19_exponent_bitsize(n)
        total = windowed_total_ccz(n, *windowed_best_window(n))
        out.append((n, total / (ne * n**2)))
    return tuple(out)


def reproduce_ge19_windowed(
    sizes: tuple[int, ...] = (1024, 2048, 3072),
) -> GE19WindowedReproduction:
    """Reproduce GE19's windowed modexp count from Qualtran components.

    For each n, builds the construction at its cost-minimising window, splits
    the count into GE19's three terms, and compares against Table 1 both as-is
    and with the adder term bridged to Cuccaro's convention.
    """
    instances = []
    for n in sizes:
        we, wm = windowed_best_window(n)
        bloq = make_ge19_windowed_modexp(n, exp_window=we, mul_window=wm)
        terms = windowed_term_breakdown(bloq)
        key = f"n{n}"
        ne = bloq.exp_bitsize
        instances.append(
            GE19WindowedInstance(
                n=n,
                exp_bitsize=ne,
                coset_padding=bloq.padding,
                exp_window=we,
                mul_window=wm,
                adder_ccz=terms.adder_ccz,
                lookup_ccz=terms.lookup_ccz,
                unlookup_ccz=terms.unlookup_ccz,
                table1_toffoli=GE19["table1_toffoli_billions"][key] * 1e9,
                anc_model_toffoli=GE19_WINDOWED["anc_model_toffoli"][key],
                closed_form_16=modexp_toffoli_windowed_qualtran(n, ne),
                closed_form_24=modexp_toffoli_windowed(n, ne),
            )
        )
    return GE19WindowedReproduction(
        instances=tuple(instances),
        coefficient_series=windowed_coefficient_series(),
        window_grid=tuple(
            (we, wm, windowed_total_ccz(GE19["n"], we, wm)) for we, wm in WINDOW_GRID
        ),
    )


@attrs.define(frozen=True)
class GE19WindowedInstance:
    """The windowed construction's count at one modulus size.

    ``total_ccz`` is in Qualtran's adder currency; ``bridged_ccz`` doubles the
    adder term only, converting to GE19's Cuccaro currency (ASSUMPTIONS.md §6).
    """

    n: int
    exp_bitsize: int
    coset_padding: int
    exp_window: int
    mul_window: int
    adder_ccz: int
    lookup_ccz: int
    unlookup_ccz: int
    table1_toffoli: float
    anc_model_toffoli: float
    closed_form_16: float
    closed_form_24: float

    @property
    def total_ccz(self) -> int:
        return self.adder_ccz + self.lookup_ccz + self.unlookup_ccz

    @property
    def bridged_ccz(self) -> int:
        """Total with the adder term doubled: Gidney AND-adder -> Cuccaro."""
        return self.total_ccz + self.adder_ccz

    @property
    def adder_share(self) -> float:
        return self.adder_ccz / self.total_ccz

    @property
    def table1_ratio(self) -> float:
        return self.total_ccz / self.table1_toffoli

    @property
    def bridged_table1_ratio(self) -> float:
        return self.bridged_ccz / self.table1_toffoli

    @property
    def bridged_anc_ratio(self) -> float:
        return self.bridged_ccz / self.anc_model_toffoli

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        label = f"n={self.n}"
        return (
            ReproductionRow.make(
                label, "CCZ [vs Table 1]", float(self.total_ccz), self.table1_toffoli
            ),
            ReproductionRow.make(
                label,
                "CCZ bridged [vs T1]",
                float(self.bridged_ccz),
                self.table1_toffoli,
            ),
            ReproductionRow.make(
                label, "CCZ vs 16ne n2/lg2n", float(self.total_ccz), self.closed_form_16
            ),
            ReproductionRow.make(label, "adder share", self.adder_share),
        )


@attrs.define(frozen=True)
class GE19WindowedReproduction:
    """GE19's windowed modexp, reproduced from Qualtran components.

    ``coefficient_series`` carries the 1/lg²n identification test and
    ``window_grid`` the full window sweep (ASSUMPTIONS.md §6).
    """

    instances: tuple[GE19WindowedInstance, ...]
    coefficient_series: tuple[tuple[int, float], ...] = ()
    window_grid: tuple[tuple[int, int, int], ...] = ()

    def by_n(self, n: int) -> GE19WindowedInstance:
        for inst in self.instances:
            if inst.n == n:
                return inst
        raise KeyError(f"no windowed instance for n={n}")

    @property
    def window_argmin(self) -> tuple[int, int]:
        """``(w_e, w_m)`` minimising the count over ``window_grid``."""
        if not self.window_grid:
            raise ValueError("window_grid is empty")
        we, wm, _ = min(self.window_grid, key=lambda row: row[2])
        return we, wm

    @property
    def rows(self) -> tuple[ReproductionRow, ...]:
        return tuple(row for inst in self.instances for row in inst.rows)

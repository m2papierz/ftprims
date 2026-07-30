"""GE19 §2.3-2.5 windowed modular exponentiation, built from Qualtran leaves::

    WindowedModExp                 ceil(n_e/w_e) uncontrolled multiplications
    └── WindowedModMul             2 multiply-add passes
        └── WindowedMultiplyAdd    ceil(mul_in_bits/w_m) lookup additions
            └── LookupAddition     QROAMClean -> Add -> QROAMClean.adjoint()

Costs come from ``build_call_graph`` only; ``build_composite_bloq`` materialises
real lookup tables and is for the toy-size correctness tests. Extract with
:func:`qrepro.algorithms.factoring.modexp_logical_costs`.

Leaf costs, counting conventions, parameter sources and the measured
divergences from GE19 Table 1: ASSUMPTIONS.md §6.
"""

from __future__ import annotations

import math
from functools import cached_property
from typing import TYPE_CHECKING, Union

import numpy as np
import sympy
from attrs import field, frozen
from qualtran import (
    Bloq,
    DecomposeTypeError,
    QUInt,
    Register,
    Side,
    Signature,
)
from qualtran.bloqs.arithmetic import Add
from qualtran.bloqs.basic_gates import IntState
from qualtran.bloqs.data_loading.qroam_clean import QROAMClean, QROAMCleanAdjointWrapper
from qualtran.bloqs.mod_arithmetic import ModAdd
from qualtran.resource_counting import QECGatesCost, get_bloq_call_graph, get_cost_value

from qrepro.algorithms.factoring import placeholder_modulus

if TYPE_CHECKING:
    from qualtran import BloqBuilder, Soquet, SoquetT
    from qualtran.resource_counting import BloqCountDictT, SympySymbolAllocator

#: An ``int`` for a concrete (decomposable) instance, or a ``sympy`` symbol for
#: the call-graph placeholder that collapses every iteration to a single node.
Multiplier = Union[int, sympy.Expr]


def ge19_coset_padding(n: int, n_e: float) -> int:
    """Coset padding ``g_pad = 2·lg n + lg n_e + 10`` (GE19 §2.7 L690).

    *n* is the RSA modulus bit length, *n_e* the exponent register bit length.
    """
    return int(2 * math.log2(n) + math.log2(n_e) + 10)


def ge19_exponent_bitsize(n: int) -> int:
    """Ekera-Hastad exponent length ``n_e = ceil(1.5·n)`` (GE19 L482)."""
    return math.ceil(1.5 * n)


def _require_positive_int(name: str, value: int, minimum: int = 1) -> None:
    if not isinstance(value, (int, np.integer)) or value < minimum:
        raise ValueError(f"{name} must be an int ≥ {minimum}, got {value!r}")


@frozen
class LookupAddition(Bloq):
    """One windowed lookup addition ``y += table[addr]`` (GE19 §2.5 L590-595).

    The innermost leaf, and the only level carrying magic-state cost.
    ``QROAMClean`` is required: ``QROM.adjoint()`` does not use
    measurement-based uncomputation and ``SelectSwapQROM`` is the wrong shape
    (ASSUMPTIONS.md §6).

    Parameters
    ----------
    lookup_bitsize:
        Fused address width ``k = w_e + w_m``; the table has ``2^k`` entries.
    width:
        Accumulator and lookup-output width (``n + g_pad`` in the coset regime).
    table:
        Concrete table data. ``None`` (the only value used at scale) builds the
        ``QROAMClean`` from bitsize so every lookup addition collapses to one
        call-graph node. Data enables decomposition, for toy sizes only.
    modulus:
        ``None`` uses a plain ``Add``, which is what GE19 costs. An int switches
        to ``ModAdd`` for exact arithmetic at toy sizes; never on a costing path.
    """

    lookup_bitsize: int
    width: int
    table: tuple[int, ...] | None = field(
        default=None,
        converter=lambda t: None if t is None else tuple(int(v) for v in t),
    )
    modulus: int | None = None

    def __attrs_post_init__(self) -> None:
        _require_positive_int("lookup_bitsize", self.lookup_bitsize)
        _require_positive_int("width", self.width)
        if self.table is not None:
            expected = 1 << self.lookup_bitsize
            if len(self.table) != expected:
                raise ValueError(
                    f"table must have 2^lookup_bitsize = {expected} entries, "
                    f"got {len(self.table)}"
                )
            limit = 1 << self.width
            if any(not 0 <= v < limit for v in self.table):
                raise ValueError(f"every table entry must lie in [0, 2^{self.width})")
        if self.modulus is not None:
            _require_positive_int("modulus", self.modulus, minimum=2)
            if self.modulus > (1 << self.width):
                raise ValueError(
                    f"modulus {self.modulus} does not fit in width {self.width}"
                )

    @cached_property
    def signature(self) -> Signature:
        return Signature(
            [
                Register("addr", QUInt(self.lookup_bitsize)),
                Register("y", QUInt(self.width)),
            ]
        )

    def _qrom(self) -> QROAMClean:
        """Built from bitsize unless concrete data was supplied.

        ``log_block_sizes=(0,)`` pins plain unary iteration, which is what
        GE19 L594 costs; Qualtran's auto choice emits junk ancillae GE19 does
        not budget.
        """
        if self.table is None:
            return QROAMClean.build_from_bitsize(
                (1 << self.lookup_bitsize,), (self.width,), log_block_sizes=(0,)
            )
        return QROAMClean.build_from_data(
            self.table, target_bitsizes=(self.width,), log_block_sizes=(0,)
        )

    def _adder(self) -> Bloq:
        if self.modulus is None:
            return Add(QUInt(self.width))
        return ModAdd(self.width, self.modulus)

    def build_call_graph(self, ssa: SympySymbolAllocator) -> BloqCountDictT:
        qrom = self._qrom()
        return {qrom: 1, self._adder(): 1, qrom.adjoint(): 1}

    def build_composite_bloq(
        self, bb: BloqBuilder, addr: Soquet, y: Soquet
    ) -> dict[str, SoquetT]:
        if self.table is None:
            raise DecomposeTypeError(
                f"cannot decompose {self} without table data; supply `table` "
                "(toy sizes only — at scale the data-free call graph is the "
                "costing path)"
            )
        qrom = self._qrom()
        addr, target = bb.add(qrom, selection=addr)
        if self.modulus is None:
            target, y = bb.add(self._adder(), a=target, b=y)
        else:
            target, y = bb.add(self._adder(), x=target, y=y)
        addr = bb.add(qrom.adjoint(), selection=addr, target0_=target)
        return {"addr": addr, "y": y}

    def on_classical_vals(self, addr: int, y: int) -> dict[str, int]:
        if self.table is None:
            raise ValueError(f"classical action of {self} needs table data")
        modulus = self.modulus if self.modulus is not None else (1 << self.width)
        return {"addr": addr, "y": (y + self.table[addr]) % modulus}


@frozen
class WindowedMultiplyAdd(Bloq):
    """One multiply-add pass ``y += x·k`` by windowed lookup (GE19 §2.5 L590).

    Each lookup addition fuses the ``w_e`` exponent-window bits with ``w_m``
    bits of the input factor ``x`` into one ``2^(w_e+w_m)``-entry address
    (GE19 L591), so the exponent enters as address bits rather than as a
    control. Window ``i`` contributes ``x_i · k · 2^(i·w_m)`` with
    ``k = multiplier^addr mod N``; entries are canonicalised into ``[0, N)``
    (GE19 L667-670).

    Parameters
    ----------
    multiplier:
        Base power ``g^(2^(j·w_e)) mod N`` for this exponent window, or a
        ``sympy`` symbol on the call-graph path (cost is data-independent).
    mod:
        The RSA modulus ``N``.
    width:
        Register width of both ``x`` and ``y``.
    exp_window, mul_window:
        ``w_e`` and ``w_m``.
    input_slack_bits:
        Extra bits of ``x`` iterated over beyond ``width`` (GE19 anc:170).
        Must be 0 to decompose. Sensitivity: ASSUMPTIONS.md §6.
    invert:
        Use ``-k^-1 mod N`` instead of ``k`` -- the unmultiply pass that clears
        the source register. Cost-identical, so the call graph ignores it.
    exact_modular:
        Route the addition through ``ModAdd`` for exact arithmetic at toy
        sizes. Never set on a costing path.
    """

    multiplier: Multiplier
    mod: int
    width: int
    exp_window: int
    mul_window: int
    input_slack_bits: int = 2
    invert: bool = False
    exact_modular: bool = False

    def __attrs_post_init__(self) -> None:
        _require_positive_int("width", self.width)
        _require_positive_int("exp_window", self.exp_window)
        _require_positive_int("mul_window", self.mul_window)
        _require_positive_int("mod", self.mod, minimum=3)
        if self.input_slack_bits < 0:
            raise ValueError(
                f"input_slack_bits must be ≥ 0, got {self.input_slack_bits}"
            )

    @cached_property
    def signature(self) -> Signature:
        w = QUInt(self.width)
        return Signature(
            [
                Register("addr", QUInt(self.exp_window)),
                Register("x", w),
                Register("y", w),
            ]
        )

    @property
    def mul_in_bits(self) -> int:
        """Bits of ``x`` iterated over as the input factor (GE19 anc:170)."""
        return self.width + self.input_slack_bits

    @property
    def n_lookup_additions(self) -> int:
        """``ceil(mul_in_bits / w_m)``: lookup additions the call graph charges.

        Exceeds :attr:`n_factor_windows` by one whenever the slack bits push
        ``mul_in_bits`` past a multiple of ``w_m``. The excess is charged but
        not built: the slack bits belong to no register, so the decomposition
        cannot represent them and refuses to run while they are set. The
        divergence is pinned rather than reconciled (ASSUMPTIONS.md §6).
        """
        return math.ceil(self.mul_in_bits / self.mul_window)

    @property
    def n_factor_windows(self) -> int:
        """``ceil(width / w_m)``: lookup additions the decomposition emits."""
        return len(self._windows())

    def _lookup_addition(self, lookup_bitsize: int, table=None) -> LookupAddition:
        return LookupAddition(
            lookup_bitsize=lookup_bitsize,
            width=self.width,
            table=table,
            modulus=self.mod if self.exact_modular else None,
        )

    def build_call_graph(self, ssa: SympySymbolAllocator) -> BloqCountDictT:
        # The tail window is costed at full width too (GE19 anc:171).
        return {
            self._lookup_addition(
                self.exp_window + self.mul_window
            ): self.n_lookup_additions
        }

    def _multiplier_for(self, addr: int) -> int:
        """``k = multiplier^addr mod N``, negated-inverted when unmultiplying."""
        k = pow(int(self.multiplier), addr, self.mod)
        if self.invert:
            k = (-pow(k, -1, self.mod)) % self.mod
        return k

    def _windows(self) -> list[tuple[int, int]]:
        """``(start_bit, n_bits)`` of each ``w_m``-bit window of ``x``, LSB first."""
        out = []
        for start in range(0, self.width, self.mul_window):
            out.append((start, min(self.mul_window, self.width - start)))
        return out

    def _window_term(self, x_i: int, k: int, start_bit: int) -> int:
        """One window's contribution ``x_i · k · 2^start_bit``, canonicalised
        into ``[0, N)`` (GE19 L667-670)."""
        return (x_i * k * (1 << start_bit)) % self.mod

    def _table(self, start_bit: int, win_bits: int) -> tuple[int, ...]:
        """Fused-address table for the window at ``start_bit``.

        Address ``a`` splits as ``(e, x_i)`` with the exponent window in the
        high ``w_e`` bits.
        """
        entries = []
        for a in range(1 << (self.exp_window + win_bits)):
            e, x_i = divmod(a, 1 << win_bits)
            entries.append(self._window_term(x_i, self._multiplier_for(e), start_bit))
        return tuple(entries)

    def _accumulate(self, x: int, k: int) -> int:
        """``x·k`` as the lookup additions build it up, window by window.

        Congruent to ``x·k`` mod N but not reduced to it: every window
        contributes its own canonicalised term, so the total lands somewhere in
        ``[0, n_factor_windows·N)``. That is the coset representation's
        operational content -- a plain, non-modular ``Add`` preserves the
        residue and the padding absorbs the accumulated multiples of N.
        """
        return sum(
            self._window_term((x >> start) & ((1 << win_bits) - 1), k, start)
            for start, win_bits in self._windows()
        )

    def build_composite_bloq(
        self, bb: BloqBuilder, addr: Soquet, x: Soquet, y: Soquet
    ) -> dict[str, SoquetT]:
        if isinstance(self.multiplier, sympy.Expr):
            raise DecomposeTypeError(
                f"cannot decompose {self} with symbolic multiplier"
            )
        if self.input_slack_bits:
            raise DecomposeTypeError(
                f"cannot decompose {self} with input_slack_bits="
                f"{self.input_slack_bits}; it iterates over bits the register "
                "does not have. Set input_slack_bits=0 for correctness tests."
            )
        addr_bits = bb.split(addr)
        # bb.split is MSB-first; window i (value 2^start) sits at the tail.
        x_bits = bb.split(x)
        for start, win_bits in self._windows():
            hi = self.width - start
            win = x_bits[hi - win_bits : hi]
            fused = bb.join(
                np.concatenate([addr_bits, win]),
                dtype=QUInt(self.exp_window + win_bits),
            )
            fused, y = bb.add(
                self._lookup_addition(
                    self.exp_window + win_bits, table=self._table(start, win_bits)
                ),
                addr=fused,
                y=y,
            )
            fused_bits = bb.split(fused)
            addr_bits = fused_bits[: self.exp_window]
            x_bits[hi - win_bits : hi] = fused_bits[self.exp_window :]
        return {
            "addr": bb.join(addr_bits, dtype=QUInt(self.exp_window)),
            "x": bb.join(x_bits, dtype=QUInt(self.width)),
            "y": y,
        }

    def on_classical_vals(self, addr: int, x: int, y: int) -> dict[str, int]:
        if isinstance(self.multiplier, sympy.Expr):
            raise ValueError(f"classical action of {self} needs a concrete multiplier")
        k = self._multiplier_for(addr)
        if self.exact_modular:
            return {"addr": addr, "x": x, "y": (y + x * k) % self.mod}
        # Coset regime: the register keeps a representative of y + x·k mod N,
        # not the residue -- which one depends on how the windows split `x`.
        return {
            "addr": addr,
            "x": x,
            "y": (y + self._accumulate(x, k)) % (1 << self.width),
        }


@frozen
class WindowedModMul(Bloq):
    """``x *= base_power^addr mod N``, uncontrolled (GE19 §2.5 L590).

    Two multiply-add passes (GE19 L694) -- multiply into a fresh workspace,
    then unmultiply to clear the source -- followed by a register relabel. No
    CSwap is emitted: these multiplications are uncontrolled, so unlike
    Qualtran's ``CModMulK`` the relabel is bookkeeping (ASSUMPTIONS.md §6).

    Uncontrolled means this is correct only inside the full windowed
    exponentiation loop. It has no control wire and cannot be conditionally
    skipped, so it is not a drop-in for ``CModMulK``.
    """

    base_power: Multiplier
    mod: int
    width: int
    exp_window: int
    mul_window: int
    input_slack_bits: int = 2
    exact_modular: bool = False

    def __attrs_post_init__(self) -> None:
        _require_positive_int("width", self.width)
        _require_positive_int("exp_window", self.exp_window)
        _require_positive_int("mul_window", self.mul_window)
        _require_positive_int("mod", self.mod, minimum=3)

    @cached_property
    def signature(self) -> Signature:
        return Signature(
            [
                Register("addr", QUInt(self.exp_window)),
                Register("x", QUInt(self.width)),
            ]
        )

    def _multiply_add(self, multiplier: Multiplier, *, invert: bool):
        return WindowedMultiplyAdd(
            multiplier=multiplier,
            mod=self.mod,
            width=self.width,
            exp_window=self.exp_window,
            mul_window=self.mul_window,
            input_slack_bits=self.input_slack_bits,
            invert=invert,
            exact_modular=self.exact_modular,
        )

    def build_call_graph(self, ssa: SympySymbolAllocator) -> BloqCountDictT:
        # One symbol for both passes so they collapse to a single node at
        # multiplicity 2; `invert` is cost-neutral.
        k = ssa.new_symbol("k")
        return {self._multiply_add(k, invert=False): 2}

    def build_composite_bloq(
        self, bb: BloqBuilder, addr: Soquet, x: Soquet
    ) -> dict[str, SoquetT]:
        if isinstance(self.base_power, sympy.Expr):
            raise DecomposeTypeError(
                f"cannot decompose {self} with symbolic base_power"
            )
        y = bb.allocate(self.width)
        # y += x·k
        addr, x, y = bb.add(
            self._multiply_add(self.base_power, invert=False), addr=addr, x=x, y=y
        )
        # x += y·(-k^-1)  ==>  x == 0
        addr, y, x = bb.add(
            self._multiply_add(self.base_power, invert=True), addr=addr, x=y, y=x
        )
        # GE19 L514: `x` is now |0> and is freed; `y` carries the product and
        # takes over the `x` register name.
        bb.free(x)  # raises if the unmultiply left anything behind
        return {"addr": addr, "x": y}

    def on_classical_vals(self, addr: int, x: int) -> dict[str, int]:
        if isinstance(self.base_power, sympy.Expr):
            raise ValueError(f"classical action of {self} needs a concrete base_power")
        return {
            "addr": addr,
            "x": (x * pow(self.base_power, addr, self.mod)) % self.mod,
        }


@frozen
class WindowedModExp(Bloq):
    """GE19 §2.3-2.5 windowed modular exponentiation.

    For each exponent window ``e[j·w_e : (j+1)·w_e]`` there is one uncontrolled
    multiplication by ``g^(2^(j·w_e)·e[...]) mod N`` (GE19 §2.5 L590), with all
    ``2^w_e`` values classically precomputed (GE19 L575) into the lookup tables.

    Parameters
    ----------
    base, mod:
        ``g`` and ``N``. The magic-state count is value-independent.
    exp_bitsize, x_bitsize:
        ``n_e`` and ``n``. Use ``n_e = ceil(1.5n)`` for Ekera-Hastad (GE19 L482).
    exp_window, mul_window:
        ``w_e`` and ``w_m``, defaulting to GE19 L690's published (5, 5).
    coset_padding:
        ``g_pad``; ``None`` resolves to :func:`ge19_coset_padding`. Padding is
        what lets a plain non-modular adder do modular addition (GE19 §2.4 L542).
    runway_sep:
        Carry-runway separation ``g_sep`` (GE19 §2.6). ``None`` means runways
        are off and excluded from the count (ASSUMPTIONS.md §6).
    input_slack_bits, exact_modular:
        See :class:`WindowedMultiplyAdd`.
    """

    base: int
    mod: int
    exp_bitsize: int
    x_bitsize: int
    exp_window: int = 5
    mul_window: int = 5
    coset_padding: int | None = None
    runway_sep: int | None = None
    input_slack_bits: int = 2
    exact_modular: bool = False

    def __attrs_post_init__(self) -> None:
        _require_positive_int("exp_bitsize", self.exp_bitsize)
        _require_positive_int("x_bitsize", self.x_bitsize)
        _require_positive_int("exp_window", self.exp_window)
        _require_positive_int("mul_window", self.mul_window)
        _require_positive_int("mod", self.mod, minimum=3)
        if self.mod % 2 == 0:
            raise ValueError(f"mod must be odd (RSA modulus), got {self.mod}")
        if not 0 < self.base < self.mod:
            raise ValueError(f"base must lie in (0, mod={self.mod}), got {self.base}")
        if math.gcd(self.base, self.mod) != 1:
            raise ValueError(f"base {self.base} must be coprime to mod {self.mod}")
        if self.coset_padding is not None and self.coset_padding < 0:
            raise ValueError(f"coset_padding must be ≥ 0, got {self.coset_padding}")
        if self.runway_sep is not None:
            _require_positive_int("runway_sep", self.runway_sep)
        if self.exact_modular and self.padding:
            raise ValueError(
                "exact_modular requires coset_padding=0: exact ModAdd arithmetic "
                "and the coset representation are alternative ways to handle the "
                "modular reduction, not composable ones"
            )

    @property
    def padding(self) -> int:
        """``g_pad``, resolved from GE19 L690 when not given explicitly."""
        if self.coset_padding is not None:
            return self.coset_padding
        return ge19_coset_padding(self.x_bitsize, self.exp_bitsize)

    @property
    def piece_count(self) -> int:
        """Carry-runway pieces; 1 when runways are off (GE19 anc:166)."""
        if self.runway_sep is None:
            return 1
        return math.ceil(self.x_bitsize / self.runway_sep)

    @property
    def width(self) -> int:
        """Padded register width. Each runway piece carries its own ``g_pad``."""
        return self.x_bitsize + self.padding * self.piece_count

    @property
    def n_exponent_windows(self) -> int:
        """``ceil(n_e / w_e)`` uncontrolled multiplications (GE19 L590)."""
        return math.ceil(self.exp_bitsize / self.exp_window)

    @cached_property
    def signature(self) -> Signature:
        return Signature(
            [
                Register("exponent", QUInt(self.exp_bitsize)),
                Register("x", QUInt(self.width), side=Side.RIGHT),
            ]
        )

    def _mod_mul(self, base_power: Multiplier) -> WindowedModMul:
        return WindowedModMul(
            base_power=base_power,
            mod=self.mod,
            width=self.width,
            exp_window=self.exp_window,
            mul_window=self.mul_window,
            input_slack_bits=self.input_slack_bits,
            exact_modular=self.exact_modular,
        )

    def build_call_graph(self, ssa: SympySymbolAllocator) -> BloqCountDictT:
        # One symbol for every exponent window so all ceil(n_e/w_e) iterations
        # collapse to a single node. Concrete per-window base powers would make
        # each a distinct bloq and the count would not terminate at n=2048.
        k = ssa.new_symbol("k")
        return {
            self._mod_mul(k): self.n_exponent_windows,
            IntState(val=1, bitsize=self.width): 1,
        }

    def build_composite_bloq(
        self, bb: BloqBuilder, exponent: Soquet
    ) -> dict[str, SoquetT]:
        if self.input_slack_bits:
            raise DecomposeTypeError(
                f"cannot decompose {self} with input_slack_bits="
                f"{self.input_slack_bits}; set it to 0 for correctness tests."
            )
        x = bb.add(IntState(val=1, bitsize=self.width))
        exp_bits = bb.split(exponent)
        base_power = self.base % self.mod
        # Right-to-left: window 0 is the least significant w_e exponent bits,
        # which sit at the TAIL of the MSB-first split array.
        for start in range(0, self.exp_bitsize, self.exp_window):
            win_bits = min(self.exp_window, self.exp_bitsize - start)
            hi = self.exp_bitsize - start
            addr = bb.join(exp_bits[hi - win_bits : hi], dtype=QUInt(win_bits))
            mod_mul = WindowedModMul(
                base_power=base_power,
                mod=self.mod,
                width=self.width,
                exp_window=win_bits,
                mul_window=self.mul_window,
                input_slack_bits=self.input_slack_bits,
                exact_modular=self.exact_modular,
            )
            addr, x = bb.add(mod_mul, addr=addr, x=x)
            exp_bits[hi - win_bits : hi] = bb.split(addr)
            # Next window's base: g^(2^((j+1)·w_e)).
            base_power = pow(base_power, 1 << win_bits, self.mod)
        return {"exponent": bb.join(exp_bits, dtype=QUInt(self.exp_bitsize)), "x": x}

    def on_classical_vals(self, exponent: int) -> dict[str, int]:
        return {"exponent": exponent, "x": pow(self.base, exponent, self.mod)}


def make_ge19_windowed_modexp(
    n_bits: int,
    *,
    base: int = 7,
    exp_window: int = 5,
    mul_window: int = 5,
    exp_bitsize: int | None = None,
    coset_padding: int | None = None,
    runway_sep: int | None = None,
    input_slack_bits: int = 2,
) -> WindowedModExp:
    """Build GE19's windowed ``ModExp`` for an *n_bits*-bit RSA modulus.

    Every default is a GE19-published value; sources and sensitivities are in
    ASSUMPTIONS.md §2/§6.

    Parameters
    ----------
    n_bits:
        RSA modulus bit length (e.g. 2048).
    base:
        Exponentiation base ``g`` (does not affect the gate count).
    exp_window, mul_window:
        ``w_e`` and ``w_m``; swept in ``experiments/sweep_windowed_modexp.py``.
    exp_bitsize:
        ``n_e``; defaults to ``ceil(1.5·n)``. Pass ``2*n_bits`` for Shor.
    coset_padding, runway_sep, input_slack_bits:
        See :class:`WindowedModExp`.
    """
    mod = placeholder_modulus(n_bits, base)
    return WindowedModExp(
        base=base,
        mod=mod,
        exp_bitsize=(
            exp_bitsize if exp_bitsize is not None else ge19_exponent_bitsize(n_bits)
        ),
        x_bitsize=n_bits,
        exp_window=exp_window,
        mul_window=mul_window,
        coset_padding=coset_padding,
        runway_sep=runway_sep,
        input_slack_bits=input_slack_bits,
    )


#: Call-graph frontier for the term breakdown: stop descending here so each of
#: GE19's three cost terms stays separable.
_TERM_LEAVES = (Add, ModAdd, QROAMClean, QROAMCleanAdjointWrapper)


@frozen
class WindowedTermCosts:
    """Magic-state count split across GE19 §2.5 L593-595's three cost terms."""

    adder_ccz: int
    lookup_ccz: int
    unlookup_ccz: int

    @property
    def total_ccz(self) -> int:
        return self.adder_ccz + self.lookup_ccz + self.unlookup_ccz

    @property
    def adder_bridged_total_ccz(self) -> int:
        """Total with the adder term, and only the adder term, doubled.

        Converts Qualtran's Gidney AND-adder to GE19's Cuccaro convention;
        reported beside the unbridged total, never in place of it
        (ASSUMPTIONS.md §6).
        """
        return self.total_ccz + self.adder_ccz


def windowed_term_breakdown(bloq: Bloq) -> WindowedTermCosts:
    """Split *bloq*'s magic-state count into GE19's three terms.

    Walks the call graph with a ``keep`` frontier at the adder / lookup /
    unlookup leaves, so no wires are expanded. *bloq* is a
    :class:`WindowedModExp` or any bloq built from those leaves.
    """
    _, sigma = get_bloq_call_graph(bloq, keep=lambda b: isinstance(b, _TERM_LEAVES))
    adder = lookup = unlookup = 0
    for leaf, multiplicity in sigma.items():
        counts = get_cost_value(leaf, QECGatesCost()).total_t_and_ccz_count(
            ts_per_rotation=0
        )
        ccz = int(counts["n_ccz"]) * int(multiplicity)
        if isinstance(leaf, (Add, ModAdd)):
            adder += ccz
        elif isinstance(leaf, QROAMCleanAdjointWrapper):
            unlookup += ccz
        elif isinstance(leaf, QROAMClean):
            lookup += ccz
        elif ccz:
            # An unclassified non-zero leaf means the construction grew a term
            # this attribution does not model; fail rather than drop it.
            raise ValueError(
                f"unclassified non-zero leaf {type(leaf).__name__} contributing "
                f"{ccz} CCZ; the term breakdown no longer covers the construction"
            )
    return WindowedTermCosts(adder_ccz=adder, lookup_ccz=lookup, unlookup_ccz=unlookup)

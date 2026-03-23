"""Build QREF v1 program descriptions from benchmark results.

QREF is a hierarchical-DAG format for fault-tolerant resource estimation.
See https://github.com/PsiQ/qref for the spec.

Two export modes are supported:

**Numeric** (default): exports a flat leaf routine with concrete resource
values extracted from a real Qualtran benchmark run. This is the
authoritative cost source.

**Symbolic** (``--symbolic``): exports **approximate analytic formulas**
that depend on ``input_params`` so that Bartiq can compile and evaluate
them.  These formulas are *textbook-level approximations* — they capture
the dominant scaling term but may omit lower-order additive constants
and do not reproduce the exact gate counts that Qualtran computes.

.. warning::

   Symbolic mode is **not** a faithful export of the numeric benchmark.
   It is a separate, simplified analytic model intended for quick
   asymptotic exploration with Bartiq.  Use ``export-qref --check`` to
   compare the symbolic approximation against a real numeric run.

Programs are validated through ``qref.SchemaV1`` before serialisation.
"""

from __future__ import annotations

from typing import Any

import yaml
from qref import SchemaV1

from ftprims.algorithms._base import LogicalCosts
from ftprims.config import DEFAULT_CONFIG, QREFConfig


# ---------------------------------------------------------------------------
# Symbolic cost formulas — APPROXIMATE ANALYTIC MODEL
# ---------------------------------------------------------------------------
# IMPORTANT: These are NOT derived from the Qualtran benchmark.  They are
# hand-written textbook-level approximations that capture the dominant
# asymptotic scaling term.  They may diverge from the numeric benchmark
# at concrete parameter values, especially for small n or when Qualtran's
# decomposition includes additive constants, ancilla management overhead,
# or implementation-specific optimisations not reflected here.
#
# Use ``check_symbolic_consistency()`` to compare these approximations
# against the real numeric benchmark at any concrete parameter point.
#
# Each key is ``(primitive, variant_or_op)`` — e.g. ``("qft", "textbook")``.
# ``required_params`` lists the symbols the formulas reference.

_SymbolicEntry = dict[str, Any]  # keys: required_params, resources

_SYMBOLIC_COSTS: dict[tuple[str, str], _SymbolicEntry] = {
    # -- QFT --
    # The textbook QFT on n qubits has n(n-1)/2 controlled-rotation
    # pairs.  Qualtran splits these into CCZ gates (T_gates_direct)
    # and true rotations depending on the angle; the symbolic model
    # counts them all as rotations (dominant FTQC cost after synthesis).
    ("qft", "textbook"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "0",
            "rotations": "n*(n - 1)/2",
            "cliffords": "n*(n - 1)/2",
            "n_qubits": "n + 1",
        },
    },
    # ApproximateQFT uses phase-gradient rotations with ancillae,
    # converting most rotations to Clifford additions.  The qubit
    # count is larger (ancilla registers) and the non-Clifford cost
    # drops dramatically.  These formulas are rough upper bounds;
    # Qualtran's implementation may differ significantly.
    ("qft", "approx"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "0",
            "rotations": "0",
            "cliffords": "n + n//2",
            "n_qubits": "n + n//2",
        },
    },
    # -- QPE --
    # TextbookQPE = inverse QFT on m-qubit register + m applications
    # of controlled-U^(2^k).  The controlled-U cost is unitary-
    # dependent and cannot be expressed symbolically without knowing
    # the unitary.  These formulas cover only the inverse QFT part.
    ("qpe", "default"): {
        "required_params": ["m"],
        "resources": {
            "T_gates_direct": "0",
            "rotations": "m*(m - 1)/2",
            "cliffords": "m*(m - 1)/2",
            "n_qubits": "m + 2",
        },
    },
    # -- Arithmetic --
    # Qualtran's Add(n) uses n-1 And gates (each costing 4 T-gates),
    # plus ancilla qubits for the And gate outputs.
    # Qubits: 2 input registers (2*n) + n-1 And ancillas = 3*n - 1.
    ("arithmetic", "add"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "4*(n - 1)",
            "rotations": "0",
            "cliffords": "8*n",
            "n_qubits": "3*n - 1",
        },
    },
    ("arithmetic", "add_oop"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "4*n",
            "rotations": "0",
            "cliffords": "8*n",
            "n_qubits": "3*n + 1",
        },
    },
    ("arithmetic", "leq"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "4*(2*n - 1)",
            "rotations": "0",
            "cliffords": "8*n",
            "n_qubits": "2*n + 1",
        },
    },
    # Product(n, n) decomposes into n*(2n-1) And gates via
    # schoolbook multiplication.  T_direct = 4 * n*(2n-1).
    # Qualtran's QECGatesCost reports 0 Cliffords at this level.
    ("arithmetic", "mul"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "4*n*(2*n - 1)",
            "rotations": "0",
            "cliffords": "0",
            "n_qubits": "4*n",
        },
    },
    # ModAdd composes ~5 adders/comparators internally.
    ("arithmetic", "modadd"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "20*n",
            "rotations": "0",
            "cliffords": "40*n",
            "n_qubits": "2*n + 1",
        },
    },
    # -- QROM --
    # Basic QROM uses data_size - 1 multi-controlled gates,
    # each costing ~4 T-gates (one And gate).
    ("qrom", "basic"): {
        "required_params": ["data_size", "target_bitsize"],
        "resources": {
            "T_gates_direct": "4*(data_size - 1)",
            "rotations": "0",
            "cliffords": "4*data_size",
            "n_qubits": "ceil(log2(data_size)) + target_bitsize",
        },
    },
    # SelectSwapQROM trades ancillae for fewer T-gates.  The cost
    # depends on the block-size parameter k; at the default k≈log2(√N)
    # the T-count scales as O(√N · target_bitsize).  This formula
    # captures the asymptotic trend but may diverge at small N.
    ("qrom", "selectswap"): {
        "required_params": ["data_size", "target_bitsize"],
        "resources": {
            "T_gates_direct": "4*ceil(sqrt(data_size))*target_bitsize",
            "rotations": "0",
            "cliffords": "4*data_size",
            "n_qubits": "ceil(log2(data_size)) + 2*target_bitsize",
        },
    },
}


def _resolve_variant_key(primitive: str, params: dict[str, Any]) -> tuple[str, str]:
    """Determine the ``(primitive, variant_or_op)`` lookup key.

    Falls back to ``"default"`` when no variant/op parameter is present.
    """
    variant = str(params.get("variant", params.get("op", "default")))
    return (primitive, variant)


def build_qref_program(
    name: str,
    params: dict[str, Any],
    costs: LogicalCosts,
    *,
    symbolic: bool = False,
    children: list[dict] | None = None,
    port_size: int | None = None,
    cfg: QREFConfig | None = None,
) -> dict:
    """Create a QREF v1 program dict.

    Parameters
    ----------
    name:
        Routine name (e.g. ``"qft_textbook"``).
    params:
        Algorithm parameters recorded as ``input_params``.
    costs:
        Logical-level resource counts (used in numeric mode).
    symbolic:
        When True, emit **approximate** symbolic resource expressions
        suitable for Bartiq compilation.  These are textbook-level
        formulas, not a faithful export of the numeric benchmark.
    children:
        Optional child routines for hierarchical programs.
    port_size:
        If given, generate ``in``/``out`` ports of this size.
    cfg:
        QREF export configuration.
    """
    cfg = cfg or DEFAULT_CONFIG.qref

    ports: list[dict[str, Any]] = []
    if port_size is not None:
        ports = [
            {"name": "in", "direction": "input", "size": port_size},
            {"name": "out", "direction": "output", "size": port_size},
        ]

    if symbolic:
        key = _resolve_variant_key(name, params)
        resources, required_params = _build_symbolic_resources(key)
        # Ensure all symbols referenced in formulas appear in input_params.
        input_params = list(dict.fromkeys(list(params.keys()) + required_params))
    else:
        resources = _build_numeric_resources(costs)
        input_params = list(params.keys())

    program: dict[str, Any] = {
        "version": cfg.version,
        "program": {
            "name": name,
            "ports": ports,
            "resources": resources,
            "input_params": input_params,
            "children": children or [],
            "connections": [],
        },
    }

    if symbolic:
        program["_meta"] = {
            "cost_model": "approximate_analytic",
            "note": (
                "Resource expressions are textbook-level approximations. "
                "They capture dominant scaling but may diverge from the "
                "numeric Qualtran benchmark at concrete parameter values. "
                "Use 'ftprims export-qref --check' to compare."
            ),
        }

    if cfg.validate:
        schema = SchemaV1(**program)
        program = schema.model_dump()
        # SchemaV1 strips unknown keys; re-attach _meta after validation.
        if symbolic:
            program["_meta"] = {
                "cost_model": "approximate_analytic",
                "note": (
                    "Resource expressions are textbook-level approximations. "
                    "They capture dominant scaling but may diverge from the "
                    "numeric Qualtran benchmark at concrete parameter values. "
                    "Use 'ftprims export-qref --check' to compare."
                ),
            }

    return program


def save_qref(program: dict, path: str) -> None:
    """Dump QREF program to YAML."""
    with open(path, "w") as f:
        yaml.safe_dump(program, f, sort_keys=False)


def _build_numeric_resources(costs: LogicalCosts) -> list[dict[str, Any]]:
    """Concrete resource values from computed LogicalCosts."""
    return [
        {"name": "T_gates_ftqc", "type": "additive", "value": costs.t_count_ftqc},
        {"name": "T_gates_direct", "type": "additive", "value": costs.t_count_direct},
        {"name": "rotations", "type": "additive", "value": costs.rotation_count},
        {"name": "cliffords", "type": "additive", "value": costs.clifford_count},
        {
            "name": "n_qubits",
            "type": "additive",
            "value": costs.logical_qubits_estimate,
        },
    ]


def _build_symbolic_resources(
    key: tuple[str, str],
) -> tuple[list[dict[str, Any]], list[str]]:
    """Symbolic resource expressions for Bartiq compilation.

    Returns ``(resources_list, required_params)`` so the caller can
    merge required params into the program's ``input_params``.

    .. note::

       These are approximate analytic formulas, not a faithful
       representation of the numeric benchmark.
    """
    entry = _SYMBOLIC_COSTS.get(key)
    if entry is None:
        available = sorted(f"{p}/{v}" for p, v in _SYMBOLIC_COSTS)
        raise ValueError(
            f"No symbolic cost formulas for {key[0]!r} variant/op "
            f"{key[1]!r}; available: {available}"
        )
    resources = [
        {"name": name, "type": "additive", "value": expr}
        for name, expr in entry["resources"].items()
    ]
    return resources, list(entry["required_params"])


def check_symbolic_consistency(
    primitive: str,
    params: dict[str, Any],
    numeric_costs: LogicalCosts,
) -> dict[str, Any]:
    """Compare the symbolic approximation against a real numeric benchmark.

    Returns a dict with:
      - ``available``: whether symbolic formulas exist for this primitive/variant
      - ``consistent``: True when every comparable field matches exactly
      - ``comparisons``: per-resource ``{symbolic, numeric, match, relative_error}``

    This lets users (and CI) verify how far the analytic model drifts
    from the authoritative Qualtran numbers at concrete parameter values.
    """
    import math as _math

    key = _resolve_variant_key(primitive, params)
    entry = _SYMBOLIC_COSTS.get(key)
    if entry is None:
        return {
            "available": False,
            "reason": f"No symbolic formulas for {key[0]!r}/{key[1]!r}",
        }

    # Evaluate symbolic formulas with concrete parameter values.
    safe_ns: dict[str, Any] = {
        **{k: v for k, v in params.items() if isinstance(v, (int, float))},
        "ceil": _math.ceil,
        "log2": _math.log2,
        "sqrt": _math.sqrt,
    }

    symbolic_vals: dict[str, int | str] = {}
    for name, expr in entry["resources"].items():
        try:
            symbolic_vals[name] = int(
                eval(expr, {"__builtins__": {}}, safe_ns)
            )  # noqa: S307
        except Exception as exc:
            symbolic_vals[name] = f"eval error: {exc}"

    numeric_vals: dict[str, int] = {
        "T_gates_direct": numeric_costs.t_count_direct,
        "rotations": numeric_costs.rotation_count,
        "cliffords": numeric_costs.clifford_count,
        "n_qubits": numeric_costs.logical_qubits_estimate,
    }

    comparisons: dict[str, dict[str, Any]] = {}
    for field in sorted(set(symbolic_vals) | set(numeric_vals)):
        s = symbolic_vals.get(field)
        n = numeric_vals.get(field)
        if isinstance(s, int) and isinstance(n, int):
            rel_err = abs(s - n) / max(n, 1) if n else None
            comparisons[field] = {
                "symbolic": s,
                "numeric": n,
                "match": s == n,
                "relative_error": round(rel_err, 4) if rel_err is not None else None,
            }
        else:
            comparisons[field] = {"symbolic": s, "numeric": n, "match": None}

    all_match = all(
        c.get("match") is True
        for c in comparisons.values()
        if c.get("match") is not None
    )

    max_rel = max(
        (c.get("relative_error") or 0.0)
        for c in comparisons.values()
        if c.get("match") is not None
    )

    return {
        "available": True,
        "consistent": all_match,
        "max_relative_error": round(max_rel, 4),
        "comparisons": comparisons,
    }

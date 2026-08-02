"""QREF v1 export (https://github.com/PsiQ/qref).

Numeric mode exports a flat leaf routine holding concrete Qualtran values and
is the authoritative cost source. Symbolic mode exports the textbook-level
analytic formulas in :data:`_SYMBOLIC_COSTS` so Bartiq can compile and evaluate
them; those capture the dominant scaling term only and diverge from the numeric
benchmark. ``check_symbolic_consistency`` measures the divergence.

Programs are validated through ``qref.SchemaV1`` before serialisation.
"""

from __future__ import annotations

from typing import Any

import yaml
from qref import SchemaV1

from qrepro.algorithms._base import LogicalCosts
from qrepro.config import DEFAULT_CONFIG, QREFConfig

# Hand-written asymptotic formulas, not derived from the Qualtran benchmark.
# Keyed by ``(primitive, variant_or_op)``; ``required_params`` lists the symbols
# the formulas reference.

_SymbolicEntry = dict[str, Any]  # keys: required_params, resources

_SYMBOLIC_COSTS: dict[tuple[str, str], _SymbolicEntry] = {
    # n(n-1)/2 controlled-rotation pairs. Qualtran splits these into CCZ gates
    # and true rotations by angle; the symbolic model counts them all as
    # rotations, the dominant FTQC cost after synthesis.
    ("qft", "textbook"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "0",
            "rotations": "n*(n - 1)/2",
            "cliffords": "n*(n - 1)/2",
            "n_qubits": "n + 1",
        },
    },
    # Phase-gradient rotations with ancillae turn most rotations into Clifford
    # additions: more qubits, far less non-Clifford cost. Rough upper bounds.
    ("qft", "approx"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "0",
            "rotations": "0",
            "cliffords": "n + n//2",
            "n_qubits": "n + n//2",
        },
    },
    # Inverse QFT on the m-qubit register plus m applications of
    # controlled-U^(2^k). The controlled-U cost depends on the unitary, so
    # these formulas cover the inverse QFT only.
    ("qpe", "default"): {
        "required_params": ["m"],
        "resources": {
            "T_gates_direct": "0",
            "rotations": "m*(m - 1)/2",
            "cliffords": "m*(m - 1)/2",
            "n_qubits": "m + 2",
        },
    },
    # Add(n): n-1 And gates at 4 T each, plus one ancilla per And output, so
    # 2*n input qubits + n-1 ancillae.
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
    # Schoolbook Product(n, n): n*(2n-1) And gates. QECGatesCost reports zero
    # Cliffords at this level.
    ("arithmetic", "mul"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "4*n*(2*n - 1)",
            "rotations": "0",
            "cliffords": "0",
            "n_qubits": "4*n",
        },
    },
    # ModAdd composes about five adders and comparators.
    ("arithmetic", "modadd"): {
        "required_params": ["n"],
        "resources": {
            "T_gates_direct": "20*n",
            "rotations": "0",
            "cliffords": "40*n",
            "n_qubits": "2*n + 1",
        },
    },
    # data_size - 1 multi-controlled gates, one And (4 T) each.
    ("qrom", "basic"): {
        "required_params": ["data_size", "target_bitsize"],
        "resources": {
            "T_gates_direct": "4*(data_size - 1)",
            "rotations": "0",
            "cliffords": "4*data_size",
            "n_qubits": "ceil(log2(data_size)) + target_bitsize",
        },
    },
    # At the default block size k = log2(sqrt(N)) the T-count scales as
    # O(sqrt(N) * target_bitsize). Diverges at small N.
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


_SYMBOLIC_META: dict[str, str] = {
    "cost_model": "approximate_analytic",
    "note": (
        "Resource expressions are textbook-level approximations. "
        "They capture dominant scaling but may diverge from the "
        "numeric Qualtran benchmark at concrete parameter values. "
        "Use 'qrepro export-qref --check' to compare."
    ),
}


def _resolve_variant_key(primitive: str, params: dict[str, Any]) -> tuple[str, str]:
    """The ``(primitive, variant_or_op)`` lookup key; ``"default"`` when the
    params carry neither ``variant`` nor ``op``."""
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

    *params* is recorded as ``input_params``. *costs* is used in numeric mode
    only; *symbolic* emits the analytic expressions instead. *port_size*
    generates ``in``/``out`` ports of that size.
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
        # Every symbol the formulas reference must appear in input_params.
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
        program["_meta"] = dict(_SYMBOLIC_META)

    if cfg.validate:
        schema = SchemaV1(**program)
        program = schema.model_dump()
        # SchemaV1 strips unknown keys; re-attach _meta after validation.
        if symbolic:
            program["_meta"] = dict(_SYMBOLIC_META)

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
    """``(resources, required_params)`` for the analytic model at *key*."""
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
    """Compare the analytic model against a numeric benchmark run.

    Returns ``available`` (whether formulas exist for this primitive/variant),
    ``consistent`` (every comparable field matches exactly),
    ``max_relative_error``, and per-resource ``comparisons`` of
    ``{symbolic, numeric, match, relative_error}``.
    """
    import math as _math

    key = _resolve_variant_key(primitive, params)
    entry = _SYMBOLIC_COSTS.get(key)
    if entry is None:
        return {
            "available": False,
            "reason": f"No symbolic formulas for {key[0]!r}/{key[1]!r}",
        }

    safe_ns: dict[str, Any] = {
        **{k: v for k, v in params.items() if isinstance(v, (int, float))},
        "ceil": _math.ceil,
        "log2": _math.log2,
        "sqrt": _math.sqrt,
    }

    symbolic_vals: dict[str, int | str] = {}
    for name, expr in entry["resources"].items():
        try:
            symbolic_vals[name] = int(eval(expr, {"__builtins__": {}}, safe_ns))  # noqa: S307
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

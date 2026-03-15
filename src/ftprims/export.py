"""Build QREF v1 program descriptions from benchmark results.

QREF is a hierarchical-DAG format for fault-tolerant resource estimation.
See https://github.com/PsiQ/qref for the spec.

Two export modes are supported:

**Numeric** (default): exports a flat leaf routine with concrete resource
values.  Useful for archiving results but Bartiq has nothing to compile.

**Symbolic**: exports resource expressions that depend on ``input_params``
so that Bartiq can compile the routine and ``evaluate(...)`` can
substitute concrete values.  Symbolic expressions are derived from the
known cost formulas for each primitive (e.g. QFT rotations ~ n(n-1)/2).

Programs are validated through ``qref.SchemaV1`` before serialisation.
"""

from __future__ import annotations

from typing import Any

import yaml
from qref import SchemaV1

from ftprims.algorithms._base import LogicalCosts
from ftprims.config import DEFAULT_CONFIG, QREFConfig


# Symbolic cost formulas
# Each entry maps a primitive name to a dict of resource-name => SymPy
# expression string using the primitive's input_params.
# These are the textbook / Qualtran formulas.

_SYMBOLIC_COSTS: dict[str, dict[str, str]] = {
    "qft": {
        # Textbook QFT: n(n-1)/2 rotations, each needing synthesis.
        # Direct T from rotations = 0 (all cost is in rotation synthesis).
        "T_gates_direct": "0",
        "rotations": "n*(n - 1)/2",
        "cliffords": "n*(n - 1)/2",
        "n_qubits": "n",
    },
    "qpe": {
        # QPE with m precision bits: 2^m - 1 controlled-U applications
        # plus the inverse QFT on m qubits.
        "T_gates_direct": "0",
        "rotations": "m*(m - 1)/2 + (2**m - 1)",
        "cliffords": "m*(m - 1)/2",
        "n_qubits": "m + 1",
    },
    "arithmetic": {
        # Add (in-place): ~4n T-gates, no rotations.
        "T_gates_direct": "4*n",
        "rotations": "0",
        "cliffords": "8*n",
        "n_qubits": "2*n",
    },
    "qrom": {
        # Basic QROM: ~4·data_size T-gates (And-based decomposition).
        "T_gates_direct": "4*data_size",
        "rotations": "0",
        "cliffords": "4*data_size",
        "n_qubits": "ceil(log2(data_size)) + target_bitsize",
    },
}


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
        When True, emit symbolic resource expressions suitable for
        Bartiq compilation.  When False (default), emit concrete values.
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
        resources = _build_symbolic_resources(name)
    else:
        resources = _build_numeric_resources(costs)

    program: dict[str, Any] = {
        "version": cfg.version,
        "program": {
            "name": name,
            "ports": ports,
            "resources": resources,
            "input_params": list(params.keys()),
            "children": children or [],
            "connections": [],
        },
    }

    if cfg.validate:
        schema = SchemaV1(**program)
        program = schema.model_dump()

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
        {"name": "n_qubits", "type": "additive", "value": costs.qubits},
    ]


def _build_symbolic_resources(primitive: str) -> list[dict[str, Any]]:
    """Symbolic resource expressions for Bartiq compilation."""
    formulas = _SYMBOLIC_COSTS.get(primitive)
    if formulas is None:
        raise ValueError(
            f"No symbolic cost formulas for {primitive!r}; "
            f"available: {sorted(_SYMBOLIC_COSTS)}"
        )
    return [
        {"name": name, "type": "additive", "value": expr}
        for name, expr in formulas.items()
    ]

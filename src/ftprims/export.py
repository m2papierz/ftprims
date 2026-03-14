"""Build QREF v1 program descriptions from benchmark results.

QREF is a hierarchical-DAG format for fault-tolerant resource estimation.
See https://github.com/PsiQ/qref for the spec.
"""

from __future__ import annotations

from typing import Any

import yaml

from ftprims.algorithms._base import LogicalCosts


def build_qref_program(
    name: str,
    params: dict[str, Any],
    costs: LogicalCosts,
    *,
    children: list[dict] | None = None,
    port_size: int | None = None,
) -> dict:
    """Create a QREF v1 program dict.

    Parameters
    ----------
    name:
        Routine name (e.g. ``"qft_textbook"``).
    params:
        Algorithm parameters recorded as ``input_params``.
    costs:
        Logical-level resource counts to embed.
    children:
        Optional child routines for hierarchical programs.
    port_size:
        If given, generate ``in``/``out`` ports of this size.
    """
    ports: list[dict[str, Any]] = []
    if port_size is not None:
        ports = [
            {"name": "in", "direction": "input", "size": port_size},
            {"name": "out", "direction": "output", "size": port_size},
        ]

    program: dict[str, Any] = {
        "version": "v1",
        "program": {
            "name": name,
            "type": "null",
            "ports": ports,
            "resources": [
                {"name": "T_gates", "type": "additive", "value": costs.t_count},
                {
                    "name": "cliffords",
                    "type": "additive",
                    "value": costs.clifford_count,
                },
                {
                    "name": "rotations",
                    "type": "additive",
                    "value": costs.rotation_count,
                },
                {"name": "n_qubits", "type": "additive", "value": costs.qubits},
            ],
            "input_params": list(params.keys()),
            "children": children or [],
            "connections": [],
        },
    }
    return program


def save_qref(program: dict, path: str) -> None:
    """Dump QREF program to YAML."""
    with open(path, "w") as f:
        yaml.safe_dump(program, f, sort_keys=False)

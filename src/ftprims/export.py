"""
Build QREF v1 program descriptions from benchmark results.

See https://github.com/PsiQ/qref for the schema.
"""

from __future__ import annotations

from typing import Any

import yaml

from ftprims.algorithms._base import LogicalCosts


def build_qref_program(
    name: str,
    params: dict[str, Any],
    costs: LogicalCosts,
    children: list[dict] | None = None,
) -> dict:
    """Create a QREF-compatible program dict.

    See https://github.com/PsiQ/qref for the schema.
    """
    program: dict[str, Any] = {
        "version": "v1",
        "program": {
            "name": name,
            "type": "null",
            "ports": [],
            "resources": [
                {"name": "T_gates", "value": costs.t_count, "type": "additive"},
                {"name": "qubits", "value": costs.qubits, "type": "other"},
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

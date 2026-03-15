"""Build QREF v1 program descriptions from benchmark results.

QREF is a hierarchical-DAG format for fault-tolerant resource estimation.
See https://github.com/PsiQ/qref for the spec.

Programs are validated through ``qref.SchemaV1`` before serialisation.
"""

from __future__ import annotations

from typing import Any

import yaml
from qref import SchemaV1

from ftprims.algorithms._base import LogicalCosts
from ftprims.config import DEFAULT_CONFIG, QREFConfig


def build_qref_program(
    name: str,
    params: dict[str, Any],
    costs: LogicalCosts,
    *,
    children: list[dict] | None = None,
    port_size: int | None = None,
    cfg: QREFConfig | None = None,
) -> dict:
    """Create a QREF v1 program dict.

    When ``cfg.validate`` is True (the default) the dict is round-tripped
    through ``qref.SchemaV1`` so that schema errors surface immediately.

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

    program: dict[str, Any] = {
        "version": cfg.version,
        "program": {
            "name": name,
            "ports": ports,
            "resources": [
                {
                    "name": "T_gates_ftqc",
                    "type": "additive",
                    "value": costs.t_count_ftqc,
                },
                {
                    "name": "T_gates_direct",
                    "type": "additive",
                    "value": costs.t_count_direct,
                },
                {
                    "name": "rotations",
                    "type": "additive",
                    "value": costs.rotation_count,
                },
                {
                    "name": "cliffords",
                    "type": "additive",
                    "value": costs.clifford_count,
                },
                {"name": "n_qubits", "type": "additive", "value": costs.qubits},
            ],
            "input_params": list(params.keys()),
            "children": children or [],
            "connections": [],
        },
    }

    if cfg.validate:
        # Round-trip through SchemaV1 to catch schema errors early.
        schema = SchemaV1(**program)
        program = schema.model_dump()

    return program


def save_qref(program: dict, path: str) -> None:
    """Dump QREF program to YAML."""
    with open(path, "w") as f:
        yaml.safe_dump(program, f, sort_keys=False)

"""QREF export round-trip and breakdown per-item correctness tests."""

from __future__ import annotations

import pytest
import yaml

from qrepro.algorithms import registry
from qrepro.breakdown import extract_structural_breakdown
from qrepro.config import DEFAULT_CONFIG
from qrepro.export import build_qref_program, save_qref

QREF_CASES = [
    ("qft", dict(n=32, variant="textbook"), 16),
    ("qft", dict(n=32, variant="approx"), 16),
    ("arithmetic", dict(n=16, op="add"), 16),
    ("arithmetic", dict(n=16, op="mul"), 16),
    ("qpe", dict(m=8, phi=0.25), None),
    ("qrom", dict(data_size=256, variant="basic"), None),
]


def _case_id(c):
    return f"{c[0]}_{'_'.join(str(v) for v in c[1].values())}"


@pytest.mark.parametrize(
    "name,params,port_size",
    QREF_CASES,
    ids=[_case_id(c) for c in QREF_CASES],
)
def test_qref_numeric_round_trip(name, params, port_size, tmp_path):
    """Export QREF numeric YAML, reload it, verify resources match logical costs."""
    bench = registry[name]
    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    out_path = tmp_path / f"qref_{name}.yaml"
    program = build_qref_program(
        name,
        params,
        costs,
        symbolic=False,
        port_size=port_size,
        cfg=DEFAULT_CONFIG.qref,
    )
    save_qref(program, str(out_path))

    # Reload and verify.
    with open(out_path) as f:
        data = yaml.safe_load(f)

    assert data["version"] == "v1"
    routine = data["program"]
    resources = {r["name"]: r["value"] for r in routine["resources"]}

    assert resources["T_gates_direct"] == costs.t_count_direct, (
        f"QREF T_gates_direct={resources['T_gates_direct']} != {costs.t_count_direct}"
    )
    assert resources["T_gates_ftqc"] == costs.t_count_ftqc, (
        f"QREF T_gates_ftqc={resources['T_gates_ftqc']} != {costs.t_count_ftqc}"
    )
    assert resources["n_qubits"] == costs.logical_qubits_estimate, (
        f"QREF n_qubits={resources['n_qubits']} != {costs.logical_qubits_estimate}"
    )
    assert resources["rotations"] == costs.rotation_count, (
        f"QREF rotations={resources['rotations']} != {costs.rotation_count}"
    )


def test_qref_yaml_validates_as_schema_v1(tmp_path):
    """Exported YAML must pass qref.SchemaV1 validation."""
    from qref import SchemaV1

    bench = registry["arithmetic"]
    bloq = bench.build_bloq(n=16, op="add")
    costs = bench.logical_costs(bloq)

    out_path = tmp_path / "qref_valid.yaml"
    program = build_qref_program(
        "arithmetic",
        {"n": 16, "op": "add"},
        costs,
        port_size=16,
        cfg=DEFAULT_CONFIG.qref,
    )
    save_qref(program, str(out_path))

    with open(out_path) as f:
        raw = yaml.safe_load(f)

    # This raises if the schema is invalid.
    SchemaV1(**raw)


# Breakdown per-item verification: the cost-carrying components, at finer
# granularity than the dominant-component check in test_integration.
# Format: (component, direct_t, rotation_count, est_t_ftqc)

BREAKDOWN_ITEMS = {
    ("qft", "textbook"): [
        ("rotations", 2014, 435, 45514),
    ],
    ("qft", "approx"): [
        ("controlled_nonclifford", 2632, 0, 2632),
    ],
    ("qpe", "default"): [
        ("qft_qpe_core", 118, 15, 1618),
        ("controlled_nonclifford", 1020, 0, 1020),
    ],
    ("arithmetic", "add"): [
        ("controlled_nonclifford", 60, 0, 60),
    ],
    ("qrom", "basic"): [
        ("controlled_nonclifford", 1012, 0, 1012),
    ],
}

_BUILD_PARAMS = {
    ("qft", "textbook"): dict(n=32, variant="textbook"),
    ("qft", "approx"): dict(n=32, variant="approx"),
    ("qpe", "default"): dict(m=8, phi=0.25),
    ("arithmetic", "add"): dict(n=16, op="add"),
    ("qrom", "basic"): dict(data_size=256, variant="basic"),
}


@pytest.mark.parametrize(
    "key",
    list(BREAKDOWN_ITEMS.keys()),
    ids=[f"{k[0]}_{k[1]}" for k in BREAKDOWN_ITEMS.keys()],
)
def test_breakdown_per_item(key):
    """Each breakdown component must match pinned (component, direct_t,
    rotation_count, est_t_ftqc) values."""
    name = key[0]
    params = _BUILD_PARAMS[key]
    expected_items = BREAKDOWN_ITEMS[key]

    bench = registry[name]
    bloq = bench.build_bloq(**params)
    items = extract_structural_breakdown(bloq)

    actual = {i.component: (i.direct_t, i.rotation_count, i.est_t_ftqc) for i in items}

    for component, exp_dt, exp_rot, exp_ftqc in expected_items:
        assert component in actual, (
            f"Missing component '{component}' in breakdown. Got: {list(actual.keys())}"
        )
        dt, rot, ftqc = actual[component]
        assert dt == exp_dt, f"{component}.direct_t: {dt} != {exp_dt}"
        assert rot == exp_rot, f"{component}.rotation_count: {rot} != {exp_rot}"
        assert ftqc == exp_ftqc, f"{component}.est_t_ftqc: {ftqc} != {exp_ftqc}"


def test_breakdown_no_unexpected_components():
    """Breakdown components must only be from the known taxonomy."""
    from qrepro.breakdown import COMPONENTS

    allowed = set(COMPONENTS)
    for key, params in _BUILD_PARAMS.items():
        bench = registry[key[0]]
        bloq = bench.build_bloq(**params)
        items = extract_structural_breakdown(bloq)
        for item in items:
            assert item.component in allowed, (
                f"{key}: unknown component '{item.component}'"
            )

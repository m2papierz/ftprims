"""Smoke tests - verify project structure and imports."""

import ftprims.algorithms  # noqa: F401 — triggers benchmark registration
from ftprims.algorithms._base import registry


def test_registry_populated():
    """All five benchmarks should be registered after import."""
    expected = {"qft", "qpe", "qrom", "arithmetic"}
    assert expected.issubset(registry.keys()), f"Missing: {expected - registry.keys()}"


def test_qref_export_roundtrip():
    """QREF builder produces valid structure."""
    from ftprims.algorithms._base import LogicalCosts
    from ftprims.export import build_qref_program

    costs = LogicalCosts(qubits=10, t_count=100, clifford_count=50)
    prog = build_qref_program("test", {"n": 8}, costs)
    assert prog["version"] == "v1"
    assert prog["program"]["name"] == "test"
    assert any(r["name"] == "T_gates" for r in prog["program"]["resources"])

"""CLI round-trip tests: invoke the CLI subprocess, check its JSON against the API."""

from __future__ import annotations

import json
import subprocess

import pytest

from qrepro.algorithms import registry


def _run_cli(*args: str) -> dict:
    """Run ``qrepro run ...`` and parse the JSON from stdout."""
    result = subprocess.run(
        ["qrepro", "run", *args],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, f"CLI failed: {result.stderr}"
    lines = result.stdout.strip().split("\n")
    json_start = next(i for i, l in enumerate(lines) if l.strip().startswith("{"))
    return json.loads("\n".join(lines[json_start:]))


# One rotation-heavy case (t_ftqc diverges from t_direct) and one rotation-free
# case (they coincide). Per-primitive values are pinned in-process by
# test_integration.REFERENCE_CASES.
CLI_CASES = [
    (
        ["qft", "-p", "n=32", "-p", "variant=textbook"],
        "qft",
        dict(n=32, variant="textbook"),
    ),
    (["arithmetic", "-p", "n=16", "-p", "op=add"], "arithmetic", dict(n=16, op="add")),
]


@pytest.mark.parametrize(
    "cli_args,name,params",
    CLI_CASES,
    ids=[c[1] + "_" + "_".join(str(v) for v in c[2].values()) for c in CLI_CASES],
)
def test_cli_logical_matches_api(cli_args, name, params):
    """CLI JSON logical costs must exactly match Python API."""
    data = _run_cli(*cli_args, "--breakdown")
    bench = registry[name]
    bloq = bench.build_bloq(**params)
    api = bench.logical_costs(bloq)

    cli_l = data["logical"]
    assert cli_l["t_count_direct"] == api.t_count_direct
    assert cli_l["t_count_ftqc"] == api.t_count_ftqc
    assert cli_l["logical_qubits_estimate"] == api.logical_qubits_estimate
    assert cli_l["rotation_count"] == api.rotation_count
    assert cli_l["magic_state_count"] == api.magic_state_count


@pytest.mark.parametrize(
    "profile,factory",
    [
        ("gidney_fowler", "ccz2t"),
        ("beverland", "fifteen_to_one"),
    ],
)
def test_cli_physical_profile_forwarded(profile, factory):
    """CLI --profile and --factory must appear in JSON physical output."""
    data = _run_cli(
        "qft",
        "-p",
        "n=16",
        "-p",
        "variant=textbook",
        "--physical",
        "--profile",
        profile,
        "--factory",
        factory,
    )
    assert data["physical"]["profile"] == profile
    assert data["physical"]["factory"] == factory
    assert data["physical"]["budget_satisfied"] is True
    assert data["physical"]["wall_time_us"] > 0


def test_cli_rotation_eps_affects_ftqc():
    """Changing --rotation-eps must change t_count_ftqc for rotation-heavy circuits."""
    data_tight = _run_cli(
        "qft",
        "-p",
        "n=32",
        "-p",
        "variant=textbook",
        "--rotation-eps",
        "1e-10",
    )
    data_loose = _run_cli(
        "qft",
        "-p",
        "n=32",
        "-p",
        "variant=textbook",
        "--rotation-eps",
        "1e-4",
    )
    t_tight = data_tight["logical"]["t_count_ftqc"]
    t_loose = data_loose["logical"]["t_count_ftqc"]
    assert t_tight > t_loose, (
        f"Tighter epsilon should give more T-gates: {t_tight} vs {t_loose}"
    )
    # t_count_direct should be unchanged (no rotations involved)
    assert (
        data_tight["logical"]["t_count_direct"]
        == data_loose["logical"]["t_count_direct"]
    )


def test_cli_breakdown_sums_to_ftqc():
    """CLI breakdown est_t_ftqc items must sum close to logical t_count_ftqc."""
    data = _run_cli(
        "qft",
        "-p",
        "n=32",
        "-p",
        "variant=textbook",
        "--breakdown",
    )
    bd_total = sum(item["est_t_ftqc"] for item in data["breakdown"])
    logical_ftqc = data["logical"]["t_count_ftqc"]
    denom = max(logical_ftqc, bd_total, 1)
    delta = abs(logical_ftqc - bd_total) / denom
    assert delta < 0.01, f"CLI breakdown total={bd_total} vs logical={logical_ftqc}"

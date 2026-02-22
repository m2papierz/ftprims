"""ftprims CLI — run benchmarks, sweep parameters, export QREF."""

from __future__ import annotations

import json
from pathlib import Path

import click

from ftprims.algorithms import registry


@click.group()
@click.version_option(package_name="ftprims")
def main() -> None:
    """ftprims — FTQC primitives benchmark suite."""


@main.command()
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
@click.option(
    "--out", type=click.Path(), default=None, help="Save JSON results to file"
)
@click.option("--svg", type=click.Path(), default=None, help="Save call-graph SVG")
def run(
    primitive: str, param: tuple[str, ...], out: str | None, svg: str | None
) -> None:
    """Run a single benchmark and report resource costs."""
    bench = registry[primitive]
    params = _parse_params(param)
    click.echo(f"Building {primitive} with {params}")

    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)

    result = {
        "primitive": primitive,
        "params": params,
        "logical": {
            "qubits": costs.qubit,
            "t_count": costs.t_count,
            "clifford_count": costs.clifford_count,
            "rotation_count": costs.rotation_count,
        },
    }
    click.echo(json.dumps(result, indent=2))

    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True)
        Path(out).write_text(json.dumps(result, indent=2))
        click.echo(f"Saved → {out}")


@main.command()
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
def verify(primitive: str, param: tuple[str, ...]) -> None:
    """Run small-scale Cirq verification for a primitive."""
    bench = registry[primitive]
    params = _parse_params(param)
    result = bench.verify_small(**params)
    status = "✓ PASS" if result.passed else "✗ FAIL"
    click.echo(f"{status}  {result.detail}")


@main.command("export-qref")
@click.argument("primitive", type=click.Choice(list(registry)))
@click.option("--param", "-p", multiple=True, help="key=value parameter pairs")
@click.option("--out", type=click.Path(), required=True, help="Output YAML path")
def export_qref(primitive: str, param: tuple[str, ...], out: str) -> None:
    """Export benchmark as a QREF v1 program."""
    from ftprims.export.qref_export import build_qref_program, save_qref

    bench = registry[primitive]
    params = _parse_params(param)
    bloq = bench.build_bloq(**params)
    costs = bench.logical_costs(bloq)
    program = build_qref_program(primitive, params, costs)

    Path(out).parent.mkdir(parents=True, exist_ok=True)
    save_qref(program, out)
    click.echo(f"QREF exported → {out}")


def _parse_params(raw: tuple[str, ...]) -> dict[str, int | float | str]:
    """Parse 'key=value' strings into a typed dict."""
    params: dict[str, int | float | str] = {}
    for item in raw:
        k, _, v = item.partition("=")
        try:
            params[k] = int(v)
        except ValueError:
            try:
                params[k] = float(v)
            except ValueError:
                params[k] = v
    return params

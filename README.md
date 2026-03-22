[![CI](https://github.com/m2papierz/ftprims/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/m2papierz/ftprims/actions/workflows/ci.yaml)
[![Python](https://img.shields.io/pypi/pyversions/ftprims)](https://pypi.org/project/ftprims/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

# ftprims
Fault-tolerant quantum computing (FTQC) primitives benchmark suite. Built on [Qualtran](https://qualtran.readthedocs.io/) + [Cirq](https://quantumai.google/cirq) with native [QREF](https://github.com/PsiQ/qref) / [Bartiq](https://github.com/PsiQ/bartiq) export. Benchmark canonical FTQC building blocks, extract logical & physical resource costs via Qualtran, verify correctness with Cirq simulation, and export results as QREF programs for cost propagation in Bartiq.

> [!NOTE]
> Learning project - built to deepen hands-on understanding of FTQC resource estimation, Qualtran's bloq abstractions, and the QREF/Bartiq toolchain. Simplifications and approximations often appear in the design.

### Primitives

| Primitive | Variants | Key metric |
|-----------|----------|------------|
| **QFT** | Textbook, Approximate | T-count vs n (incl. rotation synthesis) |
| **QPE** | Textbook (pluggable U) | T-count vs precision bits |
| **Arithmetic** | Add, OutOfPlaceAdder, LessThanEqual, Product, ModAdd | T-count vs bitsize |
| **QROM** | QROM, SelectSwapQROM | T-count vs table size, T/ancilla Pareto |

## Installation

Requires Python 3.10–3.12.

```bash
git clone https://github.com/m2papierz/ftprims.git && cd ftprims

# with uv (recommended)
uv sync

# or with pip
pip install -e ".[dev]"
```

## Quick start - run everything

The `run_all.sh` script runs every benchmark, verification, QREF export, consistency check, and experiment sweep in one go:

```bash
./run_all.sh
```

Results (JSON, YAML, CSV, PNG charts) land in `results/`.

## Usage

### Run a benchmark

```bash
# Logical costs only
uv run ftprims run qft -p n=32

# Include surface-code physical estimate
uv run ftprims run qft -p n=32 --physical

# Arithmetic
uv run ftprims run arithmetic -p n=64 -p op=mul

# QROM with SelectSwap trade-off
uv run ftprims run qrom -p data_size=256 -p variant=selectswap -p log_block_sizes=4

# Save results to JSON
uv run ftprims run qft -p n=32 --physical --out results/qft_n32.json
```

### Structural cost breakdown

The `--breakdown` flag decomposes costs into component categories via Qualtran's `call_graph`, showing where T-gates actually come from:

```bash
uv run ftprims run qft -p n=16 -p variant=textbook --breakdown
```

This adds a `breakdown` array and `breakdown_summary` to the JSON output. Categories: `rotations`, `qft_qpe_core`, `qrom_core`, `arithmetic_core`, `controlled_nonclifford`, `clifford_scaffolding`, `other`.

Gate classification is cost-aware: parameterised `*PowGate` bloqs are classified as `rotations` when their exponent is non-Clifford (requires synthesis), rather than being lumped into `controlled_nonclifford` by name alone.

Options: `--breakdown-depth` (call_graph depth, default 1), `--rotation-eps` (synthesis precision, default 1e-10).

### Physical model variants

Physical estimation supports multiple surface-code configurations:

```bash
# Beverland profile with fast data block and 15-to-1 factory
uv run ftprims run qft -p n=32 --physical \
  --profile beverland --data-block fast --factory fifteen_to_one

# Fixed code distance
uv run ftprims run qft -p n=32 --physical --data-d 21

# Custom error budget
uv run ftprims run qft -p n=32 --physical --error-budget 1e-2

# Override physical error rate and cycle time
uv run ftprims run qft -p n=32 --physical --physical-error 1e-4 --cycle-time-us 1.0
```

Available profiles: `gidney_fowler` (default), `beverland`. Data blocks: `simple` (default), `compact`, `fast`. Factories: `ccz2t` (default), `fifteen_to_one`.

### Interpret results

The `--explain` flag generates a short rule-based interpretation:

```bash
uv run ftprims run qft -p n=16 --breakdown --physical --explain
```

Use `--explain-json` to embed the explanation in the JSON output instead.

### Verify (small-scale Cirq simulation)

```bash
uv run ftprims verify qft        -p n=4 -p variant=textbook
uv run ftprims verify qft        -p n=4 -p variant=approx
uv run ftprims verify qpe        -p m=4 -p phi=0.25
uv run ftprims verify arithmetic -p n=4 -p op=add
uv run ftprims verify arithmetic -p n=4 -p op=modadd
uv run ftprims verify qrom       -p data_size=8 -p target_bitsize=4 -p variant=basic
uv run ftprims verify qrom       -p data_size=8 -p target_bitsize=4 -p variant=selectswap
```

### Export to QREF / Bartiq

```bash
# Numeric export (concrete values from the Qualtran benchmark - authoritative)
uv run ftprims export-qref qft -p n=32 --out results/qft.qref.yaml

# Symbolic export (approximate analytic formulas for Bartiq compilation)
uv run ftprims export-qref qft -p n=32 --symbolic --out results/qft_sym.qref.yaml

# Symbolic + consistency check against numeric benchmark
uv run ftprims export-qref qft -p n=32 --symbolic --check --out results/qft_sym.qref.yaml

# Compile and evaluate with Bartiq
uv run ftprims bartiq results/qft_sym.qref.yaml --assign n=64
```

> [!IMPORTANT]
> Symbolic mode (`--symbolic`) exports **approximate analytic formulas** - textbook-level scaling terms that may diverge from the numeric benchmark at concrete parameter values. Use `--check` to compare the approximation against the real Qualtran numbers. Numeric export is always the authoritative cost source.

### Parameter sweep experiments

```bash
uv run python experiments/sweep_qft.py
uv run python experiments/sweep_qpe.py
uv run python experiments/sweep_arithmetic.py
uv run python experiments/sweep_qrom.py

# Compare physical configs for any primitive
uv run python experiments/compare_physical_configs.py qft n=16 variant=textbook
```

Each sweep writes CSV data and PNG charts (including per-component breakdown charts) to `results/`. The physical comparison script produces a scatter plot of physical qubits vs wall time across 9 preset configurations.

### Configuration

```bash
# Print default config
uv run ftprims dump-config

# Save and edit
uv run ftprims dump-config --out config.yaml
# then pass to any command:
uv run ftprims run qft -p n=32 --physical --config config.yaml
```

Key config options: `rotation_synthesis_epsilon` (default `1e-10`), `error_budget`, `physical_error`, `cycle_time_us`, `data_d`.

## Output format

Logical costs report two T-count metrics:

- **`t_count_direct`** - raw T-gates + 4xCCZ/And. Accurate for pure Clifford+T circuits.
- **`t_count_ftqc`** - includes rotation synthesis cost. This is the primary FTQC metric.

When `--breakdown` is used, the output includes per-component cost attribution with estimated FTQC T-cost and a summary identifying the dominant component.

Physical estimates include `failure_prob` and `budget_satisfied` - the model never silently masks an unmet error budget. The output also records which `profile`, `data_block`, and `factory` were used, so results are reproducible across runs.

## Architecture

```
ftprims/
├── run_all.sh             # Run every benchmark, verify, export, and sweep
├── src/ftprims/
│   ├── algorithms/        # Benchmark implementations (QFT, QPE, Arithmetic, QROM)
│   │   └── _base.py       # Protocol, data models (LogicalCosts, PhysicalCosts, BreakdownItem)
│   ├── breakdown.py       # Structural cost breakdown via call_graph
│   ├── physical.py        # Surface-code physical model variants
│   ├── resource.py        # Logical cost extraction from Qualtran
│   ├── explain.py         # Rule-based result interpretation
│   ├── export.py          # QREF/Bartiq export (numeric + approximate symbolic)
│   ├── cli.py             # Click CLI
│   └── config.py          # Configuration
└── experiments/           # Parameter sweep scripts (CSV + PNG output)
```

## License

Apache 2.0 - see [LICENSE](LICENSE).

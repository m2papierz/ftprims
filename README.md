[![CI](https://github.com/devqubit-labs/devqubit/actions/workflows/ci.yaml/badge.svg?branch=main)](https://github.com/devqubit-labs/devqubit/actions/workflows/ci.yaml)
[![Python](https://img.shields.io/pypi/pyversions/devqubit)](https://pypi.org/project/devqubit/)
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

Requires Python 3.10–3.12 and [uv](https://docs.astral.sh/uv/).

```bash
git clone https://github.com/m2papierz/ftprims.git && cd ftprims
uv sync
```

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

### Verify (small-scale Cirq simulation)

```bash
uv run ftprims verify qft -p n=4
uv run ftprims verify qpe -p m=4 -p phi=0.25
uv run ftprims verify arithmetic -p n=4 -p op=add
uv run ftprims verify qrom -p data_size=8
```

### Export to QREF / Bartiq

```bash
# Numeric export (concrete values)
uv run ftprims export-qref qft -p n=32 --out results/qft.qref.yaml

# Symbolic export (expressions for Bartiq compilation)
uv run ftprims export-qref qft -p n=32 --symbolic --out results/qft_sym.qref.yaml

# Compile and evaluate with Bartiq
uv run ftprims bartiq results/qft_sym.qref.yaml --assign n=64
```

### Parameter sweep experiments

```bash
uv run python experiments/sweep_qft.py
uv run python experiments/sweep_qpe.py
uv run python experiments/sweep_arithmetic.py
uv run python experiments/sweep_qrom.py
```

Each sweep writes CSV data and PNG charts to `results/`.

### Configuration

```bash
# Print default config
uv run ftprims dump-config

# Save and edit
uv run ftprims dump-config --out config.yaml
# then pass to any command:
uv run ftprims run qft -p n=32 --physical --config config.yaml
```

Key config options: `rotation_synthesis_epsilon` (default `1e-10`), `error_budget`, `physical_error`, `cycle_time_us`.

## Output format

Logical costs report two T-count metrics:

- **`t_count_direct`** — raw T-gates + 4×CCZ/And. Accurate for pure Clifford+T circuits.
- **`t_count_ftqc`** — includes rotation synthesis cost (Ross-Selinger model, configurable ε). This is the primary FTQC metric.

Physical estimates include `failure_prob` and `budget_satisfied` — the model never silently masks an unmet error budget.

## License

Apache 2.0 — see [LICENSE](LICENSE).

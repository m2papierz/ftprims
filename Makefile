.PHONY: install setup fmt lint check test audit ci clean run-all run verify export sweeps clean-results

PYTHON   ?= python3
UV       ?= uv

# ── Install ──────────────────────────────────────────────────────────────────

install:
	$(UV) sync
	@echo ""
	@echo "  ✓ ftprims installed (editable via uv sync)"

# ── Setup (first-time contributor) ───────────────────────────────────────────

setup: install
	$(UV) run pre-commit install
	@echo "  ✓ Pre-commit hooks installed"

# ── Format ───────────────────────────────────────────────────────────────────

fmt:
	$(UV) run ruff check --select I --fix src/ tests/ experiments/ notebooks/
	$(UV) run ruff format src/ tests/ experiments/ notebooks/
	@echo "  ✓ Formatted"

# ── Test ─────────────────────────────────────────────────────────────────────

test:
	$(UV) run pytest

# ── Pipeline (run_all.sh and individual stages) ─────────────────────────────

run-all:
	bash run_all.sh

run:
	$(UV) run ftprims run qft -p n=32 -p variant=textbook --breakdown --physical
	$(UV) run ftprims run qft -p n=32 -p variant=approx --breakdown --physical
	$(UV) run ftprims run qpe -p m=8 -p phi=0.25 --breakdown --physical
	$(UV) run ftprims run arithmetic -p n=16 -p op=add --breakdown --physical
	$(UV) run ftprims run arithmetic -p n=16 -p op=mul --breakdown --physical
	$(UV) run ftprims run qrom -p data_size=256 -p variant=basic --breakdown --physical

verify:
	$(UV) run ftprims verify qft -p n=4 -p variant=textbook
	$(UV) run ftprims verify qft -p n=4 -p variant=approx
	$(UV) run ftprims verify qpe -p m=4 -p phi=0.25
	$(UV) run ftprims verify arithmetic -p n=4 -p op=add
	$(UV) run ftprims verify arithmetic -p n=4 -p op=add_oop
	$(UV) run ftprims verify arithmetic -p n=4 -p op=leq
	$(UV) run ftprims verify arithmetic -p n=4 -p op=modadd
	$(UV) run ftprims verify qrom -p data_size=8 -p target_bitsize=4 -p variant=basic
	$(UV) run ftprims verify qrom -p data_size=8 -p target_bitsize=4 -p variant=selectswap

export:
	@mkdir -p results/qref/numeric results/qref/symbolic
	$(UV) run ftprims export-qref qft -p n=32 -p variant=textbook --out results/qref/numeric/qref_qft_textbook.yaml
	$(UV) run ftprims export-qref qft -p n=32 -p variant=textbook --symbolic --out results/qref/symbolic/qref_qft_textbook_symbolic.yaml

sweeps:
	@mkdir -p results/sweeps results/charts
	$(UV) run python experiments/sweep_rotation_epsilon.py
	$(UV) run python experiments/sweep_ge19_physical.py
	$(UV) run python experiments/landscape.py

# ── Clean ────────────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "  ✓ Cleaned"

clean-results:
	rm -rf results/
	@echo "  ✓ Results cleaned"

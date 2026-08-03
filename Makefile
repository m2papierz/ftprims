.PHONY: install setup fmt test run-all run verify export sweeps clean clean-results

PYTHON   ?= python3
UV       ?= uv

install:
	$(UV) sync
	@echo ""
	@echo "  OK qrepro installed (editable via uv sync)"

setup: install
	$(UV) run pre-commit install
	@echo "  OK Pre-commit hooks installed"

fmt:
	$(UV) run ruff check --select I --fix src/ tests/ experiments/ notebooks/
	$(UV) run ruff format src/ tests/ experiments/ notebooks/
	@echo "  OK Formatted"

test:
	$(UV) run pytest

run-all:
	bash run_all.sh

run:
	$(UV) run qrepro run qft -p n=32 -p variant=textbook --breakdown --physical
	$(UV) run qrepro run qft -p n=32 -p variant=approx --breakdown --physical
	$(UV) run qrepro run qpe -p m=8 -p phi=0.25 --breakdown --physical
	$(UV) run qrepro run arithmetic -p n=16 -p op=add --breakdown --physical
	$(UV) run qrepro run arithmetic -p n=16 -p op=mul --breakdown --physical
	$(UV) run qrepro run qrom -p data_size=256 -p variant=basic --breakdown --physical

verify:
	$(UV) run qrepro verify qft -p n=4 -p variant=textbook
	$(UV) run qrepro verify qft -p n=4 -p variant=approx
	$(UV) run qrepro verify qpe -p m=4 -p phi=0.25
	$(UV) run qrepro verify arithmetic -p n=4 -p op=add
	$(UV) run qrepro verify arithmetic -p n=4 -p op=add_oop
	$(UV) run qrepro verify arithmetic -p n=4 -p op=modadd
	$(UV) run qrepro verify qrom -p data_size=8 -p target_bitsize=4 -p variant=basic

export:
	@mkdir -p results/qref/numeric results/qref/symbolic
	$(UV) run qrepro export-qref qft -p n=32 -p variant=textbook --out results/qref/numeric/qref_qft_textbook.yaml
	$(UV) run qrepro export-qref qft -p n=32 -p variant=textbook --symbolic --out results/qref/symbolic/qref_qft_textbook_symbolic.yaml

sweeps:
	@mkdir -p results/sweeps results/charts
	$(UV) run python experiments/sweep_rotation_epsilon.py
	$(UV) run python experiments/sweep_ge19_physical.py
	$(UV) run python experiments/sweep_windowed_modexp.py
	$(UV) run python experiments/plot_landscape.py
	$(UV) run python experiments/plot_regime_identification.py

clean:
	rm -rf dist/ build/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "  OK Cleaned"

clean-results:
	rm -rf results/
	@echo "  OK Results cleaned"

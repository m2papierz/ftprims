.PHONY: install setup fmt lint check test audit ci clean

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
	$(UV) run black src/ tests/ experiments/
	$(UV) run isort src/ tests/ experiments/
	@echo "  ✓ Formatted"

# ── Test ─────────────────────────────────────────────────────────────────────

test:
	$(UV) run pytest

# ── Clean ────────────────────────────────────────────────────────────────────

clean:
	rm -rf dist/ build/ .pytest_cache/ .ruff_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	@echo "  ✓ Cleaned"

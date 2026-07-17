"""Pytest configuration for the ftprims test suite.

``ftprims`` (including ``ftprims.references``, the single source of reproduction
targets) is installed editable from ``src/``, so the tests import it directly
under ``--import-mode=importlib`` — no repo-root ``sys.path`` shim is needed.
"""

from __future__ import annotations

"""Centralised configuration for ftprims."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import attrs
import yaml


@attrs.define
class SurfaceCodeConfig:
    """Tunable parameters for surface-code physical estimation.

    ``None`` on *physical_error* / *cycle_time_us* takes the QEC profile
    preset; ``None`` on *data_d* auto-searches the minimum feasible distance.
    """

    physical_error: float | None = None
    cycle_time_us: float | None = None
    data_d: int | None = None
    error_budget: float = 1e-3
    rotation_synthesis_epsilon: float | None = 1e-10


@attrs.define
class QREFConfig:
    """Defaults for QREF v1 export."""

    version: str = "v1"
    validate: bool = True  # pass through SchemaV1 before saving


@attrs.define
class FTPrimsConfig:
    """Top-level configuration bundle."""

    surface_code: SurfaceCodeConfig = attrs.Factory(SurfaceCodeConfig)
    qref: QREFConfig = attrs.Factory(QREFConfig)

    def to_dict(self) -> dict[str, Any]:
        return attrs.asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> FTPrimsConfig:
        sc = d.get("surface_code", {})
        qr = d.get("qref", {})
        return cls(
            surface_code=SurfaceCodeConfig(**sc),
            qref=QREFConfig(**qr),
        )

    @classmethod
    def load(cls, path: str | Path) -> FTPrimsConfig:
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls.from_dict(raw or {})


#: Used whenever no explicit config is passed.
DEFAULT_CONFIG = FTPrimsConfig()

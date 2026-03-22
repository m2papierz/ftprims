"""Centralised configuration for ftprims."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import attrs
import yaml


@attrs.define
class SurfaceCodeConfig:
    """User-tunable parameters for surface-code physical estimation."""

    # PhysicalParameters - None means "use QEC profile preset"
    physical_error: float | None = None
    cycle_time_us: float | None = None

    # Code distance - None => auto-search for minimum feasible distance
    data_d: int | None = None

    # Error budget for the whole algorithm
    error_budget: float = 1e-3

    # Rotation synthesis precision
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

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            yaml.safe_dump(self.to_dict(), f, sort_keys=False)

    @classmethod
    def load(cls, path: str | Path) -> FTPrimsConfig:
        with open(path) as f:
            raw = yaml.safe_load(f)
        return cls.from_dict(raw or {})


# Module-level default used when no explicit config is passed.
DEFAULT_CONFIG = FTPrimsConfig()

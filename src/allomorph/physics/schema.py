"""
Allomorph Physics - Pydantic Configuration Schemas.

Defines formal schemas for acoustic wave-speed continuum points and string physics.
"""

from typing import Literal

from pydantic import Field

from allomorph.base import AllomorphBaseModel

__all__ = [
    "WaveSpeedContinuumPoint",
]


class WaveSpeedContinuumPoint(AllomorphBaseModel):
    """Single point in the log-spaced wave-speed continuum across the instrument register."""

    f0: float = Field(gt=0.0)
    v0: float = Field(gt=0.0)
    scale_m: float = Field(gt=0.0)
    register: Literal["lower", "upper"]
    weight: float = Field(default=1.0, ge=0.0)

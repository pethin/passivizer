"""
Allomorph Visualizer - Pydantic Configuration Schemas.

Defines schemas for interactive visualizer portals and chart exports.
"""

from allomorph.base import AllomorphBaseModel

__all__ = [
    "PortalInstrumentMeta",
]


class PortalInstrumentMeta(AllomorphBaseModel):
    """Metadata describing an instrument formatted for the interactive visualization portal."""

    id: str
    name: str
    scale_in: float
    scale_m: float
    speeds_str: str
    pickups_summary: str
    default_pickup: str

"""
Allomorph Pipeline - Pydantic Configuration Schemas.

Defines schemas for pipeline CLI arguments, Tone3000 storefront pack listings,
and Neural Amp Modeler (.nam) Architecture 2 export container metadata.
"""

from typing import Any, Literal

from pydantic import Field

from allomorph.base import AllomorphBaseModel

__all__ = [
    "NamExportMetadata",
    "NamSourceInstrumentMeta",
    "NamTargetVoiceMeta",
    "PipelineCliConfig",
    "Tone3000PackListing",
]


class PipelineCliConfig(AllomorphBaseModel):
    """Validation schema for Allomorph pipeline command-line arguments."""

    instrument: str = "all"
    stage: Literal["all", "viz", "canonical", "frontends", "targets", "train", "bake"] = "all"
    tier: Literal["clean", "standard", "std", "hotrod", "dynamic", "all"] | None = None
    pickup: str | None = None
    voice: str = "all"
    train: bool = False
    vol_pos: float | None = Field(default=None, ge=0.0, le=1.0)
    tone_pos: float | None = Field(default=None, ge=0.0, le=1.0)
    blend_pos: float | None = Field(default=None, ge=0.0, le=1.0)
    pot_taper: Literal["audio", "linear", "reverse_audio", "mn_blend"] | None = None
    cable_pf: float = Field(default=750.0, ge=0.0, le=20000.0)
    out_dir: str | None = None
    input_wav: str | None = None
    output_wav: str | None = None
    export_json: str | None = None
    html: str | None = None
    backend: str = "native"


class Tone3000PackListing(AllomorphBaseModel):
    """Declarative validation schema for Tone3000 storefront pack descriptions and metadata."""

    edition: str
    description: str = Field(..., min_length=7000, max_length=10000)
    pickup_tags: list[str] = Field(default_factory=list)
    voicings: list[str] = Field(..., min_length=22, max_length=22)


class NamSourceInstrumentMeta(AllomorphBaseModel):
    """Metadata describing the physical source instrument embedded in Architecture 2 models."""

    id: str
    name: str
    scale_length_in: float
    scale_length_m: float | None = None
    string_wave_speeds: list[float] = Field(default_factory=list)
    pickup: dict[str, Any]


class NamTargetVoiceMeta(AllomorphBaseModel):
    """Metadata describing the target acoustic voicing and circuit embedded in Architecture 2 models."""

    id: str
    name: str
    topology: str = ""
    resonant_frequency_hz: float = 0.0
    q_factor: float = 0.0
    target_position_34_m: float = 0.0
    effective_position_m: float = 0.0
    pickups: list[Any] = Field(default_factory=list)
    coils: list[Any] = Field(default_factory=list)
    circuit: Any = ""


class NamExportMetadata(AllomorphBaseModel):
    """Container metadata exported with Neural Amp Modeler (.nam) models."""

    training: dict[str, Any]
    license: str
    copyright: str
    author: str
    source_instrument: NamSourceInstrumentMeta
    target_voice: NamTargetVoiceMeta

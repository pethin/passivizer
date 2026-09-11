"""
Allomorph - Pydantic Configuration Schemas.

Defines formal, strictly-typed Pydantic v2 schemas for all Allomorph physical instruments,
target voices, RLC circuit digital twins, coils, active onboard preamps, physical scales,
and string presets.
"""

from pathlib import Path
from typing import Annotated, Any, Literal, Self, override

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator


def parse_spice_unit(v: Any) -> Any:
    """Parses standard SPICE engineering suffix notation (Meg, k, m, u, n, p, g) with unit suffixes."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        s_clean = s.rstrip("FfHhΩ").strip()
        if s_clean.lower().endswith("ohm"):
            s_clean = s_clean[:-3].strip()
        if not s_clean:
            s_clean = s
        if s_clean.lower().endswith("meg"):
            return float(s_clean[:-3]) * 1e6
        suffix_map = {
            "p": 1e-12,
            "n": 1e-9,
            "u": 1e-6,
            "m": 1e-3,
            "k": 1e3,
            "g": 1e9,
        }
        last_char = s_clean[-1].lower()
        if last_char in suffix_map:
            return float(s_clean[:-1]) * suffix_map[last_char]
        return float(s_clean)
    raise TypeError(f"Invalid SPICE value: {v}")


SpiceFloat = Annotated[float, BeforeValidator(parse_spice_unit)]


class AllomorphBaseModel(BaseModel):
    """
    Base model for Allomorph declarative configurations.
    Enforces strict validation (forbidding unknown keys) and provides
    transparent subscripting/dict-like access for downstream compatibility.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item) from None

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return False
        return (item in type(self).model_fields or hasattr(self, item)) and getattr(self, item, None) is not None

    @override
    def copy(self, *args: Any, **kwargs: Any) -> Self:
        return self.model_copy(*args, **kwargs)

    def get(self, key: str, default: Any = None) -> Any:
        val = getattr(self, key, None)
        return val if val is not None else default

    def keys(self) -> list[str]:
        return list(type(self).model_fields.keys())

    def values(self) -> list[Any]:
        return [getattr(self, k) for k in type(self).model_fields]

    def items(self) -> list[tuple[str, Any]]:
        return [(k, getattr(self, k)) for k in type(self).model_fields]


# ==============================================================================
# 1. PHYSICAL SCALES SCHEMAS
# ==============================================================================


class ScaleConfig(AllomorphBaseModel):
    """Vibrating string scale length and physical wave speeds."""

    name: str
    scale_length_in: float = Field(..., gt=0.0)
    scale_length_m: float | None = None
    scale_min_in: float | None = None
    scale_max_in: float | None = None
    is_multiscale: bool = False
    string_wave_speeds: list[float] = Field(default_factory=list)

    @model_validator(mode="after")
    def compute_scale_m(self) -> Self:
        if self.scale_length_m is None:
            self.scale_length_m = self.scale_length_in * 0.0254
        return self

    @property
    def scale_m(self) -> float:
        return self.scale_length_m if self.scale_length_m is not None else self.scale_length_in * 0.0254

    @property
    def speeds(self) -> list[float]:
        return self.string_wave_speeds


class ScalesCatalog(AllomorphBaseModel):
    """Catalog of standard vibrating scale lengths."""

    scales: dict[str, ScaleConfig] = Field(default_factory=dict)


# ==============================================================================
# 2. PHYSICAL STRINGS SCHEMAS
# ==============================================================================


class StringPresetConfig(AllomorphBaseModel):
    """Physical string core, wrap, tension, and viscoelastic damping preset."""

    name: str
    type: str = "roundwound"
    wrap: str
    core: str
    tension_lbs: float = Field(..., gt=0.0)
    damping_cutoff_hz: float = Field(..., gt=0.0)
    damping_order: float = Field(..., gt=0.0)
    bloom_db: float = 0.0
    pluck_excursion_factor: float = Field(1.0, gt=0.0)
    k_long: float = Field(0.20, ge=0.0)
    bridge_rocking_compliance: float | None = None


class InstrumentStringsConfig(AllomorphBaseModel):
    """Source instrument string setup block referencing a preset."""

    preset: str = "roundwound_nickel_standard"
    brand: str | None = None
    model: str | None = None
    gauge: str | None = None
    core: str | None = None
    wrap: str | None = None
    tension_lbs: float | None = None


class ResolvedStringConfig(StringPresetConfig):
    """Fully resolved string configuration combining preset physics and instrument setup."""

    preset: str = "roundwound_nickel_standard"
    brand: str | None = None
    model: str | None = None
    gauge: str | None = None


class StringsCatalog(AllomorphBaseModel):
    """Catalog of physical string presets."""

    strings: dict[str, StringPresetConfig] = Field(default_factory=dict)


# ==============================================================================
# 3. ONBOARD ACTIVE PREAMP SCHEMAS
# ==============================================================================


class PreampBandConfig(AllomorphBaseModel):
    """Active onboard preamp equalizer band specification."""

    type: Literal["low_shelf", "high_shelf", "bell", "low_pass", "high_pass"]
    freq_hz: float = Field(..., gt=0.0, le=20000.0)
    gain_db: float = Field(..., ge=-30.0, le=30.0)
    q: float | None = None


class PreampConfig(AllomorphBaseModel):
    """Active onboard preamp or buffer configuration."""

    id: str | None = None
    name: str
    description: str | None = None
    input_impedance_meg: float = Field(1.0, gt=0.0)
    output_impedance_ohm: float = Field(100.0, ge=0.0)
    gain_db: float = 0.0
    bands: list[PreampBandConfig] = Field(default_factory=list)


class PreampsCatalog(AllomorphBaseModel):
    """Catalog of active preamp and buffer presets."""

    preamps: dict[str, PreampConfig] = Field(default_factory=dict)


# ==============================================================================
# 4. ELECTRICAL CIRCUIT SCHEMAS
# ==============================================================================


class CircuitBranchConfig(AllomorphBaseModel):
    """RLC parameters for a single pickup coil branch in dual-branch circuits."""

    L: SpiceFloat = Field(..., gt=0.0)
    Rdc: SpiceFloat = Field(..., gt=0.0)
    Reddy: SpiceFloat = Field(..., gt=0.0)
    Ccoil: SpiceFloat = Field(..., ge=0.0)
    vsat: float | None = None


class CircuitConfig(AllomorphBaseModel):
    """
    SPICE RLC circuit configuration for passive and active pickups.
    Models single-branch or dual-branch (neck/bridge) pickups with volume/tone pot tapers.
    """

    topology: str = "single"
    L: SpiceFloat | None = None
    Rdc: SpiceFloat | None = None
    Reddy: SpiceFloat | None = None
    Ccoil: SpiceFloat | None = None
    vsat: float | None = None
    Rtop: SpiceFloat | None = None
    Rbot: SpiceFloat | None = None
    Rvol: SpiceFloat | None = None
    Rtone: SpiceFloat | None = None
    Ctone: SpiceFloat | None = None
    Crick: SpiceFloat | None = None
    Ctb: SpiceFloat | None = None
    Rtb_par: SpiceFloat | None = None
    Rtb_ser: SpiceFloat | None = None
    Rpot_n: SpiceFloat | None = None
    Rpot_b: SpiceFloat | None = None
    active: bool | None = None
    preamp: str | None = None
    preamp_gain: float | None = None
    R_out: SpiceFloat | None = None
    no_eq: bool | None = None
    Ccable: SpiceFloat | None = None
    vol_pos: float | None = None
    tone_pos: float | None = None
    blend_pos: float | None = None
    pot_taper: str | None = None
    neck: CircuitBranchConfig | None = None
    bridge: CircuitBranchConfig | None = None

    @model_validator(mode="after")
    def validate_circuit_branches(self) -> Self:
        if (
            self.topology in ("parallel", "series")
            and self.neck is None
            and self.bridge is None
            and (self.L is None or self.Rdc is None or self.Reddy is None)
        ):
            raise ValueError(
                f"Multi-coil circuit with topology '{self.topology}' must specify either "
                "'neck' and 'bridge' branches or top-level L/Rdc/Reddy parameters."
            )
        return self


class HarnessControls(AllomorphBaseModel):
    """Interactive volume, tone, and blend potentiometer wiper state with cable load."""

    vol_pos: float = Field(default=1.0, ge=0.0, le=1.0)
    tone_pos: float = Field(default=1.0, ge=0.0, le=1.0)
    blend_pos: float = Field(default=0.5, ge=0.0, le=1.0)
    pot_taper: Literal["audio", "linear", "reverse_audio", "mn_blend"] = "audio"
    cable_pf: float = Field(default=750.0, ge=0.0, le=20000.0)


class MagnetPropertiesConfig(AllomorphBaseModel):
    """Physical non-linear metallurgy and dynamic magnetic parameters."""

    k_core: float = 0.0
    f_core: float = 0.0
    k_skin: float = 0.0
    f_skin: float = 0.0
    lambda_L: float = 0.0
    k_emf: float = 0.0
    eta_hyst: float = 0.0
    alpha: float = 0.20
    alpha3: float = 0.08
    k_sag: float = 0.08
    vsat: float = 0.50
    k_eddy: float = 0.0
    kappa_orbit: float = 0.0
    k_body: float = 0.0
    beta_curv: float = 0.0
    k_pull: float = 0.0
    tau_touch: float = 0.0
    chi_mu: float = 0.0
    k_dist: float = 0.0
    kappa_geom: float = 0.0
    k_stein: float = 0.0

    def diff(self, source: Self) -> MagnetPropertiesConfig:
        """
        Computes differential softening parameters satisfying Guardrail 5.4.1:
        Δparam = max(voice_param - source_param, 0.0).
        """
        return MagnetPropertiesConfig(
            k_core=max(self.k_core - source.k_core, 0.0),
            f_core=self.f_core,
            k_skin=max(self.k_skin - source.k_skin, 0.0),
            f_skin=self.f_skin,
            lambda_L=max(self.lambda_L - source.lambda_L, 0.0),
            k_emf=max(self.k_emf - source.k_emf, 0.0),
            eta_hyst=max(self.eta_hyst - source.eta_hyst, 0.0),
            alpha=max(self.alpha - source.alpha, 0.0),
            alpha3=max(self.alpha3 - source.alpha3, 0.0),
            k_sag=max(self.k_sag - source.k_sag, 0.0),
            vsat=self.vsat,
            k_eddy=max(self.k_eddy - source.k_eddy, 0.0),
            kappa_orbit=max(self.kappa_orbit - source.kappa_orbit, 0.0),
            k_body=max(self.k_body - source.k_body, 0.0),
            beta_curv=max(self.beta_curv - source.beta_curv, 0.0),
            k_pull=max(self.k_pull - source.k_pull, 0.0),
            tau_touch=max(self.tau_touch - source.tau_touch, 0.0),
            chi_mu=max(self.chi_mu - source.chi_mu, 0.0),
            k_dist=max(self.k_dist - source.k_dist, 0.0),
            kappa_geom=max(self.kappa_geom - source.kappa_geom, 0.0),
            k_stein=max(self.k_stein - source.k_stein, 0.0),
        )


class SaturationConfig(AllomorphBaseModel):
    """Consolidated configuration for oversampled dynamic magnetic saturation."""

    vsat: float = Field(default=0.50, gt=0.0)
    alpha: float = Field(default=0.20, ge=0.0)
    alpha3: float = Field(default=0.08, ge=0.0)
    eta_hyst: float = Field(default=0.0, ge=0.0, le=1.0)
    k_sag: float = Field(default=0.08, ge=0.0)
    k_eddy: float = Field(default=0.0, ge=0.0)
    kappa_orbit: float = Field(default=0.0, ge=0.0)
    beta_curv: float = Field(default=0.0, ge=0.0)
    k_pull: float = Field(default=0.0, ge=0.0)
    tau_touch: float = Field(default=0.0, ge=0.0)
    kappa_geom: float = Field(default=0.0, ge=0.0)
    k_stein: float = Field(default=0.0, ge=0.0)
    k_emf: float = Field(default=0.0, ge=0.0)
    lambda_L: float = Field(default=0.0, ge=0.0)
    slew_limit: bool = True
    f_slew: float = Field(default=16000.0, gt=0.0)
    oversample: Literal[1, 2, 4] = 2
    displacement_weighting: bool = True
    magnet_drag: bool = True


# ==============================================================================
# 5. COIL & PICKUP SCHEMAS
# ==============================================================================


class CoilConfig(AllomorphBaseModel):
    """Physical sensing coil aperture geometry and string routing."""

    position_from_bridge_m: float = Field(..., gt=0.0)
    aperture_width_in: float = Field(0.75, gt=0.0)
    weight: float = Field(1.0, gt=0.0)
    polarity: float = 1.0
    strings: list[int | str] = Field(default_factory=lambda: ["all"])
    pole_type: str | None = None


class PickupComponentConfig(AllomorphBaseModel):
    """Component coil in a composite blended pickup configuration."""

    pickup: str | None = None
    position_from_bridge_m: float | None = None
    aperture_width_in: float = 0.75
    weight: float = 1.0
    polarity: float = 1.0
    strings: list[int | str] = Field(default_factory=lambda: ["all"])
    pole_type: str | None = None


class PickupConfig(AllomorphBaseModel):
    """Source instrument pickup configuration."""

    id: str | None = None
    name: str
    position_from_bridge_m: float | None = None
    aperture_width_in: float = 0.75
    coil_spacing_in: float = 0.0
    type: str = "single_coil"
    magnet_type: str | None = None
    resonant_frequency_hz: float | None = None
    q_factor: float | None = None
    coils: list[CoilConfig] = Field(default_factory=list)
    circuit: CircuitConfig | None = None
    components: list[PickupComponentConfig] = Field(default_factory=list)


# ==============================================================================
# 6. SOURCE INSTRUMENT SCHEMAS
# ==============================================================================


class InstrumentConfig(AllomorphBaseModel):
    """Complete source instrument definition."""

    id: str
    name: str
    scale_length_in: float = Field(..., gt=0.0)
    scale_length_m: float | None = None
    scale_min_in: float | None = None
    scale_max_in: float | None = None
    is_multiscale: bool = False
    electronics: str = "passive"
    string_wave_speeds: list[float] = Field(default_factory=list)
    default_pickup: str | None = None
    strings: InstrumentStringsConfig = Field(default_factory=InstrumentStringsConfig)
    pickups: dict[str, PickupConfig] = Field(default_factory=dict)
    pickup_mapping: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_instrument(self) -> Self:
        if self.scale_length_m is None:
            self.scale_length_m = self.scale_length_in * 0.0254
        if self.default_pickup and self.pickups and self.default_pickup not in self.pickups:
            raise KeyError(
                f"Instrument '{self.id}' default_pickup '{self.default_pickup}' "
                f"not found in pickups: {list(self.pickups.keys())}"
            )
        return self

    @classmethod
    def load(cls, identifier_or_path: str | Path | dict[str, Any]) -> InstrumentConfig:
        """Loads and validates an instrument configuration."""
        from allomorph.config.instruments import load_instrument

        return load_instrument(identifier_or_path)


# ==============================================================================
# 7. TARGET VOICE SCHEMAS
# ==============================================================================


class VoiceCoilConfig(AllomorphBaseModel):
    """Target voice coil sensing aperture geometry."""

    position_from_bridge_m: float = Field(..., gt=0.0)
    aperture_width_in: float = Field(0.75, gt=0.0)
    weight: float = Field(1.0, gt=0.0)
    polarity: float = 1.0
    strings: list[int | str] = Field(default_factory=lambda: ["all"])
    pole_type: str | None = None


class VoicePickupConfig(AllomorphBaseModel):
    """Multi-pickup target voice sub-pickup configuration."""

    name: str
    type: str = "single_coil"
    magnet_type: str | None = None
    alpha: float | None = None
    fr: float = Field(..., gt=0.0)
    Q: float = Field(..., gt=0.0)
    weight: float = Field(1.0, gt=0.0)
    polarity: float = 1.0
    coils: list[VoiceCoilConfig] = Field(default_factory=list)


class VoiceConfig(AllomorphBaseModel):
    """Complete target digital twin voice specification."""

    id: str
    name: str
    topology: str
    description: str
    blend_mode: str | None = None
    magnet_type: str | None = None
    sensor_type: Literal["magnetic", "bridge_force", "direct"] = "magnetic"
    target_string: str | None = None
    alpha: float = 0.0
    alpha3: float | None = None
    eta_hyst: float | None = None
    k_sag: float | None = None
    vsat: float | None = None
    k_eddy: float | None = None
    kappa_orbit: float | None = None
    k_body: float | None = None
    beta_curv: float | None = None
    k_pull: float | None = None
    tau_touch: float | None = None
    chi_mu: float | None = None
    k_dist: float | None = None
    kappa_geom: float | None = None
    k_stein: float | None = None
    k_emf: float | None = None
    lambda_L: float | None = None
    fr: float = Field(..., gt=0.0)
    Q: float = Field(..., gt=0.0)
    gain_db: float = 0.0
    scale: str = "34in"
    hpf: float | None = None
    preserve_aperture: bool | None = None
    coils: list[VoiceCoilConfig] = Field(default_factory=list)
    pickups: list[VoicePickupConfig] | None = None
    circuit: CircuitConfig

    @classmethod
    def load(cls, identifier_or_path: str | Path | dict[str, Any]) -> VoiceConfig:
        """Loads and validates a target voice configuration."""
        from allomorph.config.voices import VOICES, load_voice_config

        if isinstance(identifier_or_path, str) and identifier_or_path in VOICES:
            return VOICES[identifier_or_path]
        return load_voice_config(identifier_or_path)


# ==============================================================================
# 8. PIPELINE & STOREFRONT SCHEMAS
# ==============================================================================


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

"""
Allomorph - Acoustic Sensing Aperture & Spatial Boundary Engine
Computes 2D cylindrical rod Bessel apertures, 1D blade slit sinc apertures,
saddle witness-point boundary stiffness, body microphonics, and multi-coil
spatial responses across the continuous wave-speed continuum.
"""

import math
from collections.abc import Sequence
from typing import Any

import numpy as np

from allomorph.base import AllomorphBaseModel
from allomorph.config.geometry import resolve_pickup_coils, resolve_voice_coils
from allomorph.config.instruments import get_source_pickup, load_instrument
from allomorph.config.scales import SCALES
from allomorph.config.schema import (
    CoilConfig,
    InstrumentConfig,
    PickupConfig,
    VoiceCoilConfig,
    VoiceConfig,
)
from allomorph.config.voices import VOICES
from allomorph.physics.schema import WaveSpeedContinuumPoint
from allomorph.physics.strings import (
    compute_dispersive_wave_speed,
    generate_wave_speed_continuum,
    resolve_scale_range,
)

BODY_COUPLING_PROPERTIES = {
    "alnico_v": 0.08,
    "alnico_ii": 0.10,
    "ceramic": 0.03,
    "ceramic_alnico_hybrid": 0.05,
    "neodymium": 0.02,
    "active": 0.00,
}


def compute_body_microphonic_coupling(
    freqs: Sequence[float] | np.ndarray,
    src_pickup: PickupConfig | dict[str, Any] | AllomorphBaseModel,
    tgt_voice: VoiceConfig | dict[str, Any] | AllomorphBaseModel,
    inst: InstrumentConfig | dict[str, Any] | AllomorphBaseModel | None = None,
) -> np.ndarray:
    """
    Computes diffuse mechanical body-pickup microphonic coupling transfer curve.
    Unpotted and lightly potted vintage passive pickups exhibit subtle mechanical
    coupling to body vibrations around 6.2 kHz, damped above 9.5 kHz.
    Active epoxy-potted and sealed modern pickups have near-zero microphonic coupling.
    Evaluated differentially: Δk_body = max(k_tgt - k_src, 0.0).
    """
    freqs = np.asarray(freqs, dtype=np.float64)
    if inst is not None and inst.get("electronics") == "active":
        src_mag = "active"
    else:
        src_mag = src_pickup.get("magnet_type", src_pickup.get("magnet", "active"))

    tgt_mag = tgt_voice.get("magnet_type", tgt_voice.get("magnet", "alnico_v"))

    k_src = BODY_COUPLING_PROPERTIES.get(src_mag, 0.0)
    k_tgt = BODY_COUPLING_PROPERTIES.get(tgt_mag, BODY_COUPLING_PROPERTIES["alnico_v"])

    delta_k = max(k_tgt - k_src, 0.0)
    if delta_k <= 0.0:
        return np.ones_like(freqs)

    fb = 6200.0
    Qb = 1.8
    fdamp = 9500.0

    fn = freqs / fb
    denom = Qb * np.sqrt((1.0 - fn ** 2) ** 2 + (fn / Qb) ** 2)
    resonance = np.where(freqs > 10.0, fn / np.maximum(denom, 1e-9), 0.0)
    damping = np.exp(-((freqs / fdamp) ** 2))

    return 1.0 + delta_k * resonance * damping


def compute_coil_aperture(
    freqs: Sequence[float] | np.ndarray,
    v_disp: float | np.ndarray,
    w_m: float,
    pole_type: str = "rod",
) -> np.ndarray:
    """
    Computes spatial sensing aperture response across frequencies:
    - 'rod': 2D cylindrical pole piece (Airy / Bessel J1(x)/x algebraic approximation)
      ap(f) = 1 / sqrt(1 + 0.25 * (2*pi*r_p*f / v)^2) where r_p = w_m / 2.0
    - 'blade': 1D continuous bar/blade rectangular slit
      ap(f) = 1 / sqrt(1 + (1/3) * (pi*w_m*f / v)^2)
    Evaluates with C^inf smoothness, exact 1.000 at f=0, and 0.00 dB identity.
    """
    f = np.asarray(freqs, dtype=np.float64)
    if pole_type == "blade":
        arg = (math.pi * w_m * f) / v_disp
        return 1.0 / np.sqrt(1.0 + (1.0 / 3.0) * (arg ** 2))
    else:
        r_p = w_m / 2.0
        k = 2.0 * math.pi * f / v_disp
        return 1.0 / np.sqrt(1.0 + 0.25 * ((k * r_p) ** 2))


def compute_saddle_boundary_coupling(
    freqs: Sequence[float] | np.ndarray,
    pos_m: float,
    scale_m: float = 0.8636,
) -> np.ndarray:
    """
    Models the exponential boundary layer (l_b ≈ sqrt(B_s) * L) of flexural rigidity
    at the bridge saddle witness point for pickups situated close to the bridge (pos_m < 0.075 m).
    Smoothly transitions to 1.000 (0.00 dB) as distance increases to >= 75 mm.
    """
    f = np.asarray(freqs, dtype=np.float64)
    _ = scale_m
    if pos_m >= 0.075 or pos_m <= 0.0:
        return np.ones_like(f)
    ratio = np.clip(pos_m / 0.075, 0.0, 1.0)
    shelf_db = -4.0 * (1.0 - ratio)
    g = 10.0 ** (shelf_db / 20.0)
    f0 = 4500.0
    return np.sqrt((1.0 + (g ** 2) * (f / f0) ** 2) / (1.0 + (f / f0) ** 2))


def is_voice_matching_source(
    instrument: InstrumentConfig | dict[str, Any] | AllomorphBaseModel | str,
    voice_id: str,
    voice_cfg: VoiceConfig | dict[str, Any] | AllomorphBaseModel | None = None,
) -> bool:
    """
    Determines if a target voice matches the source instrument's physical scale and pickup geometry,
    meaning zero spatial or acoustic transfer is required (identity transformation).
    Tuning- and string-count-agnostic: matches on physical scale length and coil geometry.
    """
    inst = load_instrument(instrument) if not isinstance(instrument, (dict, AllomorphBaseModel)) else instrument
    vcfg = voice_cfg or VOICES.get(voice_id, {})

    src_range = resolve_scale_range(inst)
    tgt_scale = vcfg.get("scale", "34in")
    tgt_scale_info: Any = SCALES.get(tgt_scale, {})
    tgt_range = resolve_scale_range(tgt_scale_info)

    # Scale match based on physical vibrating length range (within 1.2 cm)
    if abs(src_range[0] - tgt_range[0]) > 0.012 or abs(src_range[1] - tgt_range[1]) > 0.012:
        return False

    src_p = get_source_pickup(inst, voice_id)
    src_coils = resolve_pickup_coils(src_p, inst)
    tgt_coils = resolve_voice_coils(vcfg)

    if len(src_coils) != len(tgt_coils):
        return False

    s_sort = sorted(src_coils, key=lambda c: c["position_from_bridge_m"])
    t_sort = sorted(tgt_coils, key=lambda c: c["position_from_bridge_m"])

    for sc, tc in zip(s_sort, t_sort):
        if abs(sc["position_from_bridge_m"] - tc["position_from_bridge_m"]) > 0.005:
            return False
        if abs(sc.get("aperture_width_in", 0.75) - tc.get("aperture_width_in", 0.75)) > 0.15:
            return False

    return True


def get_coil_register(coil: CoilConfig | VoiceCoilConfig | dict[str, Any] | AllomorphBaseModel) -> str:
    """
    Identifies whether a coil half is 'lower' (bass strings register),
    'upper' (treble strings register), or 'all' across the string bed.
    """
    reg = coil.get("register")
    if reg in ["lower", "bass", "low"]:
        return "lower"
    if reg in ["upper", "treble", "high"]:
        return "upper"
    if reg == "all":
        return "all"

    strings = coil.get("strings", ["all"])
    if "all" in strings:
        return "all"

    strings_set = set(strings)
    lower_markers = {"E", "A", "B", "low", "lower", "bass", 3, 4, 5, 6, "3", "4", "5", "6"}
    upper_markers = {"D", "G", "C", "high", "upper", "treble", 1, 2, "1", "2"}

    has_lower = bool(strings_set & lower_markers)
    has_upper = bool(strings_set & upper_markers)

    if has_lower and not has_upper:
        return "lower"
    elif has_upper and not has_lower:
        return "upper"
    return "all"


def numpy_pickup_acoustic_response(
    freqs: Sequence[float] | np.ndarray,
    coils: Sequence[CoilConfig | VoiceCoilConfig | dict[str, Any] | AllomorphBaseModel],
    scale_length_m: float | tuple[float, float] | list[float] | Sequence[float] | None = None,
    string_speeds: Sequence[float] | None = None,
    string_names: Sequence[str | int] | None = None,
) -> np.ndarray:
    """
    Computes compound spatial aperture and multi-coil response for an arbitrary
    array of N physical coils across the continuous wave-speed continuum of the instrument.
    Completely tuning-agnostic, gauge-agnostic, and string-count-agnostic.
    Respects geometric register half bindings for split-coil pickups (e.g. P-Bass).
    """
    f = np.asarray(freqs, dtype=np.float64)

    if isinstance(scale_length_m, (list, tuple, np.ndarray)) and len(scale_length_m) > 0 and any(float(v) > 10.0 for v in scale_length_m):
        string_speeds = scale_length_m
        scale_length_m = None

    scale_range = resolve_scale_range(scale_length_m)
    l_eff = (scale_range[0] + scale_range[1]) / 2.0

    if string_speeds is not None and len(string_speeds) > 0 and len(string_speeds) != 24:
        continuum: list[WaveSpeedContinuumPoint] = []
        n_str = len(string_speeds)
        half = n_str // 2 if n_str > 2 else 1
        for s_idx, v in enumerate(string_speeds):
            f0 = max(v / (2.0 * l_eff), 15.0)
            if string_names and s_idx < len(string_names):
                s_name = string_names[s_idx]
                if s_name in [1, 2, "1", "2", "D", "G", "C", "high", "upper", "treble"]:
                    reg = "upper"
                elif s_name in [3, 4, 5, 6, "3", "4", "5", "6", "E", "A", "B", "low", "lower", "bass"]:
                    reg = "lower"
                else:
                    reg = "lower" if s_idx < half else "upper"
            else:
                reg = "lower" if s_idx < half else "upper"
            continuum.append(
                WaveSpeedContinuumPoint(
                    f0=f0,
                    v0=float(v),
                    scale_m=l_eff,
                    register=reg,
                    weight=1.0 / n_str,
                )
            )
    else:
        continuum = generate_wave_speed_continuum(scale_range, num_points=24)

    acc = np.zeros_like(f, dtype=np.float64)
    total_pt_weight = 0.0

    for pt in continuum:
        f0 = float(pt.f0)
        v = float(pt.v0)
        pt_reg = str(pt.register)
        pt_weight = float(pt.weight)
        pt_scale_m = float(getattr(pt, "scale_m", l_eff))

        v_disp = compute_dispersive_wave_speed(f, v, f0=f0, scale_length_m=pt_scale_m)

        active: list[dict[str, Any] | AllomorphBaseModel] = []
        for c in coils:
            coil_reg = get_coil_register(c)
            if coil_reg == "all" or coil_reg == pt_reg:
                active.append(c)

        if not active:
            active = list(coils)

        total_w = sum(abs(c.get("weight", 1.0)) for c in active) or 1.0
        center_pos = sum(c["position_from_bridge_m"] * abs(c.get("weight", 1.0)) for c in active) / total_w

        coil_sum = np.zeros_like(f, dtype=np.complex128)
        p_incoh = np.zeros_like(f, dtype=np.float64)

        for c in active:
            pos_m = c["position_from_bridge_m"]
            w_m = c.get("aperture_width_in", 0.75) * 0.0254
            weight = c.get("weight", 1.0)
            polarity = c.get("polarity", 1.0)

            delta_x = pos_m - center_pos
            phase = 2.0 * math.pi * f * delta_x / v_disp
            c_pole = c.get("pole_type", "rod")
            ap_w = compute_coil_aperture(f, v_disp, w_m, pole_type=c_pole)
            w_eff = weight * ap_w

            coil_sum += w_eff * polarity * np.exp(-1j * phase)
            p_incoh += w_eff ** 2

        p_coh = np.abs(coil_sum) ** 2

        if len(active) > 1:
            delta_x_span = max(c["position_from_bridge_m"] for c in active) - min(
                c["position_from_bridge_m"] for c in active
            )
            if delta_x_span > 0.002:
                eps_quad = 0.18
                p_coh_reg = p_coh + (eps_quad ** 2) * p_incoh
                dc_incoh = sum(abs(c.get("weight", 1.0)) ** 2 for c in active)
                dc_norm = math.sqrt(total_w ** 2 + (eps_quad ** 2) * dc_incoh) / total_w

                f_start = v / delta_x_span
                f_end = 1.8 * v / delta_x_span
                t = np.clip((f - f_start) / (f_end - f_start), 0.0, 1.0)
                gamma = 0.5 * (1.0 + np.cos(np.pi * t))
                m_blend = np.sqrt(gamma * p_coh_reg + (1.0 - gamma) * p_incoh) / dc_norm
            else:
                m_blend = np.abs(coil_sum)
        else:
            m_blend = np.abs(coil_sum)

        acc += pt_weight * m_blend
        total_pt_weight += pt_weight

    return acc / total_pt_weight if total_pt_weight > 0 else acc


def numpy_pickup_macro_aperture(
    freqs: Sequence[float] | np.ndarray,
    coils: Sequence[CoilConfig | VoiceCoilConfig | dict[str, Any] | AllomorphBaseModel],
    scale_length_m: float | tuple[float, float] | list[float] | Sequence[float] | None = None,
    string_speeds: Sequence[float] | None = None,
    string_names: Sequence[str | int] | None = None,
) -> np.ndarray:
    """
    Computes the macro sensing aperture response (smooth spatial low-pass envelope
    of the individual coil aperture) averaged across the continuous wave-speed continuum,
    without inter-coil phase cancellation nulls or unphysical sinc sidelobes.
    Used for safe, non-inverting deconvolution of multi-coil source pickups.
    """
    f = np.asarray(freqs, dtype=np.float64)
    w_in = coils[0].get("aperture_width_in", 0.75) if coils else 0.75
    w_m = w_in * 0.0254

    if isinstance(scale_length_m, (list, tuple, np.ndarray)) and len(scale_length_m) > 0 and any(float(v) > 10.0 for v in scale_length_m):
        string_speeds = scale_length_m
        scale_length_m = None

    scale_range = resolve_scale_range(scale_length_m)
    l_eff = (scale_range[0] + scale_range[1]) / 2.0

    if string_speeds is not None and len(string_speeds) > 0 and len(string_speeds) != 24:
        continuum = [
            WaveSpeedContinuumPoint(
                f0=max(v / (2.0 * l_eff), 15.0),
                v0=float(v),
                scale_m=l_eff,
                register="lower" if i < len(string_speeds) // 2 else "upper",
                weight=1.0 / len(string_speeds),
            )
            for i, v in enumerate(string_speeds)
        ]
    else:
        continuum = generate_wave_speed_continuum(scale_range, num_points=24)

    acc = np.zeros_like(f, dtype=np.float64)
    total_w = 0.0
    c_pole = coils[0].get("pole_type", "rod") if coils else "rod"
    for pt in continuum:
        f0 = float(pt.f0)
        v = float(pt.v0)
        weight = float(pt.weight)
        pt_scale_m = float(getattr(pt, "scale_m", l_eff))
        v_disp = compute_dispersive_wave_speed(f, v, f0=f0, scale_length_m=pt_scale_m)
        acc += weight * compute_coil_aperture(f, v_disp, w_m, pole_type=c_pole)
        total_w += weight
    return acc / total_w if total_w > 0 else acc


def numpy_aperture(
    freqs: Sequence[float] | np.ndarray,
    w_in: float,
    d_in: float,
    speeds: Sequence[float] | None = None,
    scale_length_m: float = 0.8636,
) -> np.ndarray:
    """Computes multi-string aperture sinc + dual-coil comb using NumPy across the wave-speed continuum."""
    f = np.asarray(freqs, dtype=np.float64)
    w_m = w_in * 0.0254
    d_m = d_in * 0.0254
    if speeds is None:
        continuum = generate_wave_speed_continuum(scale_length_m)
        speeds = [pt["v0"] for pt in continuum]
    acc = np.zeros_like(f, dtype=np.float64)
    for v in speeds:
        sinc_v = np.abs(np.sinc(w_m * f / v)) + 0.05
        comb_v = np.abs(np.cos(np.pi * d_m * f / v)) + 0.05 if d_in > 0 else 1.0
        acc += sinc_v * comb_v
    return acc / len(speeds)


def numpy_position(
    freqs: Sequence[float] | np.ndarray,
    pos_m: float,
    speeds: Sequence[float] | None = None,
    scale_length_m: float = 0.8636,
) -> np.ndarray:
    """Computes spatial standing wave envelope using NumPy across the wave-speed continuum."""
    f = np.asarray(freqs, dtype=np.float64)
    if speeds is None:
        continuum = generate_wave_speed_continuum(scale_length_m)
        speeds = [pt["v0"] for pt in continuum]
    acc = np.zeros_like(f, dtype=np.float64)
    for v in speeds:
        arg_p = f * (2.0 * math.pi * pos_m / v)
        acc += np.abs(np.sin(arg_p)) + 0.15
    return acc / len(speeds)


pickup_acoustic_response = numpy_pickup_acoustic_response
aperture_response = numpy_aperture
position_envelope = numpy_position

"""
Allomorph - Nodal RLC Matrix Solver & Differential Transfer Functions
Evaluates closed-form nodal AC transfer functions across frequencies using
vectorized NumPy SIMD operations, Cole-Davidson dielectric relaxation,
Jordan after-effect permeability dispersion, and Wiener-regularized deconvolution.
"""

import math
from collections.abc import Sequence
from typing import Literal, overload

import numpy as np

from allomorph.circuit.parser import MAGNET_PROPERTIES, CircuitModel, eval_pot_taper
from allomorph.config.schema import (
    PickupConfig,
    PreampBandConfig,
    PreampConfig,
    VoiceConfig,
    VoicePickupConfig,
)
from allomorph.dsp import FREQS


def compute_core_impedance(
    s: complex | np.ndarray,
    L: float,
    L_core: float = 0.0,
    R_core: float = 0.0,
    chi_mu: float = 0.0,
    omega_mu: float = 2.0 * math.pi * 1200.0,
    k_skin: float = 0.0,
    omega_skin: float = 2.0 * math.pi * 3200.0,
    Rdc: float = 8000.0,
) -> complex | np.ndarray:
    """
    Computes Foster 2-stage ladder impedance of the coil inductor with
    Jordan after-effect complex magnetic permeability dispersion and
    solid pole eddy skin-effect dispersion:
    mu_rel(s) = 1.0 - chi_mu * ln(1.0 + s / omega_mu)
    Z_L(s) = mu_rel(s) * [s * L_inf + (s * L_core * R_core) / (s * L_core + R_core)] + Z_skin(s)
    where Z_skin(s) = Rdc * k_skin * (sqrt(1.0 + s / omega_skin) - 1.0)
    where L_inf = max(L - L_core, 0.0).
    Captures high-frequency magnetic flux expulsion from conductive pole pieces (skin effect),
    complex permeability dispersion, and eddy damping losses.
    """
    if chi_mu > 0.0:
        mu_rel = 1.0 - chi_mu * np.log(1.0 + s / omega_mu)
    else:
        mu_rel = 1.0

    if k_skin > 0.0 and omega_skin > 0.0:
        R_skin = Rdc * k_skin
        Z_skin = R_skin * (np.sqrt(1.0 + s / omega_skin) - 1.0)
    else:
        Z_skin = 0.0

    if L_core <= 0.0 or R_core <= 0.0:
        return s * L * mu_rel + Z_skin
    L_inf = max(L - L_core, 0.0)
    num = s * L_core * R_core
    den = s * L_core + R_core
    return (s * L_inf + (num / den)) * mu_rel + Z_skin


def apply_magnet_properties_to_model(
    model: CircuitModel,
    vcfg: VoiceConfig | PickupConfig,
    eddy_diffusion: bool = True,
) -> None:
    """
    Applies Foster 2-stage core eddy diffusion parameters (L_core, R_core),
    complex permeability dispersion (chi_mu), distributed winding factor (k_dist),
    and solid pole eddy skin-effect dispersion (k_skin, f_skin)
    to the CircuitModel based on authentic magnet metallurgy if not explicitly
    specified in the SPICE netlist.
    """
    if not eddy_diffusion:
        model.L_core = 0.0
        model.R_core = 0.0
        model.L_core_b = 0.0
        model.R_core_b = 0.0
        model.chi_mu = 0.0
        model.chi_mu_b = 0.0
        model.k_dist = 0.0
        model.k_dist_b = 0.0
        model.k_skin = 0.0
        model.k_skin_b = 0.0
        return

    mag_type_global = vcfg.magnet_type or "alnico_v"

    pickups: list[VoicePickupConfig] = vcfg.pickups or [] if isinstance(vcfg, VoiceConfig) else []

    if model.topology in ["parallel", "series"] and len(pickups) >= 2:
        mag_n = pickups[0].magnet_type or mag_type_global
        mag_b = pickups[1].magnet_type or mag_type_global
    else:
        mag_n = mag_type_global
        mag_b = mag_type_global

    if mag_n not in MAGNET_PROPERTIES:
        raise KeyError(
            f"Unknown magnet type '{mag_n}'. Available magnet types: {list(MAGNET_PROPERTIES.keys())}"
        )
    if mag_b not in MAGNET_PROPERTIES:
        raise KeyError(
            f"Unknown magnet type '{mag_b}'. Available magnet types: {list(MAGNET_PROPERTIES.keys())}"
        )
    props_n = MAGNET_PROPERTIES[mag_n]
    props_b = MAGNET_PROPERTIES[mag_b]

    if model.L_core <= 0.0 and props_n.k_core > 0.0:
        model.L_core = props_n.k_core * model.L
        f_c = props_n.f_core
        model.R_core = 2.0 * math.pi * f_c * model.L_core if f_c > 0.0 else 0.0

    if model.chi_mu <= 0.0 and props_n.chi_mu > 0.0:
        model.chi_mu = props_n.chi_mu
    if model.k_dist <= 0.0 and props_n.k_dist > 0.0:
        model.k_dist = props_n.k_dist
    if model.k_skin <= 0.0 and props_n.k_skin > 0.0:
        model.k_skin = props_n.k_skin
        model.f_skin = props_n.f_skin

    if model.topology in ["parallel", "series"]:
        if model.L_core_b <= 0.0 and props_b.k_core > 0.0:
            model.L_core_b = props_b.k_core * model.L_b
            f_cb = props_b.f_core
            model.R_core_b = 2.0 * math.pi * f_cb * model.L_core_b if f_cb > 0.0 else 0.0

        if model.chi_mu_b <= 0.0 and props_b.chi_mu > 0.0:
            model.chi_mu_b = props_b.chi_mu
        if model.k_dist_b <= 0.0 and props_b.k_dist > 0.0:
            model.k_dist_b = props_b.k_dist
        if model.k_skin_b <= 0.0 and props_b.k_skin > 0.0:
            model.k_skin_b = props_b.k_skin
            model.f_skin_b = props_b.f_skin


def evaluate_analog_band(band: PreampBandConfig, s: complex | np.ndarray) -> complex | np.ndarray:
    """Evaluates continuous s-domain analog transfer function for a single EQ band."""
    b_type = band.type
    f0 = band.freq_hz
    g_db = band.gain_db
    w0 = 2.0 * math.pi * f0
    g = 10.0 ** (g_db / 20.0)

    if b_type == "low_shelf":
        return (s + g * w0) / (s + w0)
    elif b_type == "high_shelf":
        return (g * s + w0) / (s + w0)
    elif b_type == "bell":
        q = float(band.q) if band.q is not None else 1.0
        num = s**2 + (w0 / q) * g * s + w0**2
        den = s**2 + (w0 / q) * s + w0**2
        return num / den
    elif b_type == "low_pass":
        return w0 / (s + w0)
    elif b_type == "high_pass":
        return s / (s + w0)
    return np.ones_like(s, dtype=np.complex128)


def compute_active_preamp_transfer(
    bands: Sequence[PreampBandConfig] | None, s: complex | np.ndarray, gain_db: float = 0.0
) -> np.ndarray:
    """Evaluates the composite analog active preamp contour across frequencies with finite DC transmission."""
    h_total = np.ones_like(s, dtype=np.complex128) * (10.0 ** (gain_db / 20.0))
    if not bands:
        return h_total
    for band in bands:
        h_total = h_total * evaluate_analog_band(band, s)
    return h_total


def compute_active_preamp_eq(
    preamp_spec: str | PreampConfig | Sequence[PreampBandConfig], s: complex | np.ndarray
) -> np.ndarray:
    """
    Evaluates analog active preamp contour transfer function.
    Accepts:
      - str (preset name): looks up in PREAMPS catalog (e.g. 'sadowsky_2band', 'stingray_2band')
      - PreampConfig: evaluates preamp model
      - Sequence[PreampBandConfig]: evaluates sequence of band configs
    """
    if isinstance(preamp_spec, str):
        from allomorph.config.preamps import get_preamp

        preset = get_preamp(preamp_spec)
        return compute_active_preamp_transfer(preset.bands, s, gain_db=float(preset.gain_db))
    elif isinstance(preamp_spec, PreampConfig):
        return compute_active_preamp_transfer(
            preamp_spec.bands, s, gain_db=float(preamp_spec.gain_db)
        )
    elif isinstance(preamp_spec, (list, tuple)):
        return compute_active_preamp_transfer(preamp_spec, s)
    return np.ones_like(s, dtype=np.complex128)


@overload
def compute_circuit_transfer_functions(
    model: CircuitModel,
    freqs: Sequence[float] | np.ndarray = FREQS,
    return_numpy: Literal[False] = False,
) -> list[list[float]]: ...


@overload
def compute_circuit_transfer_functions(
    model: CircuitModel,
    freqs: Sequence[float] | np.ndarray = FREQS,
    return_numpy: Literal[True] = ...,
) -> list[np.ndarray]: ...


@overload
def compute_circuit_transfer_functions(
    model: CircuitModel,
    freqs: Sequence[float] | np.ndarray = FREQS,
    return_numpy: bool = ...,
) -> list[list[float]] | list[np.ndarray]: ...


def compute_circuit_transfer_functions(
    model: CircuitModel,
    freqs: Sequence[float] | np.ndarray = FREQS,
    return_numpy: bool = False,
) -> list[list[float]] | list[np.ndarray]:
    """
    Computes closed-form nodal AC transfer functions across frequencies using vectorized NumPy SIMD operations.
    Returns a list of magnitude curves:
      - Single-pickup: [mag_curve] (length 1)
      - Dual-pickup (parallel or series): [mag_neck, mag_bridge] (length 2)
    Supports both passive high-Z harnesses and active buffered preamps.
    """

    def _ret(res_list: list[np.ndarray]) -> list[list[float]] | list[np.ndarray]:
        if return_numpy:
            return res_list
        return [np.asarray(x, dtype=np.float64).tolist() for x in res_list]

    f = np.asarray(freqs, dtype=np.float64)
    if model.no_eq:
        return _ret([np.ones_like(f)])

    w = np.where(f == 0.0, 2.0 * np.pi * 1e-3, 2.0 * np.pi * f)
    s = 1j * w

    # Dielectric absorption parameters (Cole-Davidson fractional-order relaxation)
    alpha_cable = model.alpha_dielectric_cable
    alpha_tone = model.alpha_dielectric_tone
    w0 = 2.0 * np.pi * 1000.0  # 1 kHz calibration reference frequency
    s_norm = np.maximum(w / w0, 1e-6)

    phase_factor_cable = np.exp(1j * (alpha_cable - 1.0) * (np.pi / 2.0))
    Y_cable_diel = s * model.Ccable * (s_norm ** (alpha_cable - 1.0)) * phase_factor_cable

    if model.Ctone > 0:
        phase_factor_tone = np.exp(1j * (alpha_tone - 1.0) * (np.pi / 2.0))
        Y_c_tone = s * model.Ctone * (s_norm ** (alpha_tone - 1.0)) * phase_factor_tone
        Y_tone = Y_c_tone / (1.0 + Y_c_tone * model.Rtone) if model.Rtone > 0 else Y_c_tone
    else:
        Y_tone = 0.0

    k_m = model.k_mutual
    c_m = model.C_mutual

    chi_mu = model.chi_mu
    chi_mu_b = model.chi_mu_b
    omega_mu = model.omega_mu

    k_dist = model.k_dist
    k_dist_b = model.k_dist_b
    omega_dist = model.omega_dist

    k_skin = model.k_skin
    f_skin = model.f_skin
    omega_skin = 2.0 * math.pi * f_skin if f_skin > 0.0 else 1.0

    k_skin_b = model.k_skin_b
    f_skin_b = model.f_skin_b
    omega_skin_b = 2.0 * math.pi * f_skin_b if f_skin_b > 0.0 else 1.0

    if k_dist > 0.0:
        gamma_dist = k_dist * np.sqrt(s / omega_dist)
        dist_factor = np.where(np.abs(gamma_dist) < 1e-5, 1.0, np.tanh(gamma_dist) / gamma_dist)
    else:
        dist_factor = 1.0

    if k_dist_b > 0.0:
        gamma_dist_b = k_dist_b * np.sqrt(s / omega_dist)
        dist_factor_b = np.where(
            np.abs(gamma_dist_b) < 1e-5, 1.0, np.tanh(gamma_dist_b) / gamma_dist_b
        )
    else:
        dist_factor_b = 1.0

    tan_d_coil = model.tan_delta_coil
    G_coil = w * model.Ccoil * tan_d_coil if tan_d_coil > 0.0 else 0.0
    G_coil_b = w * model.Ccoil_b * tan_d_coil if tan_d_coil > 0.0 else 0.0
    Y_c_n = (s * model.Ccoil + G_coil) * dist_factor
    Y_c_b = (s * model.Ccoil_b + G_coil_b) * dist_factor_b

    if model.has_active_buffer:
        # Active Preamp Buffer: coils terminate into high-Z buffer, isolating them from cable capacitance.
        # Op-amp buffer drives cable and Anagram pedalboard load through low-Z output stage.
        Z_cable_load = 1.0 / (1.0 / model.Ranagram + Y_cable_diel + s * model.Canagram)
        H_buf_to_out = Z_cable_load / (model.R_out + Z_cable_load)

        # Preamp active contour & voltage gain scaling
        preamp_gain = model.preamp_gain
        preamp_bands = model.preamp_bands
        if preamp_bands is not None:
            H_eq = (
                compute_active_preamp_transfer(preamp_bands, s, gain_db=model.preamp_gain_db)
                * preamp_gain
            )
        else:
            H_eq = compute_active_preamp_eq(model.preamp_type, s) * preamp_gain

        # Coils terminated into high-Z preamp input (R_preamp_in || C_preamp_in)
        Y_preamp_in = 1.0 / model.R_preamp_in + s * model.C_preamp_in
        Y_eff2 = Y_preamp_in + Y_tone

        if model.topology == "single":
            Z_L = compute_core_impedance(
                s,
                model.L,
                model.L_core,
                model.R_core,
                chi_mu=chi_mu,
                omega_mu=omega_mu,
                k_skin=k_skin,
                omega_skin=omega_skin,
                Rdc=model.Rdc,
            )
            Y_branch = 1.0 / (model.Rdc + Z_L) + 1.0 / model.Reddy
            Y_shunt2 = Y_c_n + Y_eff2
            H_dyn_to_2 = Y_branch / (Y_branch + Y_shunt2)

            H_total = H_dyn_to_2 * H_eq * H_buf_to_out
            return _ret([np.abs(H_total)])

        elif model.topology == "parallel":
            Z_L = compute_core_impedance(
                s,
                model.L,
                model.L_core,
                model.R_core,
                chi_mu=chi_mu,
                omega_mu=omega_mu,
                k_skin=k_skin,
                omega_skin=omega_skin,
                Rdc=model.Rdc,
            )
            Z_L_b = compute_core_impedance(
                s,
                model.L_b,
                model.L_core_b,
                model.R_core_b,
                chi_mu=chi_mu_b,
                omega_mu=omega_mu,
                k_skin=k_skin_b,
                omega_skin=omega_skin_b,
                Rdc=model.Rdc_b,
            )
            Y_br_n = 1.0 / (model.Rdc + Z_L) + 1.0 / model.Reddy
            Y_br_b = 1.0 / (model.Rdc_b + Z_L_b) + 1.0 / model.Reddy_b

            r_pot_n = model.Rpot_n
            r_pot_b = model.Rpot_b
            if r_pot_n > 0.0:
                Y_br_n = 1.0 / (1.0 / Y_br_n + r_pot_n)
            if r_pot_b > 0.0:
                Y_br_b = 1.0 / (1.0 / Y_br_b + r_pot_b)

            Y_shunt2 = Y_c_n + Y_c_b + Y_eff2

            if k_m > 0.0 or c_m > 0.0:
                M = k_m * np.sqrt(model.L * model.L_b) if k_m > 0.0 else 0.0
                Z_m = s * M
                Y_m = s * c_m
                Z_n = 1.0 / Y_br_n
                Z_b = 1.0 / Y_br_b
                delta_Z = Z_n * Z_b - (Z_m**2)
                denom_total = delta_Z * (Y_shunt2 + Y_m) + Z_n + Z_b - 2.0 * Z_m
                H_n_to_2 = (Z_b - Z_m) / denom_total
                H_b_to_2 = (Z_n - Z_m) / denom_total
            else:
                Y_total = Y_br_n + Y_br_b + Y_shunt2
                H_n_to_2 = Y_br_n / Y_total
                H_b_to_2 = Y_br_b / Y_total

            H_n = H_n_to_2 * H_eq * H_buf_to_out
            H_b = H_b_to_2 * H_eq * H_buf_to_out

            blend_pos = model.blend_pos
            if abs(blend_pos - 0.5) >= 1e-4:
                taper = model.pot_taper

                if blend_pos < 0.5:
                    gain_n = 1.0
                    norm_atten = (0.5 - blend_pos) / 0.5
                    gain_b = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
                else:
                    gain_b = 1.0
                    norm_atten = (blend_pos - 0.5) / 0.5
                    gain_n = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
                H_n = H_n * gain_n
                H_b = H_b * gain_b

            return _ret([np.abs(H_n), np.abs(H_b)])

        elif model.topology == "series":
            Z_L = compute_core_impedance(
                s,
                model.L,
                model.L_core,
                model.R_core,
                chi_mu=chi_mu,
                omega_mu=omega_mu,
                k_skin=k_skin,
                omega_skin=omega_skin,
                Rdc=model.Rdc,
            )
            Z_L_b = compute_core_impedance(
                s,
                model.L_b,
                model.L_core_b,
                model.R_core_b,
                chi_mu=chi_mu_b,
                omega_mu=omega_mu,
                k_skin=k_skin_b,
                omega_skin=omega_skin_b,
                Rdc=model.Rdc_b,
            )
            Y_br_n = 1.0 / (model.Rdc + Z_L) + 1.0 / model.Reddy
            Y_br_b = 1.0 / (model.Rdc_b + Z_L_b) + 1.0 / model.Reddy_b
            Y_cn = Y_c_n
            Y_cb = Y_c_b
            Y_2b = Y_br_b + Y_cb

            Y_m = Y_br_n + Y_cn + Y_2b
            Y_2 = Y_2b + Y_eff2
            delta = Y_m * Y_2 - Y_2b**2

            T2_n = (Y_2b * Y_br_n) / delta
            T2_b = ((Y_br_n + Y_cn) * Y_br_b) / delta

            H_n = T2_n * H_eq * H_buf_to_out
            H_b = T2_b * H_eq * H_buf_to_out

            blend_pos = model.blend_pos
            if abs(blend_pos - 0.5) >= 1e-4:
                taper = model.pot_taper

                if blend_pos < 0.5:
                    gain_n = 1.0
                    norm_atten = (0.5 - blend_pos) / 0.5
                    gain_b = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
                else:
                    gain_b = 1.0
                    norm_atten = (blend_pos - 0.5) / 0.5
                    gain_n = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
                H_n = H_n * gain_n
                H_b = H_b * gain_b

            return _ret([np.abs(H_n), np.abs(H_b)])

    # Passive RLC Guitar Harness: Coils directly loaded by pots, cable capacitance, and Anagram load
    Rload = (model.Rbot * model.Ranagram) / (model.Rbot + model.Ranagram)
    tan_d = model.tan_delta
    G_diel = w * model.Ccable * tan_d if tan_d > 0.0 else 0.0
    Zload = 1.0 / (1.0 / Rload + Y_cable_diel + s * model.Canagram + G_diel)

    # Treble bleed impedance (if configured)
    if model.Ctb > 0 and model.Rtb_par > 0:
        Z_tb = model.Rtb_ser + model.Rtb_par / (1.0 + s * model.Rtb_par * model.Ctb)
        Z23_pot = (model.Rtop * Z_tb) / (model.Rtop + Z_tb)
    else:
        Z23_pot = model.Rtop

    if model.topology == "single":
        Z_L = compute_core_impedance(
            s,
            model.L,
            model.L_core,
            model.R_core,
            chi_mu=chi_mu,
            omega_mu=omega_mu,
            k_skin=k_skin,
            omega_skin=omega_skin,
            Rdc=model.Rdc,
        )
        Y_branch = 1.0 / (model.Rdc + Z_L) + 1.0 / model.Reddy
        Y_shunt2 = Y_c_n + Y_tone

        Z_rick = 1.0 / (s * model.Crick) if model.Crick > 0 else 0.0
        Z23 = Z_rick + Z23_pot

        Y_eff2 = Y_shunt2 + 1.0 / (Z23 + Zload)
        H_dyn_to_2 = Y_branch / (Y_branch + Y_eff2)
        H_2_to_3 = Zload / (Z23 + Zload)
        H_total = np.where((f == 0.0) & (model.Crick > 0), 0.0, np.abs(H_dyn_to_2 * H_2_to_3))
        return _ret([H_total])

    elif model.topology == "parallel":
        Z_L = compute_core_impedance(
            s,
            model.L,
            model.L_core,
            model.R_core,
            chi_mu=chi_mu,
            omega_mu=omega_mu,
            k_skin=k_skin,
            omega_skin=omega_skin,
            Rdc=model.Rdc,
        )
        Z_L_b = compute_core_impedance(
            s,
            model.L_b,
            model.L_core_b,
            model.R_core_b,
            chi_mu=chi_mu_b,
            omega_mu=omega_mu,
            k_skin=k_skin_b,
            omega_skin=omega_skin_b,
            Rdc=model.Rdc_b,
        )
        Y_br_n = 1.0 / (model.Rdc + Z_L) + 1.0 / model.Reddy
        Y_br_b = 1.0 / (model.Rdc_b + Z_L_b) + 1.0 / model.Reddy_b

        r_pot_n = model.Rpot_n
        r_pot_b = model.Rpot_b
        if r_pot_n > 0.0:
            Y_br_n = 1.0 / (1.0 / Y_br_n + r_pot_n)
        if r_pot_b > 0.0:
            Y_br_b = 1.0 / (1.0 / Y_br_b + r_pot_b)

        Y_shunt2 = Y_c_n + Y_c_b + Y_tone
        Z23 = Z23_pot

        Y_out_branch = 1.0 / (Z23 + Zload)
        Y_eff2 = Y_shunt2 + Y_out_branch

        if k_m > 0.0 or c_m > 0.0:
            M = k_m * np.sqrt(model.L * model.L_b) if k_m > 0.0 else 0.0
            Z_m = s * M
            Y_m = s * c_m
            Z_n = 1.0 / Y_br_n
            Z_b = 1.0 / Y_br_b
            delta_Z = Z_n * Z_b - (Z_m**2)
            denom_total = delta_Z * (Y_eff2 + Y_m) + Z_n + Z_b - 2.0 * Z_m
            H_n_to_2 = (Z_b - Z_m) / denom_total
            H_b_to_2 = (Z_n - Z_m) / denom_total
        else:
            Y_total = Y_br_n + Y_br_b + Y_eff2
            H_n_to_2 = Y_br_n / Y_total
            H_b_to_2 = Y_br_b / Y_total

        H_2_to_3 = Zload / (Z23 + Zload)
        H_n = H_n_to_2 * H_2_to_3
        H_b = H_b_to_2 * H_2_to_3

        blend_pos = model.blend_pos
        if abs(blend_pos - 0.5) >= 1e-4:
            taper = model.pot_taper

            if blend_pos < 0.5:
                gain_n = 1.0
                norm_atten = (0.5 - blend_pos) / 0.5
                gain_b = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
            else:
                gain_b = 1.0
                norm_atten = (blend_pos - 0.5) / 0.5
                gain_n = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
            H_n = H_n * gain_n
            H_b = H_b * gain_b

        return _ret([np.abs(H_n), np.abs(H_b)])

    elif model.topology == "series":
        Z_L = compute_core_impedance(
            s,
            model.L,
            model.L_core,
            model.R_core,
            chi_mu=chi_mu,
            omega_mu=omega_mu,
            k_skin=k_skin,
            omega_skin=omega_skin,
            Rdc=model.Rdc,
        )
        Z_L_b = compute_core_impedance(
            s,
            model.L_b,
            model.L_core_b,
            model.R_core_b,
            chi_mu=chi_mu_b,
            omega_mu=omega_mu,
            k_skin=k_skin_b,
            omega_skin=omega_skin_b,
            Rdc=model.Rdc_b,
        )
        Y_br_n = 1.0 / (model.Rdc + Z_L) + 1.0 / model.Reddy
        Y_br_b = 1.0 / (model.Rdc_b + Z_L_b) + 1.0 / model.Reddy_b
        Y_cn = Y_c_n
        Y_cb = Y_c_b
        Y_2b = Y_br_b + Y_cb

        Z23 = Z23_pot
        Y_out_load = 1.0 / (Z23 + Zload)

        Y_m = Y_br_n + Y_cn + Y_2b
        Y_2 = Y_2b + Y_out_load + Y_tone
        delta = Y_m * Y_2 - Y_2b**2

        T2_n = (Y_2b * Y_br_n) / delta
        T2_b = ((Y_br_n + Y_cn) * Y_br_b) / delta
        T_2_to_3 = Zload / (Z23 + Zload)

        H_n = T2_n * T_2_to_3
        H_b = T2_b * T_2_to_3

        blend_pos = model.blend_pos
        if abs(blend_pos - 0.5) >= 1e-4:
            taper = model.pot_taper

            if blend_pos < 0.5:
                gain_n = 1.0
                norm_atten = (0.5 - blend_pos) / 0.5
                gain_b = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
            else:
                gain_b = 1.0
                norm_atten = (blend_pos - 0.5) / 0.5
                gain_n = max(1.0 - eval_pot_taper(norm_atten, taper), 0.0)
            H_n = H_n * gain_n
            H_b = H_b * gain_b

        return _ret([np.abs(H_n), np.abs(H_b)])

    raise ValueError(f"Unknown circuit topology: {model.topology}")


def compute_differential_circuit_transfer_functions(
    target_model: CircuitModel,
    source_model: CircuitModel,
    freqs: Sequence[float] | np.ndarray = FREQS,
    max_boost_db: float = 6.0,
    eps: float = 0.05,
) -> list[list[float]]:
    """
    Computes regularized differential AC transfer functions for passive-to-passive modeling:
    |H_diff(s)| = (|H_target(s)| * |H_source(s)|) / (|H_source(s)|^2 + eps^2)
    with Wiener regularization and frequency-dependent high-frequency gain clamping (<= max_boost_db
    above 4.5 kHz) to prevent amplifying passive coil hum, Johnson noise, or cable hiss.
    """
    tgt_curves = compute_circuit_transfer_functions(target_model, freqs=freqs)
    src_curves = compute_circuit_transfer_functions(source_model, freqs=freqs)

    f_arr = np.asarray(freqs, dtype=np.float64)

    diff_curves = []
    for ch_idx, tgt_c in enumerate(tgt_curves):
        if len(tgt_curves) == 1 and len(src_curves) > 1:
            # Parallel multi-pickup source summing into single-channel canonical/target stage:
            # Net source electrical transfer function is the sum of parallel branch currents
            src_arr = np.sum(src_curves, axis=0)
        else:
            src_c = src_curves[ch_idx] if len(src_curves) > ch_idx else src_curves[0]
            src_arr = np.asarray(src_c, dtype=np.float64)

        tgt_arr = np.asarray(tgt_c, dtype=np.float64)

        if np.allclose(tgt_arr, src_arr, rtol=1e-4):
            diff_curves.append(np.ones_like(tgt_arr).tolist())
            continue

        # Wiener regularized quotient
        h_diff = (tgt_arr * src_arr) / (src_arr**2 + eps**2)

        # Convert to absolute dB (linear ratio between target and source circuits)
        h_db = 20.0 * np.log10(np.maximum(h_diff, 1e-6))

        # Soft-knee limiting: smoothly saturate boost towards max_boost_db
        knee_width = min(2.5, max_boost_db / 2.0)
        thresh = max_boost_db - knee_width
        excess = np.maximum(h_db - thresh, 0.0)
        h_db_soft = np.where(
            h_db > thresh, thresh + knee_width * np.tanh(excess / knee_width), h_db
        )

        # Smooth high-frequency cosine taper above 8.0 kHz to 20.0 kHz
        # Eliminates unnatural flat horizontal ceilings and suppresses extreme ultrasonic noise
        f_start = 8000.0
        f_end = 20000.0
        t = np.clip((f_arr - f_start) / (f_end - f_start), 0.0, 1.0)
        w = 0.5 * (1.0 + np.cos(np.pi * t))
        s = 0.25 + 0.75 * w
        # Smooth C^inf transition: softplus ensures strictly monotonic, C^1 smooth blending across 0 dB
        excess_boost = (1.0 / 1.2) * np.logaddexp(0.0, 1.2 * h_db_soft)
        h_db_final = h_db_soft - (1.0 - s) * excess_boost

        h_diff_smooth = 10.0 ** (h_db_final / 20.0)
        diff_curves.append(h_diff_smooth.tolist())

    return diff_curves

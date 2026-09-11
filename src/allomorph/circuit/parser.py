"""
Allomorph - Circuit Model & Declarative Netlist Parser
Parses Allomorph declarative circuit configurations into structured CircuitModel instances
with engineering unit suffixes, continuous pot tapers, and wiper positioning.
"""

import copy
import math
from pathlib import Path
from typing import Any

import numpy as np
from pydantic import BaseModel

from allomorph.config.schema import MagnetPropertiesConfig, parse_spice_unit

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def parse_spice_val(val_str: str) -> float:
    """Parses standard SPICE engineering suffix notation (k, Meg, p, n, u, m, g)."""
    return float(parse_spice_unit(val_str))


_RAW_MAGNET_PROPERTIES: dict[str, dict[str, float]] = {
    "alnico_v": {
        "k_core": 0.08,
        "f_core": 2500.0,
        "k_skin": 0.10,
        "f_skin": 3200.0,
        "lambda_L": 0.05,
        "k_emf": 0.04,
        "eta_hyst": 0.06,
        "alpha": 0.26,
        "alpha3": 0.10,
        "k_sag": 0.08,
        "vsat": 0.50,
        "k_eddy": 0.16,
        "kappa_orbit": 0.06,
        "k_body": 0.08,
        "beta_curv": 0.035,
        "k_pull": 0.040,
        "tau_touch": 0.045,
        "chi_mu": 0.035,
        "k_dist": 0.18,
        "kappa_geom": 0.20,
        "k_stein": 0.030,
    },
    "alnico_ii": {
        "k_core": 0.10,
        "f_core": 1800.0,
        "k_skin": 0.12,
        "f_skin": 2800.0,
        "lambda_L": 0.07,
        "k_emf": 0.05,
        "eta_hyst": 0.09,
        "alpha": 0.32,
        "alpha3": 0.14,
        "k_sag": 0.12,
        "vsat": 0.45,
        "k_eddy": 0.20,
        "kappa_orbit": 0.07,
        "k_body": 0.10,
        "beta_curv": 0.050,
        "k_pull": 0.025,
        "tau_touch": 0.035,
        "chi_mu": 0.050,
        "k_dist": 0.22,
        "kappa_geom": 0.24,
        "k_stein": 0.040,
    },
    "ceramic": {
        "k_core": 0.02,
        "f_core": 6500.0,
        "k_skin": 0.00,
        "f_skin": 0.0,
        "lambda_L": 0.02,
        "k_emf": 0.02,
        "eta_hyst": 0.02,
        "alpha": 0.12,
        "alpha3": 0.04,
        "k_sag": 0.03,
        "vsat": 0.70,
        "k_eddy": 0.03,
        "kappa_orbit": 0.02,
        "k_body": 0.03,
        "beta_curv": 0.010,
        "k_pull": 0.015,
        "tau_touch": 0.025,
        "chi_mu": 0.010,
        "k_dist": 0.12,
        "kappa_geom": 0.15,
        "k_stein": 0.015,
    },
    "ceramic_alnico_hybrid": {
        "k_core": 0.05,
        "f_core": 4500.0,
        "k_skin": 0.05,
        "f_skin": 4500.0,
        "lambda_L": 0.03,
        "k_emf": 0.03,
        "eta_hyst": 0.04,
        "alpha": 0.18,
        "alpha3": 0.07,
        "k_sag": 0.05,
        "vsat": 0.60,
        "k_eddy": 0.08,
        "kappa_orbit": 0.04,
        "k_body": 0.05,
        "beta_curv": 0.020,
        "k_pull": 0.025,
        "tau_touch": 0.035,
        "chi_mu": 0.020,
        "k_dist": 0.15,
        "kappa_geom": 0.18,
        "k_stein": 0.025,
    },
    "neodymium": {
        "k_core": 0.01,
        "f_core": 8500.0,
        "k_skin": 0.02,
        "f_skin": 8000.0,
        "lambda_L": 0.01,
        "k_emf": 0.01,
        "eta_hyst": 0.01,
        "alpha": 0.08,
        "alpha3": 0.02,
        "k_sag": 0.01,
        "vsat": 0.90,
        "k_eddy": 0.01,
        "kappa_orbit": 0.01,
        "k_body": 0.01,
        "beta_curv": 0.005,
        "k_pull": 0.010,
        "tau_touch": 0.015,
        "chi_mu": 0.005,
        "k_dist": 0.10,
        "kappa_geom": 0.10,
        "k_stein": 0.008,
    },
    "piezo": {
        "k_core": 0.00,
        "f_core": 0.0,
        "k_skin": 0.00,
        "f_skin": 0.0,
        "lambda_L": 0.00,
        "k_emf": 0.00,
        "eta_hyst": 0.00,
        "alpha": 0.00,
        "alpha3": 0.00,
        "k_sag": 0.00,
        "vsat": 1.00,
        "k_eddy": 0.00,
        "kappa_orbit": 0.00,
        "k_body": 0.00,
        "beta_curv": 0.000,
        "k_pull": 0.000,
        "tau_touch": 0.000,
        "chi_mu": 0.000,
        "k_dist": 0.00,
        "kappa_geom": 0.00,
        "k_stein": 0.000,
    },
    "active": {
        "k_core": 0.00,
        "f_core": 0.0,
        "k_skin": 0.00,
        "f_skin": 0.0,
        "lambda_L": 0.00,
        "k_emf": 0.00,
        "eta_hyst": 0.00,
        "alpha": 0.00,
        "alpha3": 0.00,
        "k_sag": 0.00,
        "vsat": 1.20,
        "k_eddy": 0.00,
        "kappa_orbit": 0.00,
        "k_body": 0.00,
        "beta_curv": 0.000,
        "k_pull": 0.000,
        "tau_touch": 0.000,
        "chi_mu": 0.000,
        "k_dist": 0.00,
        "kappa_geom": 0.00,
        "k_stein": 0.000,
    },
}

MAGNET_PROPERTIES: dict[str, MagnetPropertiesConfig] = {
    k: MagnetPropertiesConfig.model_validate(v) for k, v in _RAW_MAGNET_PROPERTIES.items()
}
MAGNET_PROPERTIES["hybrid"] = MAGNET_PROPERTIES["ceramic_alnico_hybrid"]


def eval_pot_taper(pos: float, taper: str = "audio") -> float:
    """
    Evaluates potentiometer electrical resistance fraction (0.0 to 1.0) given mechanical wiper rotation pos (0.0 to 1.0).
    Supported tapers:
      - 'linear': f(theta) = theta
      - 'audio' / 'audio10': Standard CTS 10% audio taper (f(0.5) = 0.10).
      - 'audio15': Standard Bourns 15% audio taper (f(0.5) = 0.15).
      - 'reverse_audio': Standard reverse log taper.
      - 'mn_blend': Bourns MN blend pot taper.
    Satisfies Guardrail 5.2: C^inf smooth, strictly monotonic, zero slope kinks, exact (0,0) and (1,1) endpoints.
    Formula: f(theta; gamma) = (exp(gamma * theta) - 1.0) / (exp(gamma) - 1.0)
    where gamma = 2 * ln(1/k - 1).
    """
    theta = float(np.clip(pos, 0.0, 1.0))
    t = taper.lower().strip() if isinstance(taper, str) and taper.lower().strip() not in ("", "none") else "audio"
    if t == "linear":
        return theta
    elif t in ("audio", "audio10"):
        gamma = 4.394449154672439  # ln(81) = 2 * ln(9) -> 10% at 50% rotation
    elif t == "audio15":
        gamma = 3.4689389547514337  # 2 * ln(1/0.15 - 1) -> 15% at 50% rotation
    elif t == "reverse_audio":
        gamma = 4.394449154672439
        return float(1.0 - np.expm1(gamma * (1.0 - theta)) / np.expm1(gamma))
    elif t == "mn_blend":
        return theta
    else:
        raise ValueError(
            f"Unknown pot taper '{taper}'. Supported tapers: 'audio', 'audio10', 'audio15', 'linear', 'reverse_audio', 'mn_blend'."
        )

    return float(np.expm1(gamma * theta) / np.expm1(gamma))


class CircuitModel:
    """Represents a parsed RLC guitar circuit digital twin."""

    topology: str
    vsat: float
    vsat_n: float
    vsat_b: float
    L: float
    L_core: float
    R_core: float
    Rdc: float
    Reddy: float
    Ccoil: float
    L_b: float
    L_core_b: float
    R_core_b: float
    Rdc_b: float
    Reddy_b: float
    Ccoil_b: float
    Ctone: float
    Rtone: float
    Crick: float
    Rtop: float
    Rbot: float
    Ctb: float
    Rtb_par: float
    Rtb_ser: float
    has_active_buffer: bool
    preamp_type: str
    preamp_bands: list[dict[str, Any]] | None
    preamp_gain: float
    R_preamp_in: float
    C_preamp_in: float
    R_out: float
    no_eq: bool
    Ccable: float
    tan_delta: float
    tan_delta_coil: float
    Ranagram: float
    Canagram: float
    Rpot_n: float
    Rpot_b: float
    alpha_dielectric_tone: float
    alpha_dielectric_cable: float
    k_mutual: float
    C_mutual: float
    chi_mu: float
    chi_mu_b: float
    omega_mu: float
    k_dist: float
    k_dist_b: float
    omega_dist: float
    k_skin: float
    f_skin: float
    k_skin_b: float
    f_skin_b: float
    vol_pos: float
    tone_pos: float
    blend_pos: float
    pot_taper: str
    Rvol_total: float
    Rtone_total: float
    Rblend_total: float
    Rtop_default: float
    Rbot_default: float
    Rtone_default: float
    Rpot_n_default: float
    Rpot_b_default: float

    def __init__(self):
        self.topology = "single"  # "single", "parallel", "series"
        self.vsat = 0.50
        self.vsat_n = 0.50
        self.vsat_b = 0.50

        # Branch parameters (single or neck)
        self.L = 4.8
        self.L_core = 0.0
        self.R_core = 0.0
        self.Rdc = 9500.0
        self.Reddy = 110000.0
        self.Ccoil = 80e-12

        # Bridge branch (for parallel or series)
        self.L_b = 3.6
        self.L_core_b = 0.0
        self.R_core_b = 0.0
        self.Rdc_b = 7800.0
        self.Reddy_b = 125000.0
        self.Ccoil_b = 70e-12

        # Optional tone / HPF
        self.Ctone = 0.0
        self.Rtone = 0.0
        self.Crick = 0.0

        # Volume pot & treble bleed (disabled by default unless specified in netlist)
        self.Rtop = 10.0
        self.Rbot = 500000.0
        self.Ctb = 0.0
        self.Rtb_par = 0.0
        self.Rtb_ser = 0.0

        # Active preamp buffer & EQ
        self.has_active_buffer = False
        self.preamp_type = "none"  # "sadowsky_2band", "stingray_2band", or "none"
        self.preamp_bands = None
        self.preamp_gain = 1.0
        self.R_preamp_in = 1.0e6
        self.C_preamp_in = 25e-12
        self.R_out = 100.0

        # Transparent zero-EQ mode
        self.no_eq = False

        # Cable & pedalboard load
        self.Ccable = 750e-12
        self.tan_delta = 0.025
        self.tan_delta_coil = 0.025  # Enameled magnet wire dissipation factor
        self.Ranagram = 1.0e6
        self.Canagram = 30e-12

        # Individual pickup volume pot decoupling (e.g. rolled-off neck pot for Jaco growl)
        self.Rpot_n = 0.0
        self.Rpot_b = 0.0

        # Dielectric absorption (Cole-Davidson fractional-order relaxation)
        self.alpha_dielectric_tone = 0.988
        self.alpha_dielectric_cable = 0.994

        # Inter-coil mutual inductive & capacitive coupling for multi-pickup configurations
        self.k_mutual = 0.0
        self.C_mutual = 0.0

        # Complex magnetic permeability dispersion (Jordan after-effect)
        self.chi_mu = 0.0
        self.chi_mu_b = 0.0
        self.omega_mu = 2.0 * math.pi * 1200.0

        # Distributed inter-winding transmission line capacitance
        self.k_dist = 0.0
        self.k_dist_b = 0.0
        self.omega_dist = 2.0 * math.pi * 10000.0

        # Solid core eddy skin-effect fractional dispersion
        self.k_skin = 0.0
        self.f_skin = 3200.0
        self.k_skin_b = 0.0
        self.f_skin_b = 3200.0

        # Potentiometer wiper positions (1.0 = full open/bright baseline, 0.5 = center for blend)
        self.vol_pos = 1.0
        self.tone_pos = 1.0
        self.blend_pos = 0.5
        self.pot_taper = "audio"
        self.Rvol_total = 500000.0
        self.Rtone_total = 250000.0
        self.Rblend_total = 250000.0

        self.Rtop_default = 10.0
        self.Rbot_default = 500000.0
        self.Rtone_default = 0.0
        self.Rpot_n_default = 0.0
        self.Rpot_b_default = 0.0

    def apply_pot_positions(
        self,
        vol_pos: float | None = None,
        tone_pos: float | None = None,
        blend_pos: float | None = None,
        pot_taper: str | None = None,
    ):
        """
        Dynamically positions Volume, Tone, and Blend pot wipers.
        - vol_pos: 0.0 (muted) to 1.0 (full open). Splits volume pot into series Rtop and shunt Rbot.
        - tone_pos: 0.0 (dark / max cap shunting) to 1.0 (open / bright). Scales series Rtone.
        - blend_pos: 0.0 (Neck 100%, Bridge muted) to 0.5 (Center detent 100%/100%) to 1.0 (Neck muted, Bridge 100%).
        - pot_taper: 'audio' (10% CTS), 'audio15' (15% Bourns), or 'linear'. Default is self.pot_taper or 'audio'.
        When wipers are at default positions (vol=1.0, tone=1.0, blend=0.5), preserves exact netlist defaults.
        """
        taper = (
            pot_taper.lower().strip()
            if pot_taper is not None and pot_taper.lower().strip() not in ("", "none")
            else getattr(self, "pot_taper", "audio")
        )
        if taper in ("", "none", None):
            taper = "audio"

        if vol_pos is not None:
            self.vol_pos = float(np.clip(vol_pos, 0.0, 1.0))
            if self.vol_pos >= 0.9999 and hasattr(self, "Rtop_default"):
                self.Rtop = self.Rtop_default
                self.Rbot = self.Rbot_default
            else:
                eff_vol = eval_pot_taper(self.vol_pos, taper)
                r_total = getattr(self, "Rvol_total", self.Rtop + self.Rbot)
                self.Rtop = max(
                    r_total * (1.0 - eff_vol), getattr(self, "Rtop_default", 0.01)
                )
                self.Rbot = max(r_total * eff_vol, 1.0)

        if tone_pos is not None:
            self.tone_pos = float(np.clip(tone_pos, 0.0, 1.0))
            if self.tone_pos >= 0.9999 and hasattr(self, "Rtone_default"):
                self.Rtone = self.Rtone_default
            else:
                eff_tone = eval_pot_taper(self.tone_pos, taper)
                r_tone_tot = getattr(
                    self, "Rtone_total", self.Rtone if self.Rtone > 0.0 else 250000.0
                )
                self.Rtone = max(r_tone_tot * eff_tone, 0.0)

        if blend_pos is not None:
            self.blend_pos = float(np.clip(blend_pos, 0.0, 1.0))
            r_blend = getattr(self, "Rblend_total", 250000.0)
            if abs(self.blend_pos - 0.5) < 1e-4:
                # Center detent: unattenuated 100%/100% (0 dB insertion loss)
                self.Rpot_n = getattr(self, "Rpot_n_default", 0.0)
                self.Rpot_b = getattr(self, "Rpot_b_default", 0.0)
            elif self.blend_pos < 0.5:
                # Turning toward Neck (Neck 100%, Bridge attenuated)
                self.Rpot_n = getattr(self, "Rpot_n_default", 0.0)
                norm_atten = (0.5 - self.blend_pos) / 0.5  # 0.0 at center to 1.0 at full Neck
                eff_atten = eval_pot_taper(norm_atten, taper)
                self.Rpot_b = getattr(self, "Rpot_b_default", 0.0) + r_blend * eff_atten
            else:
                # Turning toward Bridge (Bridge 100%, Neck attenuated)
                self.Rpot_b = getattr(self, "Rpot_b_default", 0.0)
                norm_atten = (self.blend_pos - 0.5) / 0.5  # 0.0 at center to 1.0 at full Bridge
                eff_atten = eval_pot_taper(norm_atten, taper)
                self.Rpot_n = getattr(self, "Rpot_n_default", 0.0) + r_blend * eff_atten

    @classmethod
    def from_dict(cls, cfg: dict[str, Any]) -> CircuitModel:
        """Creates a CircuitModel from a declarative configuration dictionary."""
        def _val(v: Any, default: float = 0.0) -> float:
            if v is None or isinstance(v, bool):
                return default
            if isinstance(v, (int, float)):
                return float(v)
            if isinstance(v, str):
                return parse_spice_val(v)
            return default

        model = cls()
        model.topology = str(cfg.get("topology", "single")).lower()

        # Dynamic saturation limit
        model.vsat = _val(cfg.get("vsat"), 0.50)
        model.vsat_n = _val(cfg.get("vsat_n"), 0.50)
        model.vsat_b = _val(cfg.get("vsat_b"), 0.50)

        # Neck / single pickup branch
        if "neck" in cfg and isinstance(cfg["neck"], dict):
            neck = cfg["neck"]
            model.L = _val(neck.get("L"), model.L)
            model.L_core = _val(neck.get("L_core"), model.L_core)
            model.R_core = _val(neck.get("R_core"), model.R_core)
            model.Rdc = _val(neck.get("Rdc"), model.Rdc)
            model.Reddy = _val(neck.get("Reddy"), model.Reddy)
            model.Ccoil = _val(neck.get("Ccoil"), model.Ccoil)
            if "vsat" in neck:
                model.vsat_n = _val(neck.get("vsat"), model.vsat_n)
        else:
            model.L = _val(cfg.get("L"), model.L)
            model.L_core = _val(cfg.get("L_core"), model.L_core)
            model.R_core = _val(cfg.get("R_core"), model.R_core)
            model.Rdc = _val(cfg.get("Rdc"), model.Rdc)
            model.Reddy = _val(cfg.get("Reddy"), model.Reddy)
            model.Ccoil = _val(cfg.get("Ccoil"), model.Ccoil)

        # Bridge pickup branch
        if "bridge" in cfg and isinstance(cfg["bridge"], dict):
            bridge = cfg["bridge"]
            model.L_b = _val(bridge.get("L"), model.L_b)
            model.L_core_b = _val(bridge.get("L_core"), model.L_core_b)
            model.R_core_b = _val(bridge.get("R_core"), model.R_core_b)
            model.Rdc_b = _val(bridge.get("Rdc"), model.Rdc_b)
            model.Reddy_b = _val(bridge.get("Reddy"), model.Reddy_b)
            model.Ccoil_b = _val(bridge.get("Ccoil"), model.Ccoil_b)
            if "vsat" in bridge:
                model.vsat_b = _val(bridge.get("vsat"), model.vsat_b)
        else:
            model.L_b = _val(cfg.get("L_b"), model.L_b)
            model.L_core_b = _val(cfg.get("L_core_b"), model.L_core_b)
            model.R_core_b = _val(cfg.get("R_core_b"), model.R_core_b)
            model.Rdc_b = _val(cfg.get("Rdc_b"), model.Rdc_b)
            model.Reddy_b = _val(cfg.get("Reddy_b"), model.Reddy_b)
            model.Ccoil_b = _val(cfg.get("Ccoil_b"), model.Ccoil_b)

        # Volume Pot
        if "Rtop" in cfg or "Rbot" in cfg:
            model.Rtop = _val(cfg.get("Rtop"), 10.0)
            model.Rbot = _val(cfg.get("Rbot"), 500000.0)
        elif "Rvol" in cfg:
            model.Rtop = 10.0
            model.Rbot = _val(cfg["Rvol"], 500000.0)
        else:
            model.Rtop = 10.0
            model.Rbot = 500000.0

        # Tone Pot
        model.Rtone = _val(cfg.get("Rtone"), 0.0)
        model.Ctone = _val(cfg.get("Ctone"), 0.0)

        # HPF
        model.Crick = _val(cfg.get("Crick", cfg.get("series_hpf_cap", 0.0)), 0.0)
        if "series_hpf_cap_nf" in cfg:
            model.Crick = _val(cfg["series_hpf_cap_nf"]) * 1e-9

        # Treble bleed
        model.Ctb = _val(cfg.get("Ctb"), 0.0)
        model.Rtb_par = _val(cfg.get("Rtb_par"), 0.0)
        model.Rtb_ser = _val(cfg.get("Rtb_ser"), 0.0)

        # Individual pickup volume pot decoupling
        model.Rpot_n = _val(cfg.get("Rpot_n"), 0.0)
        model.Rpot_b = _val(cfg.get("Rpot_b"), 0.0)

        # Active preamp & buffer
        active = bool(cfg.get("active", False) or cfg.get("has_active_buffer", False))
        preamp_val = cfg.get("preamp") or cfg.get("preamp_type") or "none"
        if preamp_val != "none" or active:
            model.has_active_buffer = True
            model.preamp_type = preamp_val

        model.preamp_gain = _val(cfg.get("preamp_gain"), 1.0)
        model.R_preamp_in = _val(cfg.get("R_preamp_in", cfg.get("Rin")), 1.0e6)
        model.C_preamp_in = _val(cfg.get("C_preamp_in", cfg.get("Cin")), 25e-12)
        model.R_out = _val(cfg.get("R_out", cfg.get("Rout")), 100.0)
        model.no_eq = bool(cfg.get("no_eq", False))
        if cfg.get("preamp_bands"):
            model.preamp_bands = cfg["preamp_bands"]

        # Cable & load
        model.Ccable = _val(cfg.get("Ccable"), 750e-12)
        model.tan_delta = _val(cfg.get("tan_delta"), 0.025)
        model.tan_delta_coil = _val(cfg.get("tan_delta_coil"), 0.025)
        model.Ranagram = _val(cfg.get("Ranagram"), 1.0e6)
        model.Canagram = _val(cfg.get("Canagram"), 30e-12)

        # Coupling & Dielectrics
        if model.topology in ("parallel", "series"):
            model.k_mutual = _val(cfg.get("k_mutual"), 0.05)
            model.C_mutual = _val(cfg.get("C_mutual"), 20e-12)
        else:
            model.k_mutual = _val(cfg.get("k_mutual"), 0.0)
            model.C_mutual = _val(cfg.get("C_mutual"), 0.0)

        model.alpha_dielectric_tone = _val(
            cfg.get("alpha_dielectric_tone", cfg.get("alpha_tone")), 0.988
        )
        model.alpha_dielectric_cable = _val(
            cfg.get("alpha_dielectric_cable", cfg.get("alpha_cable")), 0.994
        )

        # Jordan / skin-effect dispersion
        model.chi_mu = _val(cfg.get("chi_mu"), 0.0)
        model.chi_mu_b = _val(cfg.get("chi_mu_b"), 0.0)
        model.omega_mu = _val(cfg.get("omega_mu"), 2.0 * math.pi * 1200.0)
        model.k_dist = _val(cfg.get("k_dist"), 0.0)
        model.k_dist_b = _val(cfg.get("k_dist_b"), 0.0)
        model.omega_dist = _val(cfg.get("omega_dist"), 2.0 * math.pi * 10000.0)
        model.k_skin = _val(cfg.get("k_skin"), 0.0)
        model.f_skin = _val(cfg.get("f_skin"), 3200.0)
        model.k_skin_b = _val(cfg.get("k_skin_b"), 0.0)
        model.f_skin_b = _val(cfg.get("f_skin_b"), 3200.0)

        # Pot defaults
        model.Rvol_total = model.Rtop + model.Rbot
        model.Rtone_total = model.Rtone if model.Rtone > 0.0 else 250000.0
        model.Rblend_total = _val(cfg.get("Rblend", cfg.get("Rblend_total")), 250000.0)
        taper_cfg = cfg.get("pot_taper")
        model.pot_taper = (
            str(taper_cfg).lower().strip()
            if taper_cfg is not None and str(taper_cfg).lower().strip() not in ("", "none")
            else "audio"
        )
        model.blend_pos = _val(cfg.get("blend_pos"), 0.5)
        model.Rtop_default = model.Rtop
        model.Rbot_default = model.Rbot
        model.Rtone_default = model.Rtone
        model.Rpot_n_default = model.Rpot_n
        model.Rpot_b_default = model.Rpot_b

        has_vol = cfg.get("vol_pos") is not None
        has_tone = cfg.get("tone_pos") is not None
        has_blend = cfg.get("blend_pos") is not None
        if has_vol or has_tone or has_blend:
            model.apply_pot_positions(
                cfg.get("vol_pos"),
                cfg.get("tone_pos"),
                cfg.get("blend_pos"),
                model.pot_taper,
            )

        return model


def load_circuit(source: CircuitModel | dict[str, Any] | BaseModel | str | Path) -> CircuitModel:
    """Loads a CircuitModel from a dict, Pydantic model, file path (.toml), voice ID, or instrument ID."""
    if isinstance(source, CircuitModel):
        return copy.copy(source)
    if isinstance(source, BaseModel):
        dumped = source.model_dump()
        if "circuit" in dumped and isinstance(dumped["circuit"], dict):
            return CircuitModel.from_dict(dumped["circuit"])
        return CircuitModel.from_dict(dumped)
    if isinstance(source, dict):
        if "circuit" in source and isinstance(source["circuit"], (dict, BaseModel)):
            c_val = source["circuit"]
            return CircuitModel.from_dict(c_val.model_dump() if isinstance(c_val, BaseModel) else c_val)
        if "circuit" in source and isinstance(source["circuit"], (str, Path)):
            return load_circuit(source["circuit"])
        return CircuitModel.from_dict(source)

    if isinstance(source, (str, Path)):
        p = Path(source)
        if p.exists() and p.is_file() and p.suffix == ".cir":
            raise ValueError(
                f"Legacy SPICE ASCII netlists (.cir) are deprecated and no longer supported. "
                f"Circuits must be defined as declarative TOML files or tables. "
                f"Attempted to load: {source}"
            )

        if p.exists() and p.is_file() and p.suffix == ".toml":
            import tomllib

            with open(p, "rb") as f:
                data = tomllib.load(f)
            return load_circuit(data)

        # Try relative to REPO_ROOT
        repo_rel = REPO_ROOT / source
        if repo_rel.exists() and repo_rel.is_file():
            return load_circuit(repo_rel)

        if p.suffix == ".cir" or str(source).endswith(".cir"):
            raise ValueError(
                f"Legacy SPICE ASCII netlists (.cir) are deprecated and no longer supported. "
                f"Circuits must be defined as declarative TOML files or tables. "
                f"Attempted to load: {source}"
            )

        # Check voices and instruments registry by string ID
        try:
            from allomorph.config.voices import VOICES

            if str(source) in VOICES:
                return load_circuit(VOICES[str(source)])
        except ImportError:
            pass

        try:
            from allomorph.config.instruments import INSTRUMENTS

            if str(source) in INSTRUMENTS:
                inst = INSTRUMENTS[str(source)]
                default_p = inst.get("default_pickup")
                if default_p and default_p in inst.get("pickups", {}):
                    p = inst["pickups"][default_p]
                    if "circuit" in p:
                        return load_circuit(p["circuit"])
                for p in inst.get("pickups", {}).values():
                    if "circuit" in p:
                        return load_circuit(p["circuit"])
        except ImportError:
            pass

    raise ValueError(f"Could not load circuit from: {source}")


def parse_netlist(source: CircuitModel | dict[str, Any] | BaseModel | str | Path) -> CircuitModel:
    """Parses a netlist or declarative circuit configuration into a CircuitModel."""
    return load_circuit(source)

"""
Allomorph - SPICE Netlist Parser & Circuit Model
Parses Allomorph .cir SPICE netlists into structured CircuitModel instances
with LRU caching, engineering unit suffixes, and pot wiper positioning.
"""

import copy
import functools
import math
import re
from pathlib import Path
from typing import Union, Dict, Any, Optional
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CIRCUITS_DIR = REPO_ROOT / "circuits"


def parse_spice_val(val_str: str) -> float:
    """Parses standard SPICE engineering suffix notation (k, Meg, p, n, u, m, g)."""
    s = val_str.strip()
    if s.lower().endswith("meg"):
        return float(s[:-3]) * 1e6
    suffix_map = {
        "p": 1e-12,
        "n": 1e-9,
        "u": 1e-6,
        "m": 1e-3,
        "k": 1e3,
        "g": 1e9,
    }
    last_char = s[-1].lower()
    if last_char in suffix_map:
        return float(s[:-1]) * suffix_map[last_char]
    return float(s)


MAGNET_PROPERTIES = {
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
MAGNET_PROPERTIES["hybrid"] = MAGNET_PROPERTIES["ceramic_alnico_hybrid"]


class CircuitModel:
    """Represents a parsed RLC guitar circuit digital twin."""

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

        # Potentiometer wiper positions (1.0 = full open/bright baseline)
        self.vol_pos = 1.0
        self.tone_pos = 1.0
        self.Rvol_total = 500000.0
        self.Rtone_total = 250000.0

    def apply_pot_positions(self, vol_pos: float = None, tone_pos: float = None):
        """
        Dynamically positions Volume and Tone pot wipers (0.0 to 1.0, default 1.0 full open).
        At vol_pos < 1.0, splits volume pot into series Rtop and shunt Rbot, loading cable capacitance.
        At tone_pos < 1.0, reduces series resistance in front of tone capacitor (increasing roll-off).
        When wipers are at 1.0, preserves exact netlist defaults.
        """
        if vol_pos is not None:
            self.vol_pos = float(np.clip(vol_pos, 0.0, 1.0))
            if self.vol_pos >= 0.9999 and hasattr(self, "Rtop_default"):
                self.Rtop = self.Rtop_default
                self.Rbot = self.Rbot_default
            else:
                r_total = getattr(self, "Rvol_total", self.Rtop + self.Rbot)
                self.Rtop = max(
                    r_total * (1.0 - self.vol_pos), getattr(self, "Rtop_default", 0.01)
                )
                self.Rbot = max(r_total * self.vol_pos, 1.0)

        if tone_pos is not None:
            self.tone_pos = float(np.clip(tone_pos, 0.0, 1.0))
            if self.tone_pos >= 0.9999 and hasattr(self, "Rtone_default"):
                self.Rtone = self.Rtone_default
            else:
                r_tone_tot = getattr(
                    self, "Rtone_total", self.Rtone if self.Rtone > 0.0 else 250000.0
                )
                self.Rtone = max(r_tone_tot * self.tone_pos, 0.0)

    @classmethod
    def from_dict(cls, cfg: dict) -> "CircuitModel":
        """Creates a CircuitModel from a declarative configuration dictionary."""
        def _val(v, default=0.0):
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
        active = bool(cfg.get("active", cfg.get("has_active_buffer", False)))
        preamp = cfg.get("preamp", cfg.get("preamp_type", "none"))
        if preamp != "none" or active:
            model.has_active_buffer = True
            model.preamp_type = preamp

        model.preamp_gain = _val(cfg.get("preamp_gain"), 1.0)
        model.R_preamp_in = _val(cfg.get("R_preamp_in", cfg.get("Rin")), 1.0e6)
        model.C_preamp_in = _val(cfg.get("C_preamp_in", cfg.get("Cin")), 25e-12)
        model.R_out = _val(cfg.get("R_out", cfg.get("Rout")), 100.0)
        model.no_eq = bool(cfg.get("no_eq", False))
        if "preamp_bands" in cfg:
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
        model.Rtop_default = model.Rtop
        model.Rbot_default = model.Rbot
        model.Rtone_default = model.Rtone

        if "vol_pos" in cfg or "tone_pos" in cfg:
            model.apply_pot_positions(cfg.get("vol_pos"), cfg.get("tone_pos"))

        return model


@functools.lru_cache(maxsize=128)
def _parse_netlist_cached(cir_path_str: str) -> CircuitModel:
    """Internal cached parser for an Allomorph .cir netlist."""
    cir_path = Path(cir_path_str)
    model = CircuitModel()
    with open(cir_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    has_neck = False
    has_bridge = False
    is_series = False

    # Check filename for known active configurations
    stem = cir_path.stem.lower()
    if "01_modern_jazz" in stem:
        model.has_active_buffer = True
        model.preamp_type = "sadowsky_2band"
    elif "stingray" in stem:
        model.has_active_buffer = True
        model.preamp_type = "stingray_2band"
    elif "16_active_character" in stem or "active_character" in stem:
        model.has_active_buffer = True
        model.preamp_type = "none"
    elif "15_source_direct" in stem or "source_direct" in stem:
        model.no_eq = True

    for line in lines:
        line_clean = line.strip()
        if not line_clean:
            continue

        line_lower = line_clean.lower()
        if "mode: no_eq" in line_lower or "no_eq" in line_lower:
            model.no_eq = True
        elif "sadowsky_2band" in line_lower or "sadowsky" in line_lower:
            model.has_active_buffer = True
            model.preamp_type = "sadowsky_2band"
        elif "stingray_2band" in line_lower:
            model.has_active_buffer = True
            model.preamp_type = "stingray_2band"
        elif "preamp voicing: none" in line_lower or "flat buffer" in line_lower:
            model.has_active_buffer = True
            model.preamp_type = "none"

        if line_clean.startswith("*") or line_clean.startswith("."):
            continue

        tokens = line_clean.split()
        tag = tokens[0].upper()

        # Behavioral soft-knee compliance
        if tag.startswith("B_COMP"):
            match = re.search(r"V\s*=\s*([0-9\.]+)\s*\*\s*tanh", line_clean, re.IGNORECASE)
            if match:
                v = float(match.group(1))
                if tag == "B_COMP_N":
                    model.vsat_n = v
                elif tag == "B_COMP_B":
                    model.vsat_b = v
                else:
                    model.vsat = v

        # Inductors
        elif tag in ["L_COIL", "L_NECK"]:
            model.L = parse_spice_val(tokens[3])
            if tag == "L_NECK":
                has_neck = True
                if tokens[2] == "node_mid":
                    is_series = True
        elif tag == "L_BRIDGE":
            model.L_b = parse_spice_val(tokens[3])
            has_bridge = True
            if tokens[1] in ["node_mid", "in_dyn_b"] and tokens[2] in ["node1_b"]:
                pass

        # Core Eddy Diffusion
        elif tag in ["L_CORE", "L_CORE_N"]:
            model.L_core = parse_spice_val(tokens[3])
        elif tag == "L_CORE_B":
            model.L_core_b = parse_spice_val(tokens[3])
        elif tag in ["R_CORE", "R_CORE_N"]:
            model.R_core = parse_spice_val(tokens[3])
        elif tag == "R_CORE_B":
            model.R_core_b = parse_spice_val(tokens[3])

        # DC Resistance
        elif tag in ["R_DC", "R_DC_N"]:
            model.Rdc = parse_spice_val(tokens[3])
        elif tag == "R_DC_B":
            model.Rdc_b = parse_spice_val(tokens[3])

        # Eddy Resistance
        elif tag in ["R_EDDY", "R_EDDY_N"]:
            model.Reddy = parse_spice_val(tokens[3])
        elif tag == "R_EDDY_B":
            model.Reddy_b = parse_spice_val(tokens[3])

        # Coil Self-Capacitance
        elif tag in ["C_COIL", "C_COIL_N"]:
            model.Ccoil = parse_spice_val(tokens[3])
        elif tag == "C_COIL_B":
            model.Ccoil_b = parse_spice_val(tokens[3])
            if tokens[2] == "node_mid":
                is_series = True

        # Tone / HPF
        elif tag == "C_TONE":
            model.Ctone = parse_spice_val(tokens[3])
        elif tag in ["R_TONE", "R_TONE_ESR"]:
            model.Rtone = parse_spice_val(tokens[3])
        elif tag == "C_RICK":
            model.Crick = parse_spice_val(tokens[3])

        # Volume Pot
        elif tag == "R_POT_TOP":
            model.Rtop = parse_spice_val(tokens[3])
        elif tag == "R_POT_BOT":
            model.Rbot = parse_spice_val(tokens[3])
        elif tag in ["R_POT_N", "R_POT_NECK"]:
            model.Rpot_n = parse_spice_val(tokens[3])
        elif tag in ["R_POT_B", "R_POT_BRIDGE"]:
            model.Rpot_b = parse_spice_val(tokens[3])

        # Treble Bleed
        elif tag == "C_TB":
            model.Ctb = parse_spice_val(tokens[3])
        elif tag == "R_TB_PAR":
            model.Rtb_par = parse_spice_val(tokens[3])
        elif tag == "R_TB_SER":
            model.Rtb_ser = parse_spice_val(tokens[3])

        # Active Preamp Buffer
        elif tag in ["E_PREAMP", "E_BUF"]:
            model.has_active_buffer = True
            if len(tokens) > 5:
                model.preamp_gain = parse_spice_val(tokens[5])
        elif tag == "R_PREAMP_IN":
            model.R_preamp_in = parse_spice_val(tokens[3])
            model.has_active_buffer = True
        elif tag == "C_PREAMP_IN":
            model.C_preamp_in = parse_spice_val(tokens[3])
            model.has_active_buffer = True
        elif tag == "R_OUT":
            model.R_out = parse_spice_val(tokens[3])
            model.has_active_buffer = True

        # Cable
        elif tag == "C_CABLE":
            model.Ccable = parse_spice_val(tokens[3])

        # Anagram
        elif tag == "R_ANAGRAM":
            model.Ranagram = parse_spice_val(tokens[3])
        elif tag == "C_ANAGRAM":
            model.Canagram = parse_spice_val(tokens[3])

        # Mutual coupling directives
        elif tag in ["K_COUPLE", "K_MUTUAL", "K1", "K_COIL"]:
            model.k_mutual = (
                parse_spice_val(tokens[3]) if len(tokens) > 3 else parse_spice_val(tokens[1])
            )
        elif tag in ["C_MUTUAL", "C_M"]:
            model.C_mutual = (
                parse_spice_val(tokens[3]) if len(tokens) > 3 else parse_spice_val(tokens[1])
            )

        # Dielectric absorption overrides
        elif tag in ["ALPHA_TONE", "ALPHA_DIEL_TONE"]:
            model.alpha_dielectric_tone = float(tokens[1])
        elif tag in ["ALPHA_CABLE", "ALPHA_DIEL_CABLE"]:
            model.alpha_dielectric_cable = float(tokens[1])

        # Solid core eddy skin-effect directives
        elif tag in ["K_SKIN", "K_SKIN_N"]:
            model.k_skin = (
                parse_spice_val(tokens[1]) if len(tokens) > 1 else parse_spice_val(tokens[3])
            )
        elif tag == "K_SKIN_B":
            model.k_skin_b = (
                parse_spice_val(tokens[1]) if len(tokens) > 1 else parse_spice_val(tokens[3])
            )
        elif tag in ["F_SKIN", "F_SKIN_N"]:
            model.f_skin = (
                parse_spice_val(tokens[1]) if len(tokens) > 1 else parse_spice_val(tokens[3])
            )
        elif tag == "F_SKIN_B":
            model.f_skin_b = (
                parse_spice_val(tokens[1]) if len(tokens) > 1 else parse_spice_val(tokens[3])
            )

    if has_neck and has_bridge:
        model.topology = "series" if is_series else "parallel"
        if model.k_mutual <= 0.0:
            model.k_mutual = 0.05
        if model.C_mutual <= 0.0:
            model.C_mutual = 20e-12
    else:
        model.topology = "single"

    model.Rvol_total = model.Rtop + model.Rbot
    model.Rtone_total = model.Rtone if model.Rtone > 0.0 else 250000.0
    model.Rtop_default = model.Rtop
    model.Rbot_default = model.Rbot
    model.Rtone_default = model.Rtone

    return model


def load_circuit(source: Union[CircuitModel, dict, str, Path]) -> CircuitModel:
    """Loads a CircuitModel from a dict, file path (.toml or .cir), voice ID, or instrument ID."""
    if isinstance(source, CircuitModel):
        return copy.copy(source)
    if isinstance(source, dict):
        if "circuit" in source and isinstance(source["circuit"], dict):
            return CircuitModel.from_dict(source["circuit"])
        if "circuit" in source and isinstance(source["circuit"], (str, Path)):
            return load_circuit(source["circuit"])
        return CircuitModel.from_dict(source)

    if isinstance(source, (str, Path)):
        p = Path(source)
        if p.exists() and p.is_file():
            if p.suffix == ".toml":
                import tomllib

                with open(p, "rb") as f:
                    data = tomllib.load(f)
                return load_circuit(data)
            elif p.suffix == ".cir":
                return copy.copy(_parse_netlist_cached(str(p.resolve())))

        # Try relative to REPO_ROOT
        repo_rel = REPO_ROOT / source
        if repo_rel.exists() and repo_rel.is_file():
            return load_circuit(repo_rel)

        # Check voices and instruments registry by string or stem
        stem = Path(source).stem
        src_map = {
            "source_standard_p": ("34in_standard_p", "split_p"),
            "source_standard_jazz_neck": ("34in_standard_jazz", "neck"),
            "source_standard_jazz_bridge": ("34in_standard_jazz", "bridge"),
            "source_standard_jazz_pair": ("34in_standard_jazz", "pair_parallel"),
            "source_standard_pj_pair": ("34in_standard_pj", "pair_parallel"),
            "source_active_stingray": ("34in_active_stingray", "mm_parallel"),
            "source_dingwall_fd3n": ("37in_multiscale_dingwall", "bridge"),
            "source_dingwall_sp1_bridge": ("34in_dingwall_sp1", "bridge"),
            "source_standard_mustang": ("30in_mustang_pj", "p"),
        }

        try:
            from allomorph.config.voices import VOICES

            if str(source) in VOICES:
                return load_circuit(VOICES[str(source)])
            if stem in VOICES:
                return load_circuit(VOICES[stem])
        except ImportError:
            pass

        try:
            from allomorph.config.instruments import INSTRUMENTS

            if stem in src_map:
                inst_id, p_id = src_map[stem]
                if inst_id in INSTRUMENTS and p_id in INSTRUMENTS[inst_id].get("pickups", {}):
                    p_data = INSTRUMENTS[inst_id]["pickups"][p_id]
                    if "circuit" in p_data:
                        return load_circuit(p_data["circuit"])

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


def parse_netlist(source: Union[CircuitModel, dict, str, Path]) -> CircuitModel:
    """Parses a netlist or declarative circuit configuration into a CircuitModel."""
    return load_circuit(source)

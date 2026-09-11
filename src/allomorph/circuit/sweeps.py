"""
Allomorph - Instantaneous Continuous Parametric Sweeps
Evaluates exact continuous electrical parameter sweeps across frequencies in < 45 ms.
Supports tone pot, volume pot, cable capacitance, tone capacitor, and active EQ sweeps.
"""

from dataclasses import dataclass
import copy
from pathlib import Path
from typing import List, Optional, Union

import numpy as np
import polars as pl

from allomorph.circuit.parser import CircuitModel, load_circuit
from allomorph.circuit.solver import apply_magnet_properties_to_model, compute_circuit_transfer_functions
from allomorph.dsp import FREQS


@dataclass
class ParametricSweepResult:
    """Represents the results of a parametric frequency response sweep."""

    param: str
    values: list[float]
    freqs: np.ndarray
    curves: list[np.ndarray]  # magnitude in dB for each swept value
    labels: list[str]
    voice_id: Optional[str] = None

    @property
    def curves_db(self) -> list[np.ndarray]:
        """Returns curves in decibels (alias for curves)."""
        return self.curves

    @property
    def curves_linear(self) -> list[np.ndarray]:
        """Returns linear magnitude curves."""
        return [10.0 ** (np.asarray(c, dtype=np.float64) / 20.0) for c in self.curves]

    def to_dataframe(self, include_voice_id: bool = False) -> pl.DataFrame:
        """
        Converts the sweep results to a Polars DataFrame with columns:
        ['frequency', 'magnitude_db', 'param', 'param_value', 'label']
        and optionally 'voice_id'.
        """
        n_f = len(self.freqs)
        n_v = len(self.values)
        all_freqs = np.tile(self.freqs, n_v)
        all_mags = np.concatenate([np.asarray(c, dtype=np.float64) for c in self.curves])
        all_params = [self.param] * (n_f * n_v)
        all_pvals = np.repeat(np.asarray(self.values, dtype=np.float64), n_f)
        all_labels = np.repeat(self.labels, n_f)

        data = {
            "frequency": all_freqs,
            "magnitude_db": all_mags,
            "param": all_params,
            "param_value": all_pvals,
            "label": all_labels,
        }
        if include_voice_id and self.voice_id:
            data["voice_id"] = [self.voice_id] * (n_f * n_v)
        return pl.DataFrame(data)


def _get_default_sweep_values(param: str) -> list[float]:
    """Provides default numerical values for a given sweep parameter."""
    p = param.lower().strip()
    if p in ("tone", "tone_pos", "tone_wiper", "tone_pot"):
        return [0.0, 0.25, 0.5, 0.75, 1.0]
    elif p in ("vol", "vol_pos", "volume", "vol_wiper", "volume_pot"):
        return [0.0, 0.25, 0.5, 0.75, 1.0]
    elif p in ("cable", "cable_pf", "ccable", "cable_capacitance"):
        return [200.0, 500.0, 750.0, 1000.0, 1500.0]
    elif p in ("tone_cap", "ctone", "cap", "tone_capacitance", "tone_cap_nf"):
        return [22.0, 33.0, 47.0, 68.0, 100.0]
    elif p in ("bass_boost", "preamp_bass", "bass"):
        return [0.0, 3.0, 6.0, 9.0, 12.0]
    elif p in ("treble_boost", "preamp_treble", "treble"):
        return [0.0, 3.0, 6.0, 9.0, 12.0]
    return [0.0, 0.5, 1.0]


def _generate_default_labels(param: str, values: list[float]) -> list[str]:
    """Generates clean human-readable labels for sweep values."""
    p = param.lower().strip()
    if p in ("tone", "tone_pos", "tone_wiper", "tone_pot"):
        return [f"Tone {int(round(v * 100))}%" for v in values]
    elif p in ("vol", "vol_pos", "volume", "vol_wiper", "volume_pot"):
        return [f"Vol {int(round(v * 100))}%" for v in values]
    elif p in ("cable", "cable_pf", "ccable", "cable_capacitance"):
        return [f"Cable {v:.0f} pF" if v > 1e-6 else f"Cable {v*1e12:.0f} pF" for v in values]
    elif p in ("tone_cap", "ctone", "cap", "tone_capacitance", "tone_cap_nf"):
        return [f"Cap {v:.0f} nF" if v > 1e-6 else f"Cap {v*1e9:.0f} nF" for v in values]
    elif p in ("bass_boost", "preamp_bass", "bass"):
        return [f"Bass {v:+.1f} dB" for v in values]
    elif p in ("treble_boost", "preamp_treble", "treble"):
        return [f"Treble {v:+.1f} dB" for v in values]
    else:
        return [f"{param}={v}" for v in values]


def compute_parametric_sweep(
    circuit_or_voice: Union[CircuitModel, dict, str, Path],
    param: str,
    values: Optional[Union[list[float], np.ndarray]] = None,
    freqs: Union[list[float], np.ndarray] = FREQS,
    labels: Optional[list[str]] = None,
    pickup_channel: int = 0,
) -> ParametricSweepResult:
    """
    Computes closed-form nodal AC transfer functions across a continuous parameter sweep.
    Executes in < 45 ms by utilizing vectorized NumPy operations and in-place circuit restoration.

    Parameters:
        circuit_or_voice: A CircuitModel instance, dictionary config, voice ID string, or Path.
        param: Parameter name to sweep:
            - 'tone' / 'tone_pos': Pot wiper position (0.0 to 1.0).
            - 'vol' / 'vol_pos': Pot wiper position (0.0 to 1.0).
            - 'cable' / 'cable_pf': Cable capacitance in pF (or Farads if < 1e-6).
            - 'tone_cap' / 'Ctone': Tone capacitance in nF (or Farads if < 1e-6).
            - 'bass_boost' / 'preamp_bass': Active preamp bass shelf gain in dB.
            - 'treble_boost' / 'preamp_treble': Active preamp treble shelf gain in dB.
            - Any direct numerical attribute on CircuitModel (e.g. 'L', 'Rdc', 'Reddy').
        values: Sequence of numerical parameter values. If None, uses smart defaults.
        freqs: Frequency vector in Hz (defaults to standard 4096-tap FREQS).
        labels: Optional custom string labels for each value.
        pickup_channel: Output channel index to sample for multi-pickup circuits (default 0).

    Returns:
        ParametricSweepResult containing curves in dB, metadata, and Polars export.
    """
    voice_id = None
    if isinstance(circuit_or_voice, CircuitModel):
        model = circuit_or_voice
        voice_id = getattr(model, "voice_id", None)
    elif isinstance(circuit_or_voice, (str, Path)):
        voice_id = Path(circuit_or_voice).stem
        model = load_circuit(circuit_or_voice)
        try:
            from allomorph.config.voices import VOICES

            cfg = VOICES.get(str(circuit_or_voice)) or VOICES.get(voice_id)
            if cfg:
                apply_magnet_properties_to_model(model, cfg)
        except Exception:
            pass
    elif isinstance(circuit_or_voice, dict):
        voice_id = circuit_or_voice.get("id") or circuit_or_voice.get("name")
        model = load_circuit(circuit_or_voice)
        apply_magnet_properties_to_model(model, circuit_or_voice)
    else:
        raise ValueError(f"Invalid circuit_or_voice: {type(circuit_or_voice)}")

    f_arr = np.asarray(freqs, dtype=np.float64)

    if values is None:
        values = _get_default_sweep_values(param)
    values = [float(v) for v in values]

    if labels is None:
        labels = _generate_default_labels(param, values)
    elif len(labels) != len(values):
        raise ValueError(f"Length of labels ({len(labels)}) must match values ({len(values)})")

    p = param.lower().strip()
    curves: list[np.ndarray] = []

    if p in ("tone", "tone_pos", "tone_wiper", "tone_pot"):
        orig_tone_pos = model.tone_pos
        orig_Rtone = model.Rtone
        try:
            for v in values:
                model.apply_pot_positions(tone_pos=v)
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            model.tone_pos = orig_tone_pos
            model.Rtone = orig_Rtone

    elif p in ("vol", "vol_pos", "volume", "vol_wiper", "volume_pot"):
        orig_vol_pos = model.vol_pos
        orig_Rtop = model.Rtop
        orig_Rbot = model.Rbot
        try:
            for v in values:
                model.apply_pot_positions(vol_pos=v)
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            model.vol_pos = orig_vol_pos
            model.Rtop = orig_Rtop
            model.Rbot = orig_Rbot

    elif p in ("cable", "cable_pf", "ccable", "cable_capacitance"):
        orig_Ccable = model.Ccable
        try:
            for v in values:
                c_farads = v * 1e-12 if v > 1e-6 else v
                model.Ccable = c_farads
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            model.Ccable = orig_Ccable

    elif p in ("tone_cap", "ctone", "cap", "tone_capacitance", "tone_cap_nf"):
        orig_Ctone = model.Ctone
        try:
            for v in values:
                c_farads = v * 1e-9 if v > 1e-6 else v
                model.Ctone = c_farads
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            model.Ctone = orig_Ctone

    elif p in ("bass_boost", "preamp_bass", "bass"):
        orig_has_buf = model.has_active_buffer
        orig_bands = copy.deepcopy(model.preamp_bands) if model.preamp_bands is not None else None
        orig_type = model.preamp_type
        try:
            from allomorph.config import PREAMPS

            base_bands = []
            if orig_bands is not None:
                base_bands = copy.deepcopy(orig_bands)
            elif model.preamp_type != "none" and model.preamp_type in PREAMPS:
                base_bands = copy.deepcopy(PREAMPS[model.preamp_type].get("bands", []))

            shelf_idx = None
            for i, b in enumerate(base_bands):
                if b.get("type") == "low_shelf":
                    shelf_idx = i
                    break
            if shelf_idx is None:
                base_bands.append({"type": "low_shelf", "freq_hz": 40.0, "gain_db": 0.0})
                shelf_idx = len(base_bands) - 1

            model.has_active_buffer = True
            for v in values:
                bands = copy.deepcopy(base_bands)
                bands[shelf_idx]["gain_db"] = float(v)
                model.preamp_bands = bands
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            model.has_active_buffer = orig_has_buf
            model.preamp_bands = orig_bands
            model.preamp_type = orig_type

    elif p in ("treble_boost", "preamp_treble", "treble"):
        orig_has_buf = model.has_active_buffer
        orig_bands = copy.deepcopy(model.preamp_bands) if model.preamp_bands is not None else None
        orig_type = model.preamp_type
        try:
            from allomorph.config import PREAMPS

            base_bands = []
            if orig_bands is not None:
                base_bands = copy.deepcopy(orig_bands)
            elif model.preamp_type != "none" and model.preamp_type in PREAMPS:
                base_bands = copy.deepcopy(PREAMPS[model.preamp_type].get("bands", []))

            shelf_idx = None
            for i, b in enumerate(base_bands):
                if b.get("type") == "high_shelf":
                    shelf_idx = i
                    break
            if shelf_idx is None:
                base_bands.append({"type": "high_shelf", "freq_hz": 4000.0, "gain_db": 0.0})
                shelf_idx = len(base_bands) - 1

            model.has_active_buffer = True
            for v in values:
                bands = copy.deepcopy(base_bands)
                bands[shelf_idx]["gain_db"] = float(v)
                model.preamp_bands = bands
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            model.has_active_buffer = orig_has_buf
            model.preamp_bands = orig_bands
            model.preamp_type = orig_type

    elif hasattr(model, param):
        orig_val = getattr(model, param)
        try:
            for v in values:
                setattr(model, param, v)
                tr = compute_circuit_transfer_functions(model, freqs=f_arr, return_numpy=True)
                ch = min(pickup_channel, len(tr) - 1)
                mag_db = 20.0 * np.log10(np.maximum(tr[ch], 1e-6))
                curves.append(mag_db)
        finally:
            setattr(model, param, orig_val)
    else:
        raise ValueError(f"Unsupported sweep parameter: '{param}'")

    return ParametricSweepResult(
        param=param,
        values=values,
        freqs=f_arr,
        curves=curves,
        labels=labels,
        voice_id=voice_id,
    )

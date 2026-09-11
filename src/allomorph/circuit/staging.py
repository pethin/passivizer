"""
Allomorph - Architecture C Two-Stage Pipeline & Simulation CLI
Coordinates two-stage deconvolution (Canonical Intermediate sweep generation,
frontend IR export for all playable instruments, backend universal target sweeps),
and provides the allomorph-sim CLI binary entrypoint.
"""

import argparse
import math
import os
import wave
from pathlib import Path
from typing import Any

import numpy as np

from allomorph.circuit.parser import load_circuit
from allomorph.circuit.schema import SimulationConfig
from allomorph.circuit.simulation import (
    CANONICAL_SWEEP_PATH,
    FRONTENDS_DIR,
    INTERMEDIATE_TARGET_PEAK_DBFS,
    INTERMEDIATE_TARGET_RMS_DBFS,
    TARGETS_DIR,
    _simulate_voice_task,
    find_default_input_audio,
    simulate_voice,
)
from allomorph.circuit.solver import compute_differential_circuit_transfer_functions
from allomorph.config.geometry import resolve_pickup_coils
from allomorph.config.instruments import load_all_instruments, load_instrument
from allomorph.config.scales import REPO_ROOT, resolve_scale_range
from allomorph.config.schema import CoilConfig
from allomorph.config.voices import VOICES
from allomorph.dsp import (
    FREQS,
    synthesize_minimum_phase_fir,
    write_wav_24bit,
)
from allomorph.naming import (
    resolve_instruments,
    resolve_voices,
)
from allomorph.physics import (
    numpy_pickup_acoustic_response,
    resolve_pickup_electrical_deconvolution_np,
)


def generate_canonical_sweep(input_wav: Path | None = None, output_wav: Path | None = None) -> Path:
    """
    Generates the calibrated Canonical Intermediate baseline audio sweep.
    Takes raw T3K sweep audio, applies Canonical Intermediate aperture (single coil at 93.5mm datum)
    and flat active buffer, and normalizes output to -1.5 dBFS True Peak / -16.5 dBFS RMS nominal.
    """
    if not input_wav:
        input_wav = find_default_input_audio()
    if not input_wav or not Path(input_wav).exists():
        raise FileNotFoundError("Raw calibration audio (T3K-sweep-v3.wav) not found in repo root.")

    output_wav = Path(output_wav) if output_wav else CANONICAL_SWEEP_PATH
    output_wav.parent.mkdir(parents=True, exist_ok=True)

    with wave.open(str(input_wav), "rb") as wf:
        sr = wf.getframerate()
        sw = wf.getsampwidth()
        n_frames = wf.getnframes()
        raw = wf.readframes(n_frames)

    if sw == 3:
        raw_padded = bytearray()
        for i in range(0, len(raw), 3):
            raw_padded.extend(raw[i : i + 3])
            raw_padded.append(0 if raw[i + 2] < 128 else 255)
        audio = np.frombuffer(raw_padded, dtype=np.int32).astype(np.float64) / 8388607.0
    elif sw == 2:
        audio = np.frombuffer(raw, dtype=np.int16).astype(np.float64) / 32767.0
    else:
        audio = np.frombuffer(raw, dtype=np.float32).astype(np.float64)

    f = np.asarray(FREQS, dtype=np.float64)
    can_coils = [
        CoilConfig(
            strings=["all"], position_from_bridge_m=0.0935, aperture_width_in=0.75, weight=1.0
        )
    ]
    h_can_ac = numpy_pickup_acoustic_response(f, can_coils, scale_length_m=(0.8636, 0.8636))
    can_fir = synthesize_minimum_phase_fir(h_can_ac, num_taps=2048)

    filtered = np.convolve(audio, can_fir, mode="same")

    raw_peak = float(np.max(np.abs(filtered)))
    raw_rms = float(np.sqrt(np.mean(filtered**2)))

    peak_gain = (10.0 ** (INTERMEDIATE_TARGET_PEAK_DBFS / 20.0)) / max(raw_peak, 1e-9)
    rms_gain = (10.0 ** (INTERMEDIATE_TARGET_RMS_DBFS / 20.0)) / max(raw_rms, 1e-9)
    gain = min(peak_gain, rms_gain)

    calibrated = np.clip(filtered * gain, -0.999, 0.999).astype(np.float32)

    write_wav_24bit(str(output_wav), calibrated, sr)
    final_peak_db = 20.0 * math.log10(max(float(np.max(np.abs(calibrated))), 1e-9))
    final_rms_db = 20.0 * math.log10(max(float(np.sqrt(np.mean(calibrated**2))), 1e-9))
    print(
        f"[Canonical Sweep] Generated {output_wav.name}: Peak = {final_peak_db:.2f} dBFS, RMS = {final_rms_db:.2f} dBFS"
    )
    return output_wav


def export_frontend_ir(
    inst_id: str, pickup_key: str, out_path: Path | None = None, num_taps: int = 2048
) -> Path:
    """
    Synthesizes a 2048-tap minimum-phase deconvolution IR transforming a source pickup into the Canonical Intermediate.
    Enforces strictly positive initial polarity to ensure zero phase cancellation when blended in parallel.
    """
    inst = load_instrument(inst_id)
    pickups = inst.pickups
    if pickup_key not in pickups:
        raise KeyError(f"Pickup key '{pickup_key}' not found in instrument '{inst_id}'")
    pickup = pickups[pickup_key]

    f = np.asarray(FREQS, dtype=np.float64)
    scale_range = resolve_scale_range(inst)
    coils = resolve_pickup_coils(pickup, inst)

    # 1. Source acoustic response
    h_src_ac = numpy_pickup_acoustic_response(f, coils, scale_length_m=scale_range)

    # 2. Canonical acoustic response (34in standard scale, 93.5mm datum, 0.75in slit)
    can_coils = [
        CoilConfig(
            strings=["all"], position_from_bridge_m=0.0935, aperture_width_in=0.75, weight=1.0
        )
    ]
    h_can_ac = numpy_pickup_acoustic_response(f, can_coils, scale_length_m=(0.8636, 0.8636))

    h_aperture_deconv = (h_can_ac * h_src_ac) / (h_src_ac**2 + 0.01)

    # 3. Circuit deconvolution
    p_circ = pickup.circuit
    can_voice = VOICES.get("00_canonical_intermediate")
    can_circ = can_voice.circuit if can_voice is not None else None
    if p_circ and can_circ:
        can_model = load_circuit(can_circ)
        src_model = load_circuit(p_circ)
        diff_curves = compute_differential_circuit_transfer_functions(can_model, src_model, freqs=f)
        h_circuit_deconv = np.asarray(diff_curves[0], dtype=np.float64)
    elif inst.electronics == "passive":
        raise ValueError(
            f"Passive instrument '{inst_id}' pickup '{pickup_key}' does not define a '[pickups.{pickup_key}.circuit]' "
            f"configuration. Passive source pickups require an explicit circuit model for differential deconvolution."
        )
    else:
        h_circuit_deconv = resolve_pickup_electrical_deconvolution_np(
            f, pickup, inst, q_target=0.707
        )

    h_total = h_aperture_deconv * h_circuit_deconv

    fir = synthesize_minimum_phase_fir(h_total, num_taps=num_taps)
    fir = np.asarray(fir, dtype=np.float32)

    # Polarity check: enforce positive polarity
    if np.sum(fir[:16]) < 0:
        fir = -fir

    if out_path is None:
        inst_dir = FRONTENDS_DIR / inst_id
        inst_dir.mkdir(parents=True, exist_ok=True)
        # Avoid repetitive token if inst_id already ends with pickup prefix (e.g. 30in_emg_mmtw + mmtw_dual)
        if inst_id.endswith("mmtw") and pickup_key.startswith("mmtw_"):
            p_name = pickup_key[len("mmtw_") :]
            out_name = f"{inst_id}_{p_name}.wav"
        else:
            out_name = f"{inst_id}_{pickup_key}.wav"
        out_path = inst_dir / out_name

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_wav_24bit(str(out_path), fir, 48000)

    # If single pickup, also generate convenience alias <inst_id>.wav
    if len(pickups) == 1:
        alias_path = out_path.parent / f"{inst_id}.wav"
        if alias_path != out_path:
            write_wav_24bit(str(alias_path), fir, 48000)

    return out_path


def export_all_frontend_irs(output_dir: Path | None = None):
    """
    Exports all 32 native frontend deconvolution IRs grouped by instrument subdirectories.
    """
    out_dir = Path(output_dir) if output_dir else FRONTENDS_DIR
    all_insts = load_all_instruments()
    exported = []
    for inst_id, inst in sorted(all_insts.items()):
        if inst_id == "canonical_intermediate":
            continue
        pickups = inst.pickups
        for p_key in sorted(pickups.keys()):
            p_file = export_frontend_ir(inst_id, p_key)
            exported.append(p_file)
            print(f" [Frontend IR] Exported {p_file.relative_to(REPO_ROOT)}")
    print(f"Successfully exported {len(exported)} frontend IRs to {out_dir}")
    return exported


def simulate_backend_targets(tier: str = "standard", voice_id: str | None = None):
    """
    Simulates target voice audio sweeps using the Canonical Intermediate baseline as input.
    Tiers:
      - 'clean': 0% saturation / maximum headroom (bypass_saturation=True)
      - 'standard': standard dynamic pickup give (100% nominal saturation)
      - 'hotrod': overwound drive pre-conditioner (175% saturation, reduced vsat)
    """
    tier_map = {
        "clean": "01_clean_headroom",
        "standard": "02_standard_dynamic",
        "std": "02_standard_dynamic",
        "dynamic": "02_standard_dynamic",
        "hotrod": "03_hot_rod_drive",
        "hot_rod": "03_hot_rod_drive",
    }
    if tier == "all":
        tiers_to_run = ["clean", "standard", "hotrod"]
    else:
        if tier not in tier_map:
            raise ValueError(
                f"Unknown tier '{tier}'. Choose from clean, standard, std, hotrod, all."
            )
        tiers_to_run = [tier]

    if not CANONICAL_SWEEP_PATH.exists():
        generate_canonical_sweep()

    voices_to_run = (
        [voice_id]
        if voice_id and voice_id != "all"
        else [vid for vid in sorted(VOICES.keys()) if vid != "00_canonical_intermediate"]
    )

    for t in tiers_to_run:
        folder_name = tier_map[t]
        target_out_dir = TARGETS_DIR / folder_name
        target_out_dir.mkdir(parents=True, exist_ok=True)

        for vid in voices_to_run:
            out_file = target_out_dir / f"out_{vid}.wav"
            print(f"[{t.upper()}] Simulating {vid} -> {out_file.name}...")

            vcfg = VOICES.get(vid)
            v_alpha = vcfg.alpha if vcfg is not None else 0.25

            if t == "clean":
                sim_alpha = 0.0
            elif t == "hotrod":
                sim_alpha = min(1.0, v_alpha * 1.75)
            else:
                sim_alpha = v_alpha

            simulate_voice(
                voice_id=vid,
                input_wav=CANONICAL_SWEEP_PATH,
                output_wav=out_file,
                instrument="canonical_intermediate",
                alpha=sim_alpha,
                normalize="none",  # T3K sweep integrity
            )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Allomorph Native Virtual Analog Circuit Simulator."
    )
    parser.add_argument(
        "--voice",
        "-v",
        default="all",
        help="Target voice to simulate (voice ID, comma-separated list, or 'all'; default: 'all')",
    )
    parser.add_argument(
        "--instrument",
        "-i",
        default="all",
        help="Source instrument configuration (ID, comma-separated list, 'all', 30in, 32in, or path to .toml; default: 'all')",
    )
    parser.add_argument(
        "--input", help="Input WAV path (defaults to auto-detecting T3K-sweep-v3.wav)"
    )
    parser.add_argument(
        "--out", help="Output WAV path (default: audio/<instrument>/out_<voice>.wav)"
    )
    parser.add_argument(
        "--prefiltered",
        action="store_true",
        help="Input is already pre-filtered through acoustic aperture",
    )
    parser.add_argument(
        "--normalize",
        choices=["auto", "rms", "peak", "none"],
        default="auto",
        help="Output level normalization mode based on input sweep dBFS (default: auto = match input sweep RMS with true-peak safety).",
    )
    parser.add_argument(
        "--target-dbfs",
        type=float,
        default=None,
        help="Explicit target level in dBFS (e.g. -22.0). If omitted, automatically derived from the input sweep.",
    )
    parser.add_argument(
        "--oversample",
        type=int,
        choices=[1, 2, 4],
        default=2,
        help="Anti-aliased oversampling factor for saturation (default: 2 = 96 kHz internal processing)",
    )
    parser.add_argument(
        "--no-displacement-weighting",
        action="store_true",
        help="Disable displacement-domain excursion weighting before saturation",
    )
    parser.add_argument(
        "--no-magnet-drag",
        action="store_true",
        help="Disable dynamic magnet drag attack braking on extreme transients",
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=None,
        help="Explicit saturation asymmetry factor alpha (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--alpha3",
        type=float,
        default=None,
        help="Explicit cubic dipole proximity factor alpha3 (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--k-sag",
        type=float,
        default=None,
        help="Explicit dynamic Lenz-law core flux sag factor k_sag (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--k-eddy",
        type=float,
        default=None,
        help="Explicit dynamic eddy-current core de-Qing factor k_eddy (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--kappa-orbit",
        type=float,
        default=None,
        help="Explicit elliptical string orbit projection factor kappa_orbit (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--beta-curv",
        type=float,
        default=None,
        help="Explicit dynamic core inductance curvature factor beta_curv (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--k-pull",
        type=float,
        default=None,
        help="Explicit nonlinear magnetic string pull factor k_pull (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--tau-touch",
        type=float,
        default=None,
        help="Explicit dynamic touch spectral tilt factor tau_touch (default: resolved from magnet_type in voices.toml)",
    )
    parser.add_argument(
        "--kappa-geom",
        type=float,
        default=None,
        help="Explicit conformal geometric clearance asymmetry factor kappa_geom (default: resolved from magnet_type)",
    )
    parser.add_argument(
        "--k-stein",
        type=float,
        default=None,
        help="Explicit dynamic Steinmetz AC core loss damping factor k_stein (default: resolved from magnet_type)",
    )
    parser.add_argument(
        "--vol",
        "--vol-pos",
        type=float,
        default=None,
        dest="vol",
        help="Volume pot wiper position (0.0 to 1.0, default 1.0 full open)",
    )
    parser.add_argument(
        "--tone",
        "--tone-pos",
        type=float,
        default=None,
        dest="tone",
        help="Tone pot wiper position (0.0 to 1.0, default 1.0 full open/bright)",
    )
    parser.add_argument(
        "--blend",
        "--blend-pos",
        type=float,
        default=None,
        dest="blend",
        help="Pickup blend wiper position (0.0 Neck to 1.0 Bridge, default: 0.5 Center detent 100%%/100%%)",
    )
    parser.add_argument(
        "--pot-taper",
        choices=["audio", "audio10", "audio15", "linear"],
        default="audio",
        help="Potentiometer resistance curve law (default: 'audio' for standard 10%% CTS audio pot)",
    )
    parser.add_argument(
        "--cable-pf",
        type=float,
        default=None,
        help="Cable capacitance loading in pF (default: from circuit config, typically 750 pF)",
    )
    parser.add_argument(
        "--sweep",
        type=str,
        default=None,
        help="Execute continuous parametric sweep (e.g. 'tone', 'vol', 'cable', 'tone_cap', 'bass_boost', 'treble_boost')",
    )
    parser.add_argument(
        "--no-spectral-tilt",
        action="store_true",
        help="Disable dynamic excursion-dependent touch spectral tilt",
    )
    parser.add_argument(
        "--no-slew-limit",
        action="store_true",
        help="Disable transient magnetic slew-rate limiting",
    )
    parser.add_argument(
        "--f-slew",
        type=float,
        default=16000.0,
        help="Magnetic domain-wall slew threshold frequency in Hz (default: 16000.0)",
    )
    parser.add_argument(
        "--no-eddy-diffusion",
        action="store_true",
        help="Disable Foster 2-stage core eddy diffusion (fall back to ideal frequency-independent L)",
    )
    parser.add_argument(
        "--no-hysteresis",
        action="store_true",
        help="Disable Dahl magnetic hysteresis friction modeling (eta_hyst = 0.0)",
    )
    parser.add_argument(
        "--eta-hyst",
        type=float,
        default=None,
        help="Explicit Dahl hysteresis coupling coefficient eta (default: resolved from magnet_type)",
    )
    parser.add_argument(
        "--no-dc-block",
        action="store_true",
        help="Disable sub-audible 8 Hz DC-blocking high-pass filter",
    )
    parser.add_argument(
        "--no-dither",
        action="store_true",
        help="Disable passive RLC-shaped -108 dBFS thermal noise dither",
    )
    parser.add_argument(
        "--jobs",
        "-j",
        type=int,
        default=None,
        help="Number of parallel worker processes for batch simulation (default: min(4, CPU count))",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Maximum audio sample frames to simulate (default: None for full file)",
    )
    parser.add_argument(
        "--stage",
        choices=["canonical", "frontends", "targets", "all"],
        default=None,
        help="Architecture C execution stage: 'canonical' (generate intermediate sweep), 'frontends' (export all 32 native frontend IRs), 'targets' (simulate backend sweeps), 'all' (canonical + frontends + targets).",
    )
    parser.add_argument(
        "--tier",
        choices=["clean", "standard", "std", "hotrod", "dynamic", "all"],
        default="standard",
        help="Dynamic tier: 'standard' / 'std' (100%% nominal target saturation), 'clean' (0%% saturation), 'hotrod' (175%% overwound), 'dynamic' (differential source/target saturation), 'all'.",
    )
    parser.add_argument(
        "--pickup",
        "-p",
        default=None,
        help="Physical pickup setting for source instrument ('auto' to resolve from pickup_mapping, or explicit pickup ID)",
    )
    args = parser.parse_args(argv)

    if args.sweep:
        from allomorph.circuit.sweeps import compute_parametric_sweep

        target_voices = resolve_voices(args.voice)
        for vid in target_voices:
            res = compute_parametric_sweep(vid, param=args.sweep, pot_taper=args.pot_taper)
            print(
                "\n========================================================================================="
            )
            print(f"  PARAMETRIC SWEEP: {vid} (Param: {args.sweep}, Taper: {args.pot_taper})")
            print(
                "========================================================================================="
            )
            print(
                f"Evaluated {len(res.values)} steps ({', '.join(res.labels)}) across {len(res.freqs)} frequencies.\n"
            )
            print("--- Frequency Response Grid ---")
            sample_freqs = [100.0, 500.0, 1000.0, 2500.0, 5000.0]
            header = f"{'Value / Label':<24}" + "".join(
                [f"{f'{f:.0f} Hz':>12}" for f in sample_freqs]
            )
            print(header)
            print("-" * len(header))
            f_arr = np.asarray(res.freqs)
            f_indices = [int(np.argmin(np.abs(f_arr - sf))) for sf in sample_freqs]
            for lbl, curve in zip(res.labels, res.curves):
                row = f"{lbl:<24}" + "".join([f"{curve[idx]:>11.1f}dB" for idx in f_indices])
                print(row)
            print("\n--- Analytical Circuit Metrics ---")
            res.print_metrics()
        return

    if args.stage == "canonical":
        generate_canonical_sweep(input_wav=args.input, output_wav=args.out)
        return
    if args.stage == "frontends":
        export_all_frontend_irs(output_dir=args.out)
        return
    if args.stage == "targets":
        simulate_backend_targets(tier=args.tier, voice_id=args.voice)
        return
    if args.stage == "all":
        generate_canonical_sweep(input_wav=args.input)
        export_all_frontend_irs(output_dir=args.out)
        simulate_backend_targets(tier=args.tier, voice_id=args.voice)
        return

    displacement_weighting = not args.no_displacement_weighting
    magnet_drag = not args.no_magnet_drag
    dc_block = not args.no_dc_block
    eddy_diffusion = not args.no_eddy_diffusion
    eta_hyst = 0.0 if args.no_hysteresis else args.eta_hyst
    noise_dither = not args.no_dither
    slew_limit = not args.no_slew_limit
    tau_touch = 0.0 if args.no_spectral_tilt else args.tau_touch

    instruments = resolve_instruments(args.instrument)
    voices = resolve_voices(args.voice)
    in_path = Path(args.input) if args.input else None
    out_path = Path(args.out) if args.out else None
    prefiltered = args.prefiltered or (in_path is not None and in_path.name.startswith("aperture_"))

    sim_cfg = SimulationConfig(
        input_wav=in_path,
        output_wav=out_path,
        pickup=args.pickup,
        tier=args.tier,
        prefiltered=prefiltered,
        normalize=args.normalize,
        target_dbfs=args.target_dbfs,
        oversample=args.oversample,
        displacement_weighting=displacement_weighting,
        magnet_drag=magnet_drag,
        alpha=args.alpha,
        alpha3=args.alpha3,
        eta_hyst=eta_hyst,
        k_sag=args.k_sag,
        k_eddy=args.k_eddy,
        kappa_orbit=args.kappa_orbit,
        beta_curv=args.beta_curv,
        k_pull=args.k_pull,
        tau_touch=tau_touch,
        kappa_geom=args.kappa_geom,
        k_stein=args.k_stein,
        vol_pos=args.vol,
        tone_pos=args.tone,
        blend_pos=args.blend,
        pot_taper=args.pot_taper,
        cable_pf=args.cable_pf,
        slew_limit=slew_limit,
        f_slew=args.f_slew,
        noise_dither=noise_dither,
        eddy_diffusion=eddy_diffusion,
        dc_block=dc_block,
        max_samples=args.max_samples,
    )
    sim_kwargs: dict[str, Any] = sim_cfg.to_sim_kwargs()

    max_workers = args.jobs if args.jobs is not None else min(4, os.cpu_count() or 4)
    for inst in instruments:
        cur_kwargs: dict[str, Any] = sim_kwargs.copy()
        cur_kwargs["instrument"] = inst
        if out_path and len(instruments) > 1 and not out_path.is_dir():
            stem = out_path.stem
            suffix = out_path.suffix
            cur_kwargs["output_wav"] = out_path.parent / f"{stem}_{inst}{suffix}"

        if len(voices) > 1 and max_workers > 1:
            from concurrent.futures import ProcessPoolExecutor

            tasks = [(v, cur_kwargs) for v in voices]
            with ProcessPoolExecutor(max_workers=max_workers) as executor:
                list(executor.map(_simulate_voice_task, tasks))
        else:
            for v in voices:
                simulate_voice(v, **cur_kwargs)


if __name__ == "__main__":
    main()

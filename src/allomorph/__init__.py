"""
Allomorph - Universal Pickup & Transducer Analog Modeling Engine
"""

__version__ = "0.1.0"

from allomorph.config import (
    INSTRUMENTS,
    VOICES,
    SCALES,
    STRINGS,
    load_instrument,
    load_all_instruments,
    load_voices_config,
    load_scales,
    load_strings_config,
    get_source_pickup,
    resolve_pickup_coils,
    resolve_voice_coils,
    resolve_voice_pickups,
    compute_effective_position,
)

from allomorph.dsp import (
    FS,
    NUM_TAPS,
    NYQ,
    FREQS,
    synthesize_minimum_phase_fir,
    write_wav_24bit,
)

from allomorph.naming import (
    VOICE_CONCISE_SLUGS,
    get_baked_basename,
    resolve_instruments,
    resolve_voices,
)

from allomorph.physics import (
    compute_voice_prefilter_firs,
    compute_aperture_prefilter_fir,
    numpy_pickup_acoustic_response,
    numpy_pickup_macro_aperture,
    compute_coil_aperture,
    generate_wave_speed_continuum,
)

from allomorph.circuit import (
    simulate_voice,
    generate_canonical_sweep,
    export_frontend_ir,
    export_all_frontend_irs,
    simulate_backend_targets,
)

__all__ = [
    "INSTRUMENTS",
    "VOICES",
    "SCALES",
    "STRINGS",
    "load_instrument",
    "load_all_instruments",
    "load_voices_config",
    "load_scales",
    "load_strings_config",
    "get_source_pickup",
    "resolve_pickup_coils",
    "resolve_voice_coils",
    "resolve_voice_pickups",
    "compute_effective_position",
    "FS",
    "NUM_TAPS",
    "NYQ",
    "FREQS",
    "synthesize_minimum_phase_fir",
    "write_wav_24bit",
    "VOICE_CONCISE_SLUGS",
    "get_baked_basename",
    "resolve_instruments",
    "resolve_voices",
    "compute_voice_prefilter_firs",
    "compute_aperture_prefilter_fir",
    "numpy_pickup_acoustic_response",
    "numpy_pickup_macro_aperture",
    "compute_coil_aperture",
    "generate_wave_speed_continuum",
    "simulate_voice",
    "generate_canonical_sweep",
    "export_frontend_ir",
    "export_all_frontend_irs",
    "simulate_backend_targets",
]

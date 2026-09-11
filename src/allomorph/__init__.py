"""
Allomorph - Universal Pickup & Transducer Analog Modeling Engine
"""

__version__ = "0.1.0"

from allomorph.circuit import (
    export_all_frontend_irs,
    export_frontend_ir,
    generate_canonical_sweep,
    simulate_backend_targets,
    simulate_voice,
)
from allomorph.config import (
    INSTRUMENTS,
    SCALES,
    STRINGS,
    VOICES,
    compute_effective_position,
    get_source_pickup,
    load_all_instruments,
    load_instrument,
    load_scales,
    load_strings_config,
    load_voices_config,
    resolve_pickup_coils,
    resolve_voice_coils,
    resolve_voice_pickups,
)
from allomorph.dsp import (
    FREQS,
    FS,
    NUM_TAPS,
    NYQ,
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
    compute_aperture_prefilter_fir,
    compute_coil_aperture,
    compute_voice_prefilter_firs,
    generate_wave_speed_continuum,
    numpy_pickup_acoustic_response,
    numpy_pickup_macro_aperture,
)

__all__ = [
    "FREQS",
    "FS",
    "INSTRUMENTS",
    "NUM_TAPS",
    "NYQ",
    "SCALES",
    "STRINGS",
    "VOICES",
    "VOICE_CONCISE_SLUGS",
    "compute_aperture_prefilter_fir",
    "compute_coil_aperture",
    "compute_effective_position",
    "compute_voice_prefilter_firs",
    "export_all_frontend_irs",
    "export_frontend_ir",
    "generate_canonical_sweep",
    "generate_wave_speed_continuum",
    "get_baked_basename",
    "get_source_pickup",
    "load_all_instruments",
    "load_instrument",
    "load_scales",
    "load_strings_config",
    "load_voices_config",
    "numpy_pickup_acoustic_response",
    "numpy_pickup_macro_aperture",
    "resolve_instruments",
    "resolve_pickup_coils",
    "resolve_voice_coils",
    "resolve_voice_pickups",
    "resolve_voices",
    "simulate_backend_targets",
    "simulate_voice",
    "synthesize_minimum_phase_fir",
    "write_wav_24bit",
]

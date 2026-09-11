"""
Allomorph - Configuration & Instrument/Voice Registry Engine.
Provides modular access to physical scales, strings, instruments, target voices, and coil geometry.
"""

from allomorph.config.scales import (
    REPO_ROOT,
    CONFIG_DIR,
    SCALES_FILE,
    load_scales,
    resolve_scale_range,
    SCALES,
)
from allomorph.config.strings import (
    STRINGS_FILE,
    load_strings_config,
    get_instrument_string,
    get_voice_string,
    STRINGS,
)
from allomorph.config.voices import (
    VOICES_DIR,
    VOICES_FILE,
    VoiceRegistry,
    load_voices_config,
    VOICES,
)
from allomorph.config.geometry import (
    _infer_pole_type,
    resolve_pickup_coils,
    resolve_voice_pickups,
    resolve_voice_coils,
    compute_effective_position,
)
from allomorph.config.instruments import (
    INSTRUMENTS_DIR,
    INSTRUMENT_ALIASES,
    load_instrument,
    load_all_instruments,
    get_source_pickup,
    INSTRUMENTS,
)

__all__ = [
    "REPO_ROOT",
    "CONFIG_DIR",
    "INSTRUMENTS_DIR",
    "SCALES_FILE",
    "VOICES_DIR",
    "VOICES_FILE",
    "STRINGS_FILE",
    "SCALES",
    "VOICES",
    "INSTRUMENTS",
    "STRINGS",
    "INSTRUMENT_ALIASES",
    "VoiceRegistry",
    "load_scales",
    "resolve_scale_range",
    "load_instrument",
    "load_all_instruments",
    "get_source_pickup",
    "load_voices_config",
    "load_strings_config",
    "get_instrument_string",
    "get_voice_string",
    "_infer_pole_type",
    "resolve_pickup_coils",
    "resolve_voice_pickups",
    "resolve_voice_coils",
    "compute_effective_position",
]

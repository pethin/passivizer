"""
Target voice configuration registry and legacy voice alias resolution.
"""

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
VOICES_DIR = CONFIG_DIR / "voices"
VOICES_FILE = CONFIG_DIR / "voices.toml"


from typing import Any, ClassVar, override


class VoiceRegistry(dict[str, Any]):
    """Dictionary wrapper that provides transparent alias resolution for legacy voice IDs."""
    ALIASES: ClassVar[dict[str, str]] = {
        "11_pmm_hybrid_series": "11b_pmm_hybrid_series",
    }

    @override
    def __getitem__(self, key: str) -> Any:
        if super().__contains__(key):
            return super().__getitem__(key)
        if key in self.ALIASES:
            return super().__getitem__(self.ALIASES[key])
        return super().__getitem__(key)

    @override
    def get(self, key: str, default: Any = None) -> Any:
        if super().__contains__(key):
            return super().get(key, default)
        if key in self.ALIASES:
            return super().get(self.ALIASES[key], default)
        return default

    @override
    def __contains__(self, key: object) -> bool:
        return super().__contains__(key) or (isinstance(key, str) and key in self.ALIASES and super().__contains__(self.ALIASES[key]))


def load_voices_config(voices_path: str | Path | None = None) -> VoiceRegistry:
    """Loads all target voices and their acoustic parameters from modular TOML files."""
    if voices_path is not None:
        p = Path(voices_path)
        if p.is_dir():
            voices: dict[str, Any] = {}
            for toml_file in sorted(p.glob("*.toml")):
                with open(toml_file, "rb") as f:
                    vdata = tomllib.load(f)
                vid = vdata.get("id", toml_file.stem)
                voices[vid] = vdata
            return VoiceRegistry(voices)
        elif p.is_file():
            with open(p, "rb") as f:
                data = tomllib.load(f)
            if "voices" in data:
                return VoiceRegistry(data.get("voices", {}))
            vid = data.get("id", p.stem)
            return VoiceRegistry({vid: data})

    voices = {}
    if VOICES_DIR.is_dir():
        for toml_file in sorted(VOICES_DIR.glob("*.toml")):
            with open(toml_file, "rb") as f:
                vdata = tomllib.load(f)
            vid = vdata.get("id", toml_file.stem)
            voices[vid] = vdata
        if voices:
            return VoiceRegistry(voices)

    if VOICES_FILE.exists():
        with open(VOICES_FILE, "rb") as f:
            data = tomllib.load(f)
        return VoiceRegistry(data.get("voices", {}))

    return VoiceRegistry({})


VOICES = load_voices_config()

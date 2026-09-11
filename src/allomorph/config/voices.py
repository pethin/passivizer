"""
Target voice configuration registry and legacy voice alias resolution.
"""

from pathlib import Path
import tomllib

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
CONFIG_DIR = REPO_ROOT / "config"
VOICES_DIR = CONFIG_DIR / "voices"
VOICES_FILE = CONFIG_DIR / "voices.toml"


class VoiceRegistry(dict):
    """Dictionary wrapper that provides transparent alias resolution for legacy voice IDs."""
    ALIASES = {
        "11_pmm_hybrid_series": "11b_pmm_hybrid_series",
    }

    def __getitem__(self, key):
        if super().__contains__(key):
            return super().__getitem__(key)
        if key in self.ALIASES:
            return super().__getitem__(self.ALIASES[key])
        return super().__getitem__(key)

    def get(self, key, default=None):
        if super().__contains__(key):
            return super().get(key, default)
        if key in self.ALIASES:
            return super().get(self.ALIASES[key], default)
        return default

    def __contains__(self, key):
        return super().__contains__(key) or (key in self.ALIASES and super().__contains__(self.ALIASES[key]))


def load_voices_config(voices_path=None):
    """Loads all target voices and their acoustic parameters from modular TOML files."""
    if voices_path is not None:
        p = Path(voices_path)
        if p.is_dir():
            voices = {}
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

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

from allomorph.config.schema import VoiceConfig


class VoiceRegistry(dict[str, VoiceConfig]):
    """Dictionary wrapper that provides transparent alias resolution for legacy voice IDs."""

    ALIASES: ClassVar[dict[str, str]] = {
        "11_pmm_hybrid_series": "11b_pmm_hybrid_series",
    }

    @override
    def __getitem__(self, key: str) -> VoiceConfig:
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


def load_voice_config(identifier_or_path: str | Path | dict[str, Any] | VoiceConfig) -> VoiceConfig:
    """Loads and validates a single target voice configuration into a VoiceConfig model."""
    if isinstance(identifier_or_path, VoiceConfig):
        return identifier_or_path
    if isinstance(identifier_or_path, dict):
        return VoiceConfig.model_validate(identifier_or_path)

    raw = str(identifier_or_path).strip()
    key = VoiceRegistry.ALIASES.get(raw, raw)

    path = Path(key)
    if not path.exists():
        if (VOICES_DIR / f"{key}.toml").exists():
            path = VOICES_DIR / f"{key}.toml"
        elif (CONFIG_DIR / f"{key}.toml").exists():
            path = CONFIG_DIR / f"{key}.toml"
        else:
            raise FileNotFoundError(f"Voice configuration not found: '{identifier_or_path}' (searched in {VOICES_DIR})")

    with open(path, "rb") as f:
        data = tomllib.load(f)
    return VoiceConfig.model_validate(data)


def load_voices_config(voices_path: str | Path | None = None) -> VoiceRegistry:
    """Loads all target voices and their acoustic parameters into validated VoiceConfig models."""
    if voices_path is not None:
        p = Path(voices_path)
        if p.is_dir():
            voices: dict[str, VoiceConfig] = {}
            for toml_file in sorted(p.glob("*.toml")):
                with open(toml_file, "rb") as f:
                    vdata = tomllib.load(f)
                vmodel = VoiceConfig.model_validate(vdata)
                voices[vmodel.id] = vmodel
            return VoiceRegistry(voices)
        elif p.is_file():
            with open(p, "rb") as f:
                data = tomllib.load(f)
            if "voices" in data:
                return VoiceRegistry({
                    k: VoiceConfig.model_validate(v) for k, v in data["voices"].items()
                })
            vmodel = VoiceConfig.model_validate(data)
            return VoiceRegistry({vmodel.id: vmodel})

    voices_dict: dict[str, VoiceConfig] = {}
    if VOICES_DIR.is_dir():
        for toml_file in sorted(VOICES_DIR.glob("*.toml")):
            with open(toml_file, "rb") as f:
                vdata = tomllib.load(f)
            vmodel = VoiceConfig.model_validate(vdata)
            voices_dict[vmodel.id] = vmodel
        if voices_dict:
            return VoiceRegistry(voices_dict)

    if VOICES_FILE.exists():
        with open(VOICES_FILE, "rb") as f:
            data = tomllib.load(f)
        return VoiceRegistry({
            k: VoiceConfig.model_validate(v) for k, v in data.get("voices", {}).items()
        })

    return VoiceRegistry({})


VOICES: VoiceRegistry = load_voices_config()

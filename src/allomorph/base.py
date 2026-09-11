"""
Allomorph Base Configuration Schemas and Utilities.

Defines foundational base classes and SPICE unit parsing validators
used across all domain-specific schema modules.
"""

import warnings
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict

warnings.filterwarnings(
    "ignore",
    message=r".*Field name \"register\".*shadows an attribute in parent.*",
    category=UserWarning,
)

__all__ = [
    "AllomorphBaseModel",
    "SpiceFloat",
    "parse_spice_unit",
]


def parse_spice_unit(v: Any) -> Any:
    """Parses standard SPICE engineering suffix notation (Meg, k, m, u, n, p, g) with unit suffixes."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = v.strip()
        if not s:
            return None
        s_clean = s.rstrip("FfHhΩ").strip()
        if s_clean.lower().endswith("ohm"):
            s_clean = s_clean[:-3].strip()
        if not s_clean:
            s_clean = s
        if s_clean.lower().endswith("meg"):
            return float(s_clean[:-3]) * 1e6
        suffix_map = {
            "p": 1e-12,
            "n": 1e-9,
            "u": 1e-6,
            "m": 1e-3,
            "k": 1e3,
            "g": 1e9,
        }
        last_char = s_clean[-1].lower()
        if last_char in suffix_map:
            return float(s_clean[:-1]) * suffix_map[last_char]
        return float(s_clean)
    raise TypeError(f"Invalid SPICE value: {v}")


SpiceFloat = Annotated[float, BeforeValidator(parse_spice_unit)]


class AllomorphBaseModel(BaseModel):
    """
    Base model for Allomorph declarative configurations.
    Enforces strict validation (forbidding unknown keys) and provides
    transparent subscripting/dict-like access for downstream compatibility.
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    def __getitem__(self, item: str) -> Any:
        try:
            return getattr(self, item)
        except AttributeError:
            raise KeyError(item) from None

    def __setitem__(self, key: str, value: Any) -> None:
        setattr(self, key, value)

    def __contains__(self, item: object) -> bool:
        if not isinstance(item, str):
            return False
        return (item in type(self).model_fields or hasattr(self, item)) and getattr(
            self, item, None
        ) is not None

    def get(self, key: str, default: Any = None) -> Any:
        val = getattr(self, key, None)
        return val if val is not None else default

    def keys(self) -> list[str]:
        return list(type(self).model_fields.keys())

    def values(self) -> list[Any]:
        return [getattr(self, k) for k in type(self).model_fields]

    def items(self) -> list[tuple[str, Any]]:
        return [(k, getattr(self, k)) for k in type(self).model_fields]

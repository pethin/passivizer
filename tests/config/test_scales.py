"""
Tests for scale lengths and string wave speeds configuration.
"""

from allomorph.config import SCALES, ScaleConfig


def test_scales_structure():
    assert "30in" in SCALES
    assert "32in" in SCALES
    assert "34in" in SCALES
    assert "multiscale" in SCALES
    assert "upright" in SCALES

    for key, cfg in SCALES.items():
        assert isinstance(cfg, ScaleConfig), f"Scale {key} is not a ScaleConfig instance"
        assert len(cfg.speeds) in (4, 5)
        assert cfg.scale_length_m is not None and cfg.scale_length_m > 0

    # 30" wave speeds should be lower than 34" wave speeds, and 34" lower than upright
    for s30, s34, sup in zip(SCALES["30in"].speeds, SCALES["34in"].speeds, SCALES["upright"].speeds):
        assert s30 < s34 < sup

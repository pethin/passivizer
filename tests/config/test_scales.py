"""
Tests for scale lengths and string wave speeds configuration.
"""

from allomorph.config import SCALES


def test_scales_structure():
    assert "30in" in SCALES
    assert "32in" in SCALES
    assert "34in" in SCALES
    assert "multiscale" in SCALES
    assert "upright" in SCALES

    assert len(SCALES["30in"]["speeds"]) == 4
    assert len(SCALES["32in"]["speeds"]) == 4
    assert len(SCALES["34in"]["speeds"]) == 4
    assert len(SCALES["multiscale"]["speeds"]) == 4
    assert len(SCALES["upright"]["speeds"]) == 4

    # 30" wave speeds should be lower than 34" wave speeds, and 34" lower than upright
    for s30, s34, sup in zip(SCALES["30in"]["speeds"], SCALES["34in"]["speeds"], SCALES["upright"]["speeds"]):
        assert s30 < s34 < sup

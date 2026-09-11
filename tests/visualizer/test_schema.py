"""
Unit tests for visualizer schemas (portal instrument metadata).
"""

from allomorph.visualizer.schema import PortalInstrumentMeta


def test_portal_instrument_meta_validation():
    """Verify PortalInstrumentMeta schema properties and serialization."""
    meta = PortalInstrumentMeta(
        id="30in",
        name='30" Short Scale Bass',
        scale_in=30.0,
        scale_m=0.762,
        speeds_str="58.0 m/s, 75.0 m/s, 99.0 m/s, 130.0 m/s",
        pickups_summary="EMG MM (@ 77.5mm)",
        default_pickup="emg_mm",
    )
    assert meta.id == "30in"
    assert meta.scale_in == 30.0
    dump = meta.model_dump()
    assert dump["id"] == "30in"
    assert dump["scale_m"] == 0.762

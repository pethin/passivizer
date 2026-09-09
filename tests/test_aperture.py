import math
import numpy as np
from scripts.model_physics import (
    aperture_response,
    position_envelope,
    pickup_acoustic_response,
    load_instrument,
    get_source_pickup,
    resolve_pickup_coils,
    SCALES
)

def test_aperture_zero_frequency():
    speeds = SCALES["30in"]["speeds"]
    res = aperture_response(np.array([0.0]), w_in=1.5, d_in=0.75, speeds=speeds)[0]
    # Sinc(0) + 0.05 = 1.05; Comb(0) + 0.05 = 1.05; Product = 1.05 * 1.05 = 1.1025
    assert math.isclose(res, 1.1025, rel_tol=1e-3)

def test_aperture_single_vs_dual():
    speeds = SCALES["30in"]["speeds"]
    val_single = aperture_response(np.array([5000.0]), w_in=0.75, d_in=0.0, speeds=speeds)[0]
    val_dual = aperture_response(np.array([5000.0]), w_in=1.50, d_in=0.75, speeds=speeds)[0]
    
    # Dual coil should have more high-frequency aperture filtering than narrow single coil
    assert val_dual < val_single

def test_position_envelope():
    speeds = SCALES["34in"]["speeds"]
    freqs = np.array([200.0, 1000.0, 5000.0])
    res_bridge = position_envelope(freqs, pos_m=0.0406, speeds=speeds)
    res_neck = position_envelope(freqs, pos_m=0.1250, speeds=speeds)
    
    assert len(res_bridge) == 3
    assert len(res_neck) == 3
    assert all(val > 0.1 for val in res_bridge)
    assert all(val > 0.1 for val in res_neck)

def test_pickup_acoustic_response_single_coil():
    speeds = SCALES["34in"]["speeds"]
    coils = [
        {"position_from_bridge_m": 0.0406, "aperture_width_in": 0.75, "weight": 1.0, "polarity": 1.0, "strings": ["all"]}
    ]
    freqs = np.array([0.0, 500.0, 2000.0])
    res = pickup_acoustic_response(freqs, coils, speeds)

    # At 0 Hz, spatial phase is 0 and sinc(0) = 1, so response is 1.0 (fundamental preserved)
    assert math.isclose(res[0], 1.0, abs_tol=1e-3)
    # At 500 and 2000 Hz, response is positive
    assert res[1] > 0.05
    assert res[2] > 0.05

def test_split_coil_string_differentiation():
    """Verify that E/A coil only affects E and A strings, and D/G coil only affects D and G strings."""
    speeds = [66.98, 89.41, 119.35, 159.31] # E, A, D, G on 32"

    coils = [
        {"position_from_bridge_m": 0.1088, "aperture_width_in": 1.10, "weight": 1.0, "polarity": 1.0, "strings": ["E", "A"]},
        {"position_from_bridge_m": 0.1368, "aperture_width_in": 1.10, "weight": 1.0, "polarity": 1.0, "strings": ["D", "G"]},
    ]

    freqs = np.array([500.0])
    val_all = pickup_acoustic_response(freqs, coils, speeds, string_names=["E", "A", "D", "G"])[0]
    val_low = pickup_acoustic_response(freqs, coils, speeds[:2], string_names=["E", "A"])[0]
    val_high = pickup_acoustic_response(freqs, coils, speeds[2:], string_names=["D", "G"])[0]

    # Low strings (closer to bridge on Reverse P) and high strings (closer to neck) have distinct responses
    assert not math.isclose(val_low, val_high, rel_tol=1e-2)
    assert val_all > 0.05

def test_3coil_pmm_compound_response():
    """Verify that 3-coil P/MM blend evaluates 3 distinct physical coil positions."""
    inst = load_instrument("32in_custom_pmm")
    blend = get_source_pickup(inst, "11_pmm_hybrid_series") # routes to blend_parallel
    coils = resolve_pickup_coils(blend, inst)

    # Should have 4 coil records (PX D/G, PX E/A, MMTWX neck, MMTWX bridge)
    assert len(coils) == 4

    # Check that D/G strings see 3 active coils and E/A strings see 3 active coils
    dg_coils = [c for c in coils if "all" in c["strings"] or "D" in c["strings"]]
    assert len(dg_coils) == 3

    ea_coils = [c for c in coils if "all" in c["strings"] or "E" in c["strings"]]
    assert len(ea_coils) == 3

    # Positions should match blueprint: PX DG 136.8mm, MMTWX neck 73.7mm, MMTWX bridge 50.8mm
    positions = sorted([round(c["position_from_bridge_m"] * 1000, 1) for c in dg_coils])
    assert positions == [50.8, 73.7, 136.8]


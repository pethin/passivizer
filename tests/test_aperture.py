import math
import polars as pl
from scripts.model_physics import polars_aperture, polars_position, SCALES

def test_polars_aperture_zero_frequency():
    speeds = SCALES["30in"]["speeds"]
    df = pl.DataFrame({"freq": [0.0]})
    expr = polars_aperture(pl.col("freq"), w_in=1.5, d_in=0.75, speeds=speeds)
    res = df.select(expr.alias("ap")).to_dict(as_series=False)["ap"][0]
    # Sinc(0) + 0.05 = 1.05; Comb(0) + 0.05 = 1.05; Product = 1.05 * 1.05 = 1.1025
    assert math.isclose(res, 1.1025, rel_tol=1e-3)

def test_polars_aperture_single_vs_dual():
    speeds = SCALES["30in"]["speeds"]
    df = pl.DataFrame({"freq": [5000.0]})
    expr_single = polars_aperture(pl.col("freq"), w_in=0.75, d_in=0.0, speeds=speeds)
    expr_dual = polars_aperture(pl.col("freq"), w_in=1.50, d_in=0.75, speeds=speeds)
    
    val_single = df.select(expr_single.alias("single")).to_dict(as_series=False)["single"][0]
    val_dual = df.select(expr_dual.alias("dual")).to_dict(as_series=False)["dual"][0]
    
    # Dual coil should have more high-frequency aperture filtering than narrow single coil
    assert val_dual < val_single

def test_polars_position_envelope():
    speeds = SCALES["34in"]["speeds"]
    # Test at bridge position (40.6mm) vs neck position (125mm)
    df = pl.DataFrame({"freq": [200.0, 1000.0, 5000.0]})
    expr_bridge = polars_position(pl.col("freq"), pos_m=0.0406, speeds=speeds)
    expr_neck = polars_position(pl.col("freq"), pos_m=0.1250, speeds=speeds)
    
    res_bridge = df.select(expr_bridge.alias("bridge")).to_dict(as_series=False)["bridge"]
    res_neck = df.select(expr_neck.alias("neck")).to_dict(as_series=False)["neck"]
    
    assert len(res_bridge) == 3
    assert len(res_neck) == 3
    assert all(val > 0.1 for val in res_bridge)
    assert all(val > 0.1 for val in res_neck)

def test_polars_pickup_acoustic_response_single_coil():
    from scripts.model_physics import polars_pickup_acoustic_response
    speeds = SCALES["34in"]["speeds"]
    coils = [
        {"position_from_bridge_m": 0.0406, "aperture_width_in": 0.75, "weight": 1.0, "polarity": 1.0, "strings": ["all"]}
    ]
    df = pl.DataFrame({"freq": [0.0, 500.0, 2000.0]})
    expr = polars_pickup_acoustic_response(pl.col("freq"), coils, speeds)
    res = df.select(expr.alias("resp")).to_dict(as_series=False)["resp"]

    # At 0 Hz, standing wave sin(0) = 0, so result is floor (0.05)
    assert math.isclose(res[0], 0.05, abs_tol=1e-4)
    # At 500 and 2000 Hz, response is positive and above floor
    assert res[1] > 0.05
    assert res[2] > 0.05

def test_split_coil_string_differentiation():
    """Verify that E/A coil only affects E and A strings, and D/G coil only affects D and G strings."""
    from scripts.model_physics import polars_pickup_acoustic_response
    speeds = [66.98, 89.41, 119.35, 159.31] # E, A, D, G on 32"

    coils = [
        {"position_from_bridge_m": 0.1088, "aperture_width_in": 1.10, "weight": 1.0, "polarity": 1.0, "strings": ["E", "A"]},
        {"position_from_bridge_m": 0.1368, "aperture_width_in": 1.10, "weight": 1.0, "polarity": 1.0, "strings": ["D", "G"]},
    ]

    df = pl.DataFrame({"freq": [500.0]})
    # Evaluate across all 4 strings
    expr_all = polars_pickup_acoustic_response(pl.col("freq"), coils, speeds, string_names=["E", "A", "D", "G"])
    val_all = df.select(expr_all.alias("val")).to_dict(as_series=False)["val"][0]

    # Evaluate on low strings only vs high strings only
    expr_low = polars_pickup_acoustic_response(pl.col("freq"), coils, speeds[:2], string_names=["E", "A"])
    expr_high = polars_pickup_acoustic_response(pl.col("freq"), coils, speeds[2:], string_names=["D", "G"])

    val_low = df.select(expr_low.alias("val")).to_dict(as_series=False)["val"][0]
    val_high = df.select(expr_high.alias("val")).to_dict(as_series=False)["val"][0]

    # Low strings (closer to bridge on Reverse P) and high strings (closer to neck) have distinct responses
    assert not math.isclose(val_low, val_high, rel_tol=1e-2)
    assert val_all > 0.05

def test_3coil_pmm_compound_response():
    """Verify that 3-coil P/MM blend evaluates 3 distinct physical coil positions."""
    from scripts.model_physics import load_instrument, get_source_pickup, resolve_pickup_coils, polars_pickup_acoustic_response

    inst = load_instrument("32in_custom_pmm")
    blend = get_source_pickup(inst, "01_jazz_bass_pair") # routes to blend_parallel
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


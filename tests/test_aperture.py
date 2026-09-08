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

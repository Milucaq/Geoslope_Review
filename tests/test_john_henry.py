import numpy as np
import pandas as pd
from gsreview.analytics.john_henry import build_mesh, anchor_synthetic, frame_at
from gsreview.analytics.synthetic import generate_synthetic_monitoring_data, SyntheticConfig


def mesh():
    z = np.arange(64, dtype=float).reshape(8, 8)
    valid = np.ones_like(z, dtype=bool)
    return build_mesh(z, valid, (0.3, 0, 500000, 0, -0.3, 5200000), stride=2)


def test_sampled_geometry_preserves_native_coordinates():
    m = mesh()
    p = m["positions"]
    o = m["origin"]
    np.testing.assert_allclose(
        (p[:, 0] + o[0] - 500000 - 0.15) / 0.3,
        np.round((p[:, 0] + o[0] - 500000 - 0.15) / 0.3),
        atol=1e-5,
    )
    assert len(m["indices"]) == 18
    assert (m["uv"] >= 0).all() and (m["uv"] <= 1).all()
    assert np.all(
        np.cross(
            p[m["indices"][:, 1]] - p[m["indices"][:, 0]],
            p[m["indices"][:, 2]] - p[m["indices"][:, 0]],
        )[:, 1]
        > 0
    )


def test_nodata_not_bridged():
    z = np.ones((12, 12))
    valid = np.ones_like(z, dtype=bool)
    valid[:, 5:7] = False
    m = build_mesh(z, valid, (1, 0, 0, 0, -1, 12), stride=2)
    e = m["positions"][:, 0] + m["origin"][0]
    tri = e[m["indices"]]
    assert not ((tri.min(axis=1) < 5.5) & (tri.max(axis=1) > 6.5)).any()


def test_synthetic_reanchor_and_visual_scale():
    m = mesh()
    raw = generate_synthetic_monitoring_data(SyntheticConfig(n_prisms=4, days=3))["records"]
    before = raw.copy(deep=True)
    records = anchor_synthetic(raw, m["positions"], m["origin"])
    pd.testing.assert_frame_equal(raw, before)
    xyz = ["easting", "northing", "rl"]
    for pid, g in records.groupby("prism_id"):
        orig = raw.loc[raw.prism_id.eq(pid), xyz].to_numpy()
        new = g[xyz].to_numpy()
        np.testing.assert_allclose(new - new[0], orig - orig[0], atol=1e-8)
    cutoff = records.timestamp.max()
    a = frame_at(records, cutoff, m["origin"])
    b = frame_at(records, cutoff, m["origin"], 100)
    assert len(a) == 4
    for one, two in zip(a, b):
        np.testing.assert_allclose(two["position"], one["position"], atol=1e-10)
        np.testing.assert_allclose(
            np.array(two["vector_endpoint"]) - two["base"],
            100 * (np.array(one["position"]) - one["base"]),
            atol=1e-7,
        )
        assert one["easting"] == two["easting"]
        assert one["coordinate_displacement_mm"] == two["coordinate_displacement_mm"]


def test_missing_measurement_retains_last_valid():
    raw = pd.DataFrame(
        {
            "prism_id": ["P"] * 3,
            "timestamp": pd.date_range("2025-01-01", periods=3),
            "easting": [1.0, 2.0, 100.0],
            "northing": [1.0, 1.0, 1.0],
            "rl": [1.0, 1.0, 1.0],
            "model_eligible": [False, True, False],
            "causal_state": ["no_evaluable", "sin_marca", "no_evaluable"],
            "reported_3d_movement_mm": [np.nan, 1.0, np.nan],
        }
    )
    item = frame_at(raw, raw.timestamp.max(), [0, 0, 0])[0]
    assert item["easting"] == 2 and not item["eligible"] and item["state"] == "no_evaluable"


def test_vector_magnitude_and_cutoff_are_independent_of_display_scale():
    raw = pd.DataFrame(
        {
            "prism_id": ["P"] * 3,
            "timestamp": pd.date_range("2025-01-01", periods=3),
            "easting": [100.0, 100.003, 999.0],
            "northing": [200.0, 200.004, 999.0],
            "rl": [300.0, 300.0, 999.0],
            "model_eligible": [False, True, True],
            "causal_state": ["no_evaluable", "sin_marca", "candidato_revision"],
            "reported_3d_movement_mm": [np.nan, 8.0, 999.0],
        }
    )
    original = raw.copy(deep=True)
    for factor in (1, 10, 50, 100):
        item = frame_at(raw, raw.timestamp.iloc[1], [100, 200, 300], factor)[0]
        np.testing.assert_allclose(item["position"], [0.003, 0, -0.004], atol=1e-9)
        np.testing.assert_allclose(
            item["vector_endpoint"], [0.003 * factor, 0, -0.004 * factor], atol=1e-8
        )
        np.testing.assert_allclose(item["coordinate_displacement_mm"], 5.0, atol=1e-8)
        assert item["movement"] == 8.0 and item["state"] == "sin_marca"
    pd.testing.assert_frame_equal(raw, original)

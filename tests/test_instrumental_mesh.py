import numpy as np
import pandas as pd
from gsreview.analytics.instrumental_mesh import instrumental_payload


def points():
    return pd.DataFrame(
        {
            "prism_id": ["A", "B", "C", "D"],
            "easting": [100, 110, 100, 110],
            "northing": [200, 200, 210, 210],
            "rl": [10, 20, 30, 40],
            "causal_state": ["sin_marca", "candidato_revision", "no_evaluable", "marca_aislada"],
            "timestamp": ["2025-01-01"] * 4,
        }
    )


def test_original_coordinates_and_filter_are_preserved():
    p = points()
    before = p.copy(deep=True)
    out = instrumental_payload(p, p.iloc[:1], selected="A", labels=True)
    assert len(out["indices"]) == 6
    assert len(out["markers"]) == 1 and out["markers"][0]["id"] == "A"
    a = np.array(out["positions"]).reshape(-1, 3)
    e, n, z = out["origin"]
    np.testing.assert_allclose(a[:, 0] + e, p.easting)
    np.testing.assert_allclose(n - a[:, 2], p.northing)
    np.testing.assert_allclose(a[:, 1] + z, p.rl)
    pd.testing.assert_frame_equal(p, before)


def test_sparse_or_disabled_surface_still_shows_points():
    p = points()
    for source in [p.iloc[:1], p.iloc[:2]]:
        out = instrumental_payload(source, source)
        assert not out["indices"] and len(out["markers"]) == len(source)
    assert not instrumental_payload(p, p, surface=False)["indices"]


def test_ambiguous_sites_and_collinear_points():
    p = points()
    p.loc[1, ["easting", "northing"]] = [100, 200]
    assert not instrumental_payload(p, p)["indices"]
    p = points()
    p["northing"] = 200
    assert not instrumental_payload(p, p)["indices"]

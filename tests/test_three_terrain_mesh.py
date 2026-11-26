import numpy as np
import pytest

from gsreview.analytics.terrain_mesh import terrain_payload
from gsreview.domain.rules import ValidationError


def grid():
    return {"easting": np.array([[100, 130], [100, 130]]),
            "northing": np.array([[230, 230], [200, 200]]),
            "elevation": np.array([[10, 20], [30, 40]])}


@pytest.mark.parametrize("factor", [1, 3, 5])
def test_mesh_is_reversible_and_does_not_change_elevations(factor):
    arrays = grid()
    saved = {k: v.copy() for k, v in arrays.items()}
    result = terrain_payload(arrays, factor)
    assert (result["rows"], result["cols"]) == (2, 2)
    p = np.array(result["positions"]).reshape(2, 2, 3)
    e, n, z = result["origin"]
    np.testing.assert_allclose(p[..., 0] + e, saved["easting"])
    np.testing.assert_allclose(n - p[..., 2], saved["northing"])
    np.testing.assert_allclose(p[..., 1] / factor + z, saved["elevation"])
    for key in arrays:
        np.testing.assert_array_equal(arrays[key], saved[key])
    assert result["elevation_min"] == 10
    assert result["elevation_max"] == 40


def test_invalid_mesh_rejected():
    with pytest.raises(ValidationError):
        terrain_payload(grid(), 2)
    arrays = grid()
    arrays["elevation"] = np.ones((1, 2))
    with pytest.raises(ValidationError):
        terrain_payload(arrays)
    arrays = grid()
    arrays["elevation"] = np.full((2, 2), np.nan)
    with pytest.raises(ValidationError):
        terrain_payload(arrays)

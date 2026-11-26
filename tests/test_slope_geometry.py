import numpy as np
import pandas as pd
from gsreview.analytics.slope_geometry import slope_degrees, slope_sectors, annotate_anchors


def test_plane_angle_and_reverse_winding():
    p = np.array([[0,0,0],[1,1,0],[0,0,1],[1,1,1]], dtype=float)
    t = np.array([[0,2,1],[1,2,3]])
    np.testing.assert_allclose(slope_degrees(p,t),45)
    np.testing.assert_allclose(slope_degrees(p,t[:,::-1]),45)
    p[:,1] = 0
    np.testing.assert_allclose(slope_degrees(p,t),0)


def test_sectors_do_not_cross_disconnected_mesh_or_low_slope():
    t = np.array([[0,1,2],[3,4,5],[6,7,8]])
    s = np.array([40,42,50,44,45,46,5,6,7])
    out = slope_sectors(s,t,35,3)
    assert set(out) == {0,1,2}
    assert len(set(out[:3])) == len(set(out[3:6])) == 1
    assert out[0] != out[3] and not out[6:].any()


def test_anchor_metadata_preserves_measurements():
    p = np.array([[1,2,-3],[4,5,-6.]])
    r = pd.DataFrame({'prism_id':['P','P'],'timestamp':pd.date_range('2025-01-01',periods=2),
                      'easting':[101.,101.001],'northing':[203.,203.],'rl':[302.,302.]})
    out = annotate_anchors(r,p,[100,200,300],np.array([40.,60.]),np.array([1,2]))
    assert out.sector_topografico.tolist() == [1,1]
    assert out.pendiente_base_deg.tolist() == [40.,40.]
    pd.testing.assert_frame_equal(out[r.columns],r)

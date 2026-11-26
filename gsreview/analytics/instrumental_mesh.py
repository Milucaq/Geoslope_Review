"""Representación instrumental local. TIN exploratoria, no topografía certificada."""
import numpy as np
from scipy.spatial import Delaunay, QhullError, cKDTree

from gsreview.domain.rules import ValidationError


def instrumental_payload(points, visible, selected=None, labels=False, focus=False,
                         surface=True):
    columns = ["easting", "northing", "rl"]
    xyz = points[columns].to_numpy(dtype=float, copy=True)
    if not len(xyz) or not np.isfinite(xyz).all():
        raise ValidationError("Coordenadas instrumentales no válidas.")
    ids = points["prism_id"].astype(str).tolist()
    if len(set(ids)) != len(ids):
        raise ValidationError("Existen prismas duplicados en el corte.")
    origin = (xyz.min(axis=0) + xyz.max(axis=0)) / 2
    local = xyz - origin
    scene = local[:, [0, 2, 1]].copy()
    scene[:, 2] *= -1
    indices = []
    # Sitios horizontales duplicados con cotas distintas no definen una superficie 2.5D.
    xy = local[:, :2]
    _, inverse, counts = np.unique(xy, axis=0, return_inverse=True, return_counts=True)
    unique = np.flatnonzero(counts[inverse] == 1)
    # Limitar puentes largos: heurística visual explícita, no límite geotécnico.
    if surface and len(unique) >= 3:
        sites = xy[unique]
        if np.linalg.matrix_rank(sites - sites.mean(axis=0)) == 2:
            try:
                triangles = Delaunay(sites).simplices
                neighbors = cKDTree(sites).query(sites, k=2)[0][:, 1]
                max_edge = 3.0 * float(np.median(neighbors))
                for tri in triangles:
                    vertices = sites[tri]
                    lengths = np.linalg.norm(vertices - np.roll(vertices, 1, axis=0), axis=1)
                    if np.max(lengths) <= max_edge:
                        indices.extend(int(unique[i]) for i in tri)
            except QhullError:
                pass
    visible_ids = set(visible["prism_id"].astype(str))
    markers = []
    for i, (_, row) in enumerate(points.iterrows()):
        if ids[i] not in visible_ids:
            continue
        markers.append({"id": ids[i], "position": scene[i].tolist(),
                        "state": str(row["causal_state"]),
                        "timestamp": str(row["timestamp"])})
    return {"positions": scene.ravel().tolist(), "indices": indices,
            "origin": origin.tolist(), "markers": markers, "selected": selected,
            "labels": bool(labels), "focus": bool(focus), "surface": bool(surface),
            "reference_count": len(ids)}

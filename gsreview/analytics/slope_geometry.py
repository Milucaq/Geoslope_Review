"""Experimental geometric slope analysis on the unexaggerated terrain mesh."""
import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def slope_degrees(positions, triangles):
    """Area-weighted vertex normals; x/z horizontal, y vertical, all in metres."""
    p = np.asarray(positions, dtype=float)
    t = np.asarray(triangles, dtype=np.int64)
    if p.ndim != 2 or p.shape[1] != 3 or not np.isfinite(p).all():
        raise ValueError('Vertices invalidos')
    if t.ndim != 2 or t.shape[1] != 3 or not len(t) or t.min() < 0 or t.max() >= len(p):
        raise ValueError('Triangulos invalidos')
    n = np.cross(p[t[:, 1]] - p[t[:, 0]], p[t[:, 2]] - p[t[:, 0]])
    n[n[:, 1] < 0] *= -1
    summed = np.zeros_like(p)
    for i in range(3):
        np.add.at(summed, t[:, i], n)
    length = np.linalg.norm(summed, axis=1)
    slopes = np.full(len(p), np.nan)
    good = length > 0
    slopes[good] = np.degrees(np.arctan2(np.linalg.norm(summed[good][:, [0, 2]], axis=1),
                                        summed[good, 1]))
    return slopes


def slope_sectors(slopes, triangles, threshold=35, min_vertices=20):
    """Connected steep vertices, no crossing gaps or creating terrain."""
    s = np.asarray(slopes, dtype=float)
    if not 0 < threshold < 90 or min_vertices < 1:
        raise ValueError('Parametros de pendiente invalidos')
    valid = np.isfinite(s) & (s >= threshold)
    t = np.asarray(triangles, dtype=np.int64)
    edges = t[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2)
    edges = edges[valid[edges].all(axis=1)]
    graph = coo_matrix((np.ones(len(edges), dtype=np.uint8),
                        (edges[:, 0], edges[:, 1])), shape=(len(s), len(s))).tocsr()
    _, labels = connected_components(graph, directed=False)
    counts = np.bincount(labels[valid], minlength=(labels.max()+1 if len(labels) else 0))
    groups = [int(i) for i in np.flatnonzero(counts >= min_vertices)]
    groups.sort(key=lambda i: (-counts[i], i))
    lookup = np.zeros(len(counts), dtype=np.int32)
    for number, group in enumerate(groups, 1):
        lookup[group] = number
    result = lookup[labels]
    result[~valid] = 0
    return result


def annotate_anchors(records, positions, origin, slopes, sectors):
    """Metadata at the initial synthetic anchor, not at projected positions."""
    result = records.copy(deep=True)
    first = result.sort_values('timestamp').groupby('prism_id', sort=False).head(1)
    coordinates = first[['easting', 'northing', 'rl']].to_numpy(dtype=float)
    local = coordinates - np.asarray(origin, dtype=float)
    local = local[:, [0, 2, 1]]
    local[:, 2] *= -1
    distance, idx = cKDTree(positions).query(local)
    if np.any(distance > 1e-4):
        raise ValueError('Anclajes no coinciden con vertices del terreno')
    slope_map = dict(zip(first.prism_id, slopes[idx]))
    sector_map = dict(zip(first.prism_id, sectors[idx]))
    result['pendiente_base_deg'] = result.prism_id.map(slope_map)
    result['sector_topografico'] = result.prism_id.map(sector_map)
    return result

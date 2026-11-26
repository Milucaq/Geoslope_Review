"""Measured terrain geometry and independent synthetic prism placement."""
import numpy as np
import pandas as pd


def build_mesh(z, valid, transform, stride=6):
    """Sample native vertices; never triangulate across a block containing NoData.

    transform is (a,b,c,d,e,f), mapping pixel corner to projected coordinates.
    """
    z = np.asarray(z)
    valid = np.asarray(valid, dtype=bool) & np.isfinite(z)
    if z.ndim != 2 or valid.shape != z.shape or stride < 1:
        raise ValueError("Raster o paso no válido")
    a, b, c, d, e, f = transform
    if not (a > 0 and e < 0 and b == d == 0):
        raise ValueError("Se requiere una cuadrícula norte arriba sin rotación")
    rr = np.arange(0, z.shape[0], stride)
    cc = np.arange(0, z.shape[1], stride)
    if min(len(rr), len(cc)) < 2:
        raise ValueError("Raster demasiado pequeño")
    # Include the boundary of every block when determining its validity.
    block = np.logical_and.reduceat(np.logical_and.reduceat(valid, rr, axis=0), cc, axis=1)
    sampled = valid[np.ix_(rr, cc)]
    good = (block[:-1, :-1] & block[1:, :-1] & block[:-1, 1:] & block[1:, 1:])
    good &= sampled[:-1, :-1] & sampled[1:, :-1] & sampled[:-1, 1:] & sampled[1:, 1:]
    r, col = np.where(good)
    if not len(r):
        raise ValueError("No hay bloques completos de terreno válido")
    width = len(cc)
    tl = r * width + col
    tr, bl, br = tl + 1, tl + width, tl + width + 1
    triangles = np.column_stack((tl, bl, tr, tr, bl, br)).reshape(-1, 3)
    used, remap = np.unique(triangles, return_inverse=True)
    ri, ci = np.divmod(used, width)
    east = c + a * (cc[ci] + .5)
    north = f + e * (rr[ri] + .5)
    elevation = z[rr[ri], cc[ci]].astype(float)
    origin = np.array([(east.min()+east.max())/2, (north.min()+north.max())/2,
                       (elevation.min()+elevation.max())/2])
    bounds = np.array([east.min(), north.min(), east.max(), north.max()])
    positions = np.column_stack((east-origin[0], elevation-origin[2], origin[1]-north))
    uv = np.column_stack(((east-bounds[0])/(bounds[2]-bounds[0]),
                          (north-bounds[1])/(bounds[3]-bounds[1])))
    return {"positions": positions.astype('<f4'), "uv": uv.astype('<f4'),
            "indices": remap.reshape(-1, 3).astype('<u4'), "origin": origin,
            "bounds": bounds, "elevation_range": np.array([elevation.min(), elevation.max()])}


def anchor_synthetic(records, positions, origin, seed=42):
    """Translate simulated trajectories onto measured vertices; never mix historical data."""
    records = records.copy(deep=True).sort_values(["prism_id", "timestamp"])
    positions = np.asarray(positions, dtype=float)
    origin = np.asarray(origin, dtype=float)
    ids = records.prism_id.unique()
    if len(ids) > len(positions) or not len(ids):
        raise ValueError("No hay suficientes vértices para el escenario")
    rng = np.random.default_rng(seed)
    # Farthest-point placement in horizontal coordinates, seeded for reproducibility.
    selected = [int(rng.integers(len(positions)))]
    xy = positions[:, [0, 2]]
    distances = np.full(len(positions), np.inf)
    for _ in range(1, len(ids)):
        distances = np.minimum(distances, np.sum((xy - xy[selected[-1]]) ** 2, axis=1))
        distances[selected] = -1
        selected.append(int(np.argmax(distances)))
    xyz = ["easting", "northing", "rl"]
    for prism, index in zip(ids, selected):
        mask = records.prism_id.eq(prism)
        group = records.loc[mask, xyz]
        base = group.iloc[0].to_numpy(dtype=float)
        x, y, zz = positions[index]
        target = np.array([origin[0]+x, origin[1]-zz, origin[2]+y])
        records.loc[mask, xyz] = group.to_numpy(dtype=float) - base + target
    return records


def frame_at(records, cutoff, origin, amplify=1):
    """Show last valid simulated position when the latest observation is unavailable."""
    if amplify not in (1, 10, 50, 100):
        raise ValueError("Factor visual no válido")
    xyz = ["easting", "northing", "rl"]
    origin = np.asarray(origin, dtype=float)
    result = []
    for prism, group in records.groupby("prism_id", sort=True):
        group = group.sort_values("timestamp")
        past = group.loc[group.timestamp.le(pd.Timestamp(cutoff))]
        if past.empty:
            continue
        latest = past.iloc[-1]
        eligible = past.loc[past.model_eligible.fillna(False)]
        observed = eligible.iloc[-1] if not eligible.empty else past.iloc[0]
        base = group.iloc[0][xyz].to_numpy(dtype=float)
        actual = observed[xyz].to_numpy(dtype=float)
        # The marker always follows the unamplified simulated measurement.
        delta = actual - base
        x, y, z = actual - origin
        dx, dy, dz = base - origin
        # Separate endpoint for the illustrative arrow, not a new measurement.
        vx, vy, vz = base - origin + delta * amplify
        result.append({"id": str(prism), "position": [x,z,-y], "base": [dx,dz,-dy],
                       "vector_endpoint": [vx,vz,-vy],
                       "coordinate_displacement_mm": float(np.linalg.norm(delta)*1000),
                       "state": str(latest.causal_state), "timestamp": str(latest.timestamp),
                       "position_timestamp": str(observed.timestamp),
                       "eligible": bool(latest.model_eligible),
                       "movement": float(observed.reported_3d_movement_mm)
                       if pd.notna(observed.reported_3d_movement_mm) else None,
                       "easting": float(actual[0]), "northing": float(actual[1]), "rl": float(actual[2])})
    return result

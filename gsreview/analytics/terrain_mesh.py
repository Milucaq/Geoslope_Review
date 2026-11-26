"""Malla de terreno en coordenadas locales de renderizado; no cambia los datos de origen."""

import numpy as np

from gsreview.domain.rules import ValidationError


def terrain_payload(arrays, exaggeration=1):
    if exaggeration not in (1, 3, 5):
        raise ValidationError("Exageración vertical no válida.")
    e, n, z = (np.asarray(arrays[k], dtype=float) for k in ("easting", "northing", "elevation"))
    if e.ndim != 2 or min(e.shape) < 2 or e.shape != n.shape or e.shape != z.shape:
        raise ValidationError("La malla debe tener dimensiones compatibles.")
    if not all(np.isfinite(a).all() for a in (e, n, z)):
        raise ValidationError("La malla contiene coordenadas inválidas.")
    origin = [float((a.min() + a.max()) / 2) for a in (e, n, z)]
    # Three.js: X=Este, Y=Elevación, Z=-Norte. Centrar antes de pasar a float32.
    positions = np.stack((e - origin[0], (z - origin[2]) * exaggeration, origin[1] - n), axis=-1)
    return {
        "rows": e.shape[0],
        "cols": e.shape[1],
        "positions": positions.ravel().tolist(),
        "origin": origin,
        "elevation_min": float(z.min()),
        "elevation_max": float(z.max()),
        "exaggeration": exaggeration,
    }

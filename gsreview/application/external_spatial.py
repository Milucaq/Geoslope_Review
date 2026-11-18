"""Adaptación temporal de mediciones externas para el visor geoespacial."""

import numpy as np
import pandas as pd

from gsreview.domain.rules import ValidationError


def prepare_external_points(frame: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """Selecciona la última medición con coordenadas válidas por prisma."""
    required = {
        "prism_id",
        "timestamp",
        "easting",
        "northing",
        "rl",
        "movement_rate_mm_per_day",
    }

    if not required.issubset(frame.columns):
        raise ValidationError(
            "Los datos externos no contienen las columnas requeridas para el visor."
        )

    data = frame.copy()

    for column in ("easting", "northing", "rl", "movement_rate_mm_per_day"):
        data[column] = pd.to_numeric(data[column], errors="coerce")

    data["timestamp"] = pd.to_datetime(
        data["timestamp"], errors="coerce", utc=True
    )

    valid_coordinates = np.isfinite(
        data[["easting", "northing", "rl"]].to_numpy(dtype=float)
    ).all(axis=1)

    invalid_count = int((~valid_coordinates).sum())
    data = data.loc[valid_coordinates & data["timestamp"].notna()].copy()

    if data.empty:
        raise ValidationError(
            "No existen prismas con coordenadas válidas para visualizar."
        )

    data = (
        data.sort_values("timestamp")
        .drop_duplicates(subset=["prism_id"], keep="last")
        .reset_index(drop=True)
    )

    return data, invalid_count

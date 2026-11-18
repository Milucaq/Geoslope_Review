"""Pruebas de integración geoespacial de HU-110."""

import pandas as pd
import pytest

from gsreview.application.external_spatial import prepare_external_points
from gsreview.domain.rules import ValidationError


def sample_data():
    return pd.DataFrame(
        {
            "prism_id": ["P001", "P001", "P002"],
            "timestamp": [
                "2026-11-09T10:00:00Z",
                "2026-11-10T10:00:00Z",
                "2026-11-09T12:00:00Z",
            ],
            "easting": [500000, 500010, 500100],
            "northing": [8500000, 8500010, 8500100],
            "rl": [1200, 1201, 1210],
            "movement_rate_mm_per_day": [1.2, 2.5, 0.8],
        }
    )


def test_ultima_medicion_por_prisma():
    points, invalid = prepare_external_points(sample_data())

    assert len(points) == 2
    assert invalid == 0
    assert points.loc[
        points.prism_id.eq("P001"), "easting"
    ].iloc[0] == 500010


def test_coordenadas_invalidas():
    data = sample_data()
    data.loc[2, "easting"] = float("nan")

    points, invalid = prepare_external_points(data)

    assert invalid == 1
    assert len(points) == 1
    assert points.iloc[0]["prism_id"] == "P001"


def test_todas_las_coordenadas_invalidas():
    data = sample_data()
    data["northing"] = float("nan")

    with pytest.raises(ValidationError, match="coordenadas válidas"):
        prepare_external_points(data)


def test_columnas_obligatorias():
    data = sample_data().drop(columns=["rl"])

    with pytest.raises(ValidationError, match="columnas requeridas"):
        prepare_external_points(data)


def test_no_modifica_datos_originales():
    original = sample_data()
    snapshot = original.copy(deep=True)

    prepare_external_points(original)

    pd.testing.assert_frame_equal(original, snapshot)

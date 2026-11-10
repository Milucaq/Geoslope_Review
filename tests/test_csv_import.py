
"""Pruebas de validación para la HU-106."""

import pytest

from gsreview.application.csv_import import validate_csv
from gsreview.domain.rules import ValidationError


HEADER = (
    "source_record_id,prism_id,timestamp,easting,northing,"
    "rl,movement_rate_mm_per_day,elapsed_hours\n"
)

VALID_ROW = (
    "R001,P001,2026-11-09T10:00:00Z,"
    "500000,8500000,1200,2.5,24\n"
)


def test_csv_valido():
    result = validate_csv((HEADER + VALID_ROW).encode("utf-8"))

    assert len(result) == 1
    assert result.iloc[0]["prism_id"] == "P001"
    assert result.iloc[0]["movement_rate_mm_per_day"] == 2.5


def test_csv_vacio():
    with pytest.raises(ValidationError, match="vacío"):
        validate_csv(b"")


def test_csv_sin_columnas_obligatorias():
    content = b"prism_id,timestamp\nP001,2026-11-09\n"

    with pytest.raises(ValidationError, match="Faltan columnas"):
        validate_csv(content)


def test_csv_fecha_invalida():
    content = (HEADER + VALID_ROW.replace(
        "2026-11-09T10:00:00Z", "fecha-invalida"
    )).encode("utf-8")

    with pytest.raises(ValidationError, match="fechas"):
        validate_csv(content)


def test_csv_valor_numerico_invalido():
    content = (HEADER + VALID_ROW.replace(
        "500000", "valor-incorrecto"
    )).encode("utf-8")

    with pytest.raises(ValidationError, match="numéricos"):
        validate_csv(content)


def test_csv_identificador_duplicado():
    content = (HEADER + VALID_ROW + VALID_ROW).encode("utf-8")

    with pytest.raises(ValidationError, match="duplicados"):
        validate_csv(content)


def test_csv_tiempo_negativo():
    content = (HEADER + VALID_ROW.replace(
        ",24\n", ",-24\n"
    )).encode("utf-8")

    with pytest.raises(ValidationError, match="negativo"):
        validate_csv(content)


def test_csv_supera_limite():
    content = b"x" * (10 * 1024 * 1024 + 1)

    with pytest.raises(ValidationError, match="10 MB"):
        validate_csv(content)

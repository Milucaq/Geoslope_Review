
"""Validación de mediciones CSV externas sin modificar artefactos históricos."""

from io import BytesIO

import pandas as pd

from gsreview.domain.rules import ValidationError


REQUIRED_COLUMNS = (
    "source_record_id",
    "prism_id",
    "timestamp",
    "easting",
    "northing",
    "rl",
    "movement_rate_mm_per_day",
    "elapsed_hours",
)

NUMERIC_COLUMNS = (
    "easting",
    "northing",
    "rl",
    "movement_rate_mm_per_day",
    "elapsed_hours",
)

MAX_FILE_SIZE = 10 * 1024 * 1024


def validate_csv(content: bytes) -> pd.DataFrame:
    """Devuelve mediciones validadas sin persistirlas."""

    if not content:
        raise ValidationError("El archivo CSV está vacío.")

    if len(content) > MAX_FILE_SIZE:
        raise ValidationError("El archivo supera el límite de 10 MB.")

    try:
        frame = pd.read_csv(
            BytesIO(content),
            encoding="utf-8-sig",
            dtype=str,
            keep_default_na=False,
        )
    except (UnicodeError, pd.errors.ParserError, ValueError) as exc:
        raise ValidationError(
            "No se pudo leer el CSV. Verifica su codificación y estructura."
        ) from exc

    missing = [col for col in REQUIRED_COLUMNS if col not in frame.columns]

    if missing:
        raise ValidationError(
            "Faltan columnas obligatorias: " + ", ".join(missing)
        )

    if frame.empty:
        raise ValidationError("El archivo no contiene registros.")

    frame = frame.loc[:, REQUIRED_COLUMNS].copy()

    for column in ("source_record_id", "prism_id"):
        frame[column] = frame[column].str.strip()
        if frame[column].eq("").any():
            raise ValidationError(
                f"La columna {column} contiene identificadores vacíos."
            )

    if frame["source_record_id"].duplicated().any():
        raise ValidationError("Existen identificadores de registro duplicados.")

    frame["timestamp"] = pd.to_datetime(
        frame["timestamp"],
        errors="coerce",
        utc=True,
    )

    if frame["timestamp"].isna().any():
        raise ValidationError("Existen fechas u horas inválidas.")

    for column in NUMERIC_COLUMNS:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

        if frame[column].isna().any():
            raise ValidationError(
                f"La columna {column} contiene valores numéricos inválidos."
            )

    if frame.duplicated(["prism_id", "timestamp"]).any():
        raise ValidationError(
            "Existen mediciones duplicadas para un mismo prisma y fecha."
        )

    if frame["elapsed_hours"].lt(0).any():
        raise ValidationError(
            "El tiempo transcurrido no puede ser negativo."
        )

    return frame

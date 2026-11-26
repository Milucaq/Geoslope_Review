"""Validación segura de mediciones CSV externas sin modificar artefactos históricos."""

from io import BytesIO

import numpy as np
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
MAX_ROWS = 100_000
MAX_IDENTIFIER_LENGTH = 128

ALLOWED_EXTENSIONS = (".csv",)
ALLOWED_MIME_TYPES = (
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",
    "text/plain",
    "application/octet-stream",
    "",
)

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
BINARY_SIGNATURES = (
    b"MZ",
    b"PK\x03\x04",
    b"%PDF",
    b"\x89PNG",
    b"\xff\xd8\xff",
    b"\x7fELF",
)
DANGEROUS_PATTERNS = (
    "<script",
    "javascript:",
    "onerror=",
    "onload=",
    "cmd|",
    "powershell",
)


def validate_upload_metadata(
    filename: str | None = None,
    content_type: str | None = None,
) -> None:
    """Verifica extensión, ruta y tipo MIME declarado del archivo cargado."""
    if filename is not None:
        cleaned = filename.strip()
        if not cleaned or "\x00" in cleaned or ".." in cleaned or "/" in cleaned or "\\" in cleaned:
            raise ValidationError(
                "El nombre del archivo contiene caracteres o rutas no permitidas."
            )
        if not cleaned.lower().endswith(ALLOWED_EXTENSIONS):
            raise ValidationError(
                "Tipo de archivo no permitido. Solo se aceptan archivos con extensión .csv."
            )

    if content_type is not None:
        normalized_mime = content_type.split(";")[0].strip().lower()
        if normalized_mime not in ALLOWED_MIME_TYPES:
            raise ValidationError("Tipo MIME de archivo no permitido para importación CSV.")


def _check_safe_identifier_series(series: pd.Series, column: str) -> None:
    """Valida que una columna de identificadores no contenga payloads maliciosos."""
    if series.str.len().gt(MAX_IDENTIFIER_LENGTH).any():
        raise ValidationError(
            f"La columna {column} excede la longitud máxima permitida ({MAX_IDENTIFIER_LENGTH} caracteres)."
        )

    if series.str.startswith(FORMULA_PREFIXES).any():
        raise ValidationError(
            f"La columna {column} contiene caracteres potencialmente inseguros (inyección de fórmulas)."
        )

    lowered = series.str.lower()
    for pattern in DANGEROUS_PATTERNS:
        if lowered.str.contains(pattern, regex=False).any():
            raise ValidationError(
                f"La columna {column} contiene patrones no permitidos por seguridad."
            )


def validate_csv(
    content: bytes,
    filename: str | None = None,
    content_type: str | None = None,
) -> pd.DataFrame:
    """Devuelve mediciones validadas de forma segura sin persistirlas."""

    validate_upload_metadata(filename=filename, content_type=content_type)

    if not content:
        raise ValidationError("El archivo CSV está vacío.")

    if len(content) > MAX_FILE_SIZE:
        raise ValidationError("El archivo supera el límite de 10 MB.")

    if b"\x00" in content or content.startswith(BINARY_SIGNATURES):
        raise ValidationError(
            "El archivo contiene contenido binario o no corresponde a un texto CSV válido."
        )

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
        raise ValidationError("Faltan columnas obligatorias: " + ", ".join(missing))

    if frame.empty:
        raise ValidationError("El archivo no contiene registros.")

    if len(frame) > MAX_ROWS:
        raise ValidationError(
            f"El archivo supera el límite máximo permitido de {MAX_ROWS} registros."
        )

    optional = ["reported_3d_movement_mm"] if "reported_3d_movement_mm" in frame else []
    frame = frame.loc[:, list(REQUIRED_COLUMNS) + optional].copy()
    for column in optional:
        # Empty scalar measurements remain missing, never reconstructed from rates.
        raw = frame[column].str.strip()
        values = pd.to_numeric(raw.mask(raw.eq("")), errors="coerce")
        if (raw.ne("") & values.isna()).any() or np.isinf(values.to_numpy(float)).any():
            raise ValidationError("La magnitud escalar reportada debe estar en mm y ser finita o vacía.")
        frame[column] = values

    for column in ("source_record_id", "prism_id"):
        frame[column] = frame[column].str.strip()
        if frame[column].eq("").any():
            raise ValidationError(f"La columna {column} contiene identificadores vacíos.")
        _check_safe_identifier_series(frame[column], column)

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

        if frame[column].isna().any() or not np.isfinite(frame[column].to_numpy(dtype=float)).all():
            raise ValidationError(f"La columna {column} contiene valores numéricos inválidos.")

    if frame.duplicated(["prism_id", "timestamp"]).any():
        raise ValidationError("Existen mediciones duplicadas para un mismo prisma y fecha.")

    if frame["elapsed_hours"].lt(0).any():
        raise ValidationError("El tiempo transcurrido no puede ser negativo.")

    return frame

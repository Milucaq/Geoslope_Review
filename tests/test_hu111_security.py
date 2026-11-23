"""Pruebas automatizadas de seguridad en carga de archivos y control de acceso (HU-111)."""

import os
from pathlib import Path

import pytest

from conftest import engineer
from gsreview.application.csv_import import (
    MAX_FILE_SIZE,
    MAX_IDENTIFIER_LENGTH,
    validate_csv,
    validate_upload_metadata,
)
from gsreview.domain.rules import AccessDenied, ValidationError


HEADER = (
    "source_record_id,prism_id,timestamp,easting,northing,"
    "rl,movement_rate_mm_per_day,elapsed_hours\n"
)

VALID_ROW = "R001,P001,2026-11-09T10:00:00Z,500000,8500000,1200,2.5,24\n"


def test_hu111_accepts_valid_csv_with_safe_metadata():
    content = (HEADER + VALID_ROW).encode("utf-8")
    frame = validate_csv(content, filename="mediciones_seguras.csv", content_type="text/csv")
    assert len(frame) == 1
    assert frame.iloc[0]["prism_id"] == "P001"


@pytest.mark.parametrize(
    "bad_filename",
    [
        "payload.exe",
        "mediciones.xlsx",
        "reporte.pdf",
        "script.js",
        "../secretos.csv",
        "..\\config.csv",
        "subcarpeta/datos.csv",
        "archivo\x00.csv",
        "   ",
    ],
)
def test_hu111_rejects_unsafe_filenames_and_extensions(bad_filename):
    content = (HEADER + VALID_ROW).encode("utf-8")
    with pytest.raises(ValidationError):
        validate_csv(content, filename=bad_filename)


@pytest.mark.parametrize(
    "bad_mime",
    [
        "application/javascript",
        "text/html",
        "application/x-msdownload",
        "application/pdf",
    ],
)
def test_hu111_rejects_disallowed_mime_types(bad_mime):
    with pytest.raises(ValidationError, match="MIME"):
        validate_upload_metadata(filename="datos.csv", content_type=bad_mime)


@pytest.mark.parametrize(
    "binary_payload",
    [
        b"MZ\x90\x00\x03\x00\x00\x00ejecutable_disfrazado",
        b"PK\x03\x04archivo_zip_o_xlsx_disfrazado",
        b"%PDF-1.7 archivo pdf disfrazado",
        b"\x89PNG\r\n\x1a\nimagen disfrazada",
        (HEADER + "R001\x00,P001,2026-11-09T10:00:00Z,500000,8500000,1200,2.5,24\n").encode(
            "utf-8"
        ),
    ],
)
def test_hu111_rejects_binary_files_disguised_as_csv(binary_payload):
    with pytest.raises(ValidationError, match="binario"):
        validate_csv(binary_payload, filename="disfrazado.csv")


@pytest.mark.parametrize(
    "malicious_id",
    [
        "=CMD|' /C calc'!A0",
        "+SUM(1,1)",
        "-2+3+cmd",
        "@IMPORTXML(A1,A2)",
        "<script>alert(1)</script>",
        "javascript:alert(1)",
    ],
)
def test_hu111_rejects_csv_formula_and_script_injection(malicious_id):
    row = f"R001,{malicious_id},2026-11-09T10:00:00Z,500000,8500000,1200,2.5,24\n"
    with pytest.raises(ValidationError, match="inseguros|seguridad"):
        validate_csv((HEADER + row).encode("utf-8"), filename="inyeccion.csv")


def test_hu111_rejects_oversized_identifier_and_non_finite_numbers():
    long_id = "P" * (MAX_IDENTIFIER_LENGTH + 1)
    row_long = f"R001,{long_id},2026-11-09T10:00:00Z,500000,8500000,1200,2.5,24\n"
    with pytest.raises(ValidationError, match="longitud"):
        validate_csv((HEADER + row_long).encode("utf-8"))

    row_inf = "R001,P001,2026-11-09T10:00:00Z,inf,8500000,1200,2.5,24\n"
    with pytest.raises(ValidationError, match="numéricos"):
        validate_csv((HEADER + row_inf).encode("utf-8"))


def test_hu111_enforces_file_size_limit():
    oversized = b"a" * (MAX_FILE_SIZE + 1)
    with pytest.raises(ValidationError, match="10 MB"):
        validate_csv(oversized, filename="grande.csv")


def test_hu111_administrative_functions_require_authorization(app):
    _, engineer_token, _ = engineer(app)

    with pytest.raises(AccessDenied):
        app.auth.create_user(engineer_token, "otro", "Otro", "ClaveSegura!2026", "ingeniero")

    with pytest.raises(AccessDenied):
        app.auth.safe_users(engineer_token)

    with pytest.raises(AccessDenied):
        app.auth.safe_sessions(engineer_token)

    with pytest.raises(AccessDenied):
        app.settings.save(engineer_token, "display_rows", "50")

    with pytest.raises(AccessDenied):
        app.backups.create(engineer_token)

    with pytest.raises(AccessDenied):
        app.auth.authorize("token-invalido-no-registrado", "read")


def test_hu111_no_secrets_exposed_in_source_or_error_messages(app):
    root = Path(__file__).resolve().parents[1] / "gsreview"
    forbidden_literals = (
        "ClaveTemporalSoloParaPruebas2026!",
        "ClaveLocal2026!",
        "$argon2id$",
    )
    for py_file in root.rglob("*.py"):
        source = py_file.read_text(encoding="utf-8")
        for secret in forbidden_literals:
            assert secret not in source, f"Secreto expuesto en {py_file.name}"

    setup_key = os.environ.get("GEOSLOPE_SETUP_KEY", "")
    try:
        validate_csv(b"contenido_invalido", filename="malo.exe")
    except ValidationError as exc:
        message = str(exc)
        assert setup_key not in message
        assert "$argon2id$" not in message
        assert "Traceback" not in message

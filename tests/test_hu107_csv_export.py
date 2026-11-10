"""Pruebas unitarias e integración para HU-107: Exportación de datos sintéticos en formato CSV."""

from io import BytesIO

import numpy as np
import pandas as pd
import pytest

from gsreview.analytics.synthetic import (
    SYNTHETIC_CSV_COLUMNS,
    SyntheticConfig,
    export_synthetic_records_to_csv,
    generate_synthetic_monitoring_data,
)
from gsreview.application.csv_import import validate_csv
from gsreview.domain.rules import AccessDenied, ValidationError


def test_export_synthetic_csv_structure_and_hu106_compatibility():
    cfg = SyntheticConfig(n_prisms=8, days=10, cadence_hours=12, deformed_fraction=0.25, seed=107)
    scenario = generate_synthetic_monitoring_data(cfg)
    csv_bytes = export_synthetic_records_to_csv(scenario["records"])

    assert isinstance(csv_bytes, bytes)
    assert len(csv_bytes) > 0

    exported_df = pd.read_csv(BytesIO(csv_bytes))
    required_hu107_cols = {
        "prism_id",
        "timestamp",
        "easting",
        "northing",
        "rl",
        "reported_3d_movement_mm",
    }
    assert required_hu107_cols.issubset(set(exported_df.columns))
    assert tuple(exported_df.columns) == SYNTHETIC_CSV_COLUMNS
    assert len(exported_df) == scenario["summary"]["evaluables"]
    assert not exported_df.isna().any().any()

    validated_df = validate_csv(csv_bytes)
    assert len(validated_df) == len(exported_df)
    assert set(validated_df["prism_id"]) == set(exported_df["prism_id"])


def test_export_synthetic_csv_accepts_dataframe_without_model_eligible_column():
    cfg = SyntheticConfig(n_prisms=4, days=4, cadence_hours=24, deformed_fraction=0.25, seed=21)
    rows = generate_synthetic_monitoring_data(cfg)["records"]
    eligible_only = rows.loc[rows.model_eligible, list(SYNTHETIC_CSV_COLUMNS)].copy()

    csv_bytes = export_synthetic_records_to_csv(eligible_only)
    validated_df = validate_csv(csv_bytes)
    assert len(validated_df) == len(eligible_only)


@pytest.mark.parametrize(
    ("mutator", "expected_msg"),
    [
        (lambda df: pd.DataFrame(), "No hay registros sintéticos"),
        (
            lambda df: df.drop(columns=["reported_3d_movement_mm"]),
            "Faltan columnas requeridas",
        ),
        (
            lambda df: df.assign(model_eligible=False),
            "No existen mediciones sintéticas evaluables",
        ),
        (
            lambda df: df.assign(prism_id="   "),
            "identificadores inválidos",
        ),
        (
            lambda df: df.assign(source_record_id=900001),
            "identificadores de registro duplicados",
        ),
        (
            lambda df: df.assign(timestamp="fecha-invalida"),
            "fechas u horas inválidas",
        ),
        (
            lambda df: df.assign(
                prism_id="SYN-W01",
                timestamp=pd.Timestamp("2025-01-02T00:00:00Z"),
            ),
            "mediciones duplicadas para un mismo prisma y fecha",
        ),
        (
            lambda df: df.assign(reported_3d_movement_mm=np.nan),
            "valores numéricos inválidos",
        ),
        (
            lambda df: df.assign(elapsed_hours=-12.0),
            "tiempo transcurrido no puede ser negativo",
        ),
    ],
)
def test_export_synthetic_csv_rejects_invalid_records(mutator, expected_msg):
    cfg = SyntheticConfig(n_prisms=4, days=4, cadence_hours=24, deformed_fraction=0.25, seed=99)
    base_df = generate_synthetic_monitoring_data(cfg)["records"]
    corrupted_df = mutator(base_df.copy())

    with pytest.raises(ValidationError, match=expected_msg):
        export_synthetic_records_to_csv(corrupted_df)


def test_synthetic_service_export_csv_auth_audit_and_integrity(app):
    scenario = app.synthetic.generate(
        app.test_admin, n_prisms=6, days=6, cadence_hours=24, deformed_fraction=0.3, seed=107
    )
    assert "csv_bytes" in scenario

    with pytest.raises(AccessDenied):
        app.synthetic.export_csv("invalid_token", scenario)

    with pytest.raises(ValidationError, match="No hay registros sintéticos"):
        app.synthetic.export_csv(app.test_admin, "invalid_payload")

    csv_from_dict = app.synthetic.export_csv(app.test_admin, scenario)
    csv_from_df = app.synthetic.export_csv(app.test_admin, scenario["records"], seed=107)
    assert csv_from_dict == csv_from_df

    validated = validate_csv(csv_from_dict)
    assert len(validated) == scenario["summary"]["evaluables"]
    assert app.reader.verify() == 17

    events = app.reviews.audit(app.test_admin)
    export_events = [e for e in events if e["action"] == "synthetic_csv_exported"]
    assert len(export_events) >= 2
    assert export_events[0]["object_id"] == "seed:107"


def test_quality_view_renders_synthetic_panel_and_csv_export(app, monkeypatch):
    from streamlit.testing.v1 import AppTest

    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    appfile = app.app_root / "app.py"
    at = AppTest.from_file(str(appfile), default_timeout=15)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Calidad de datos"
    at.session_state["synthetic_scenario"] = app.synthetic.generate(
        app.test_admin, n_prisms=6, days=5, cadence_hours=24, deformed_fraction=0.3, seed=42
    )
    at.run()
    assert not at.exception and not at.error
    scenario = at.session_state["synthetic_scenario"]
    assert "csv_bytes" in scenario
    validated = validate_csv(scenario["csv_bytes"])
    assert len(validated) == scenario["summary"]["evaluables"]


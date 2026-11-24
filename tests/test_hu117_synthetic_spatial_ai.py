"""Pruebas automatizadas para la HU-117: Visualización espacial y detección de fallas en escenarios sintéticos."""

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from gsreview.analytics.synthetic import (
    SyntheticConfig,
    classify_synthetic_prisms,
    export_synthetic_records_to_csv,
    generate_synthetic_monitoring_data,
)
from gsreview.application.csv_import import validate_csv
from gsreview.application.external_spatial import prepare_external_points
from gsreview.domain.rules import AccessDenied, ValidationError
from gsreview.presentation.charts import SYNTHETIC_RISK_COLORS, synthetic_spatial_map


def test_hu117_classifies_prisms_into_risk_levels_and_computes_summary():
    config = SyntheticConfig(
        n_prisms=12,
        days=15,
        cadence_hours=12,
        deformed_fraction=0.25,
        noise_mm=0.35,
        seed=42,
    )
    scenario = generate_synthetic_monitoring_data(config)
    spatial_points = scenario["spatial_points"]
    summary = scenario["summary"]

    assert len(spatial_points) == 12
    required_cols = {
        "prism_id",
        "sector",
        "bench",
        "easting",
        "northing",
        "rl",
        "displacement_mm",
        "latest_rate_mm_day",
        "max_rate_mm_day",
        "acceleration_mm_day2",
        "risk_level",
        "risk_label",
        "risk_score",
        "diagnosis",
    }
    assert required_cols.issubset(spatial_points.columns)

    assert summary["prismas_alerta_falla"] == 3
    assert (
        summary["prismas_estables"]
        + summary["prismas_observacion"]
        + summary["prismas_alerta_falla"]
        == 12
    )
    assert 0.0 <= summary["indice_estabilidad_pct"] <= 100.0

    alerts = spatial_points.loc[spatial_points["risk_level"].eq("alerta_falla")]
    stables = spatial_points.loc[spatial_points["risk_level"].eq("estable")]
    assert len(alerts) == 3
    assert (alerts["risk_score"] >= 75.0).all()
    assert (alerts["displacement_mm"] > stables["displacement_mm"].max()).all()
    assert alerts["diagnosis"].str.contains("inestabilidad|inspección", case=False).all()


def test_hu117_rejects_empty_records_for_classification_and_export():
    with pytest.raises(ValidationError, match="registros sintéticos"):
        classify_synthetic_prisms(pd.DataFrame())

    with pytest.raises(ValidationError, match="mediciones sintéticas"):
        export_synthetic_records_to_csv(pd.DataFrame())


def test_hu117_builds_2d_and_3d_spatial_figures_with_risk_colors_and_highlight():
    scenario = generate_synthetic_monitoring_data(SyntheticConfig(n_prisms=10, days=12, seed=77))
    points = scenario["spatial_points"]
    target_prism = points.iloc[0]["prism_id"]

    fig_3d = synthetic_spatial_map(points, dimension="3D", selected=target_prism)
    trace_types_3d = [type(t).__name__ for t in fig_3d.data]
    assert "Surface" in trace_types_3d
    assert "Scatter3d" in trace_types_3d
    marker_colors_3d = {
        getattr(t.marker, "color", None) for t in fig_3d.data if hasattr(t, "marker")
    }
    assert SYNTHETIC_RISK_COLORS["alerta_falla"] in marker_colors_3d

    fig_2d = synthetic_spatial_map(points, dimension="2D", selected=target_prism)
    trace_types_2d = [type(t).__name__ for t in fig_2d.data]
    assert "Scatter" in trace_types_2d
    assert "Surface" not in trace_types_2d
    assert "2D" in fig_2d.layout.title.text


def test_hu117_csv_export_is_compatible_with_validator_and_external_viewer(app):
    scenario = app.synthetic.generate(app.test_admin, n_prisms=8, days=10, seed=101)
    csv_bytes = scenario["csv_bytes"]
    assert isinstance(csv_bytes, bytes) and len(csv_bytes) > 0

    validated = validate_csv(csv_bytes, filename="geoslope_sintetico_seed_101.csv")
    assert len(validated) == scenario["summary"]["evaluables"]

    ext_points, invalid_count = prepare_external_points(validated)
    assert invalid_count == 0
    assert len(ext_points) == 8

    with pytest.raises(AccessDenied):
        app.synthetic.export_csv("token-invalido", scenario)


def test_hu117_ui_renders_spatial_viewer_and_ai_diagnosis_without_altering_frozen_data(
    app, monkeypatch
):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=25)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Calidad de datos"
    at.session_state["synthetic_scenario"] = app.synthetic.generate(
        app.test_admin, n_prisms=8, days=10, seed=42
    )
    at.run()

    assert not at.exception and not at.error
    assert at.selectbox(key="syn_risk_filter").value == "Todos"
    selected_prism = at.selectbox(key="syn_selected_prism").value
    assert selected_prism.startswith("SYN-W")
    assert app.reader.verify() == 17

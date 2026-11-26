"""Authenticated import activation and simulation UI preserve historical data."""

from types import SimpleNamespace

import pandas as pd
from streamlit.testing.v1 import AppTest

from conftest import engineer
from gsreview.presentation import views


CSV = (
    "source_record_id,prism_id,timestamp,easting,northing,rl,movement_rate_mm_per_day,elapsed_hours\n"
    "EXTERNAL-1,EXTERNAL-P1,2026-01-01T00:00:00Z,100,200,10,1,24\n"
).encode()


def test_quality_import_activation_navigation_and_user_change_are_isolated(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    uploaded = SimpleNamespace(name="controlled.csv", type="text/csv", getvalue=lambda: CSV)
    monkeypatch.setattr(
        views.st, "file_uploader",
        lambda *a, **k: uploaded if k.get("key") == "hu106_csv_upload" else None,
    )
    original = app.reader.rows.copy(deep=True)
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=25)
    at.session_state["token"] = app.test_admin
    at.session_state["nav"] = "Calidad de datos"
    at.run()
    assert not at.exception and not at.error
    at.button(key="activate_external_csv").click().run()
    assert not at.exception and not at.error
    assert at.session_state["active_scenario"] == "external"
    assert at.selectbox(key="scenario_selector").value == "external"
    assert any(t.value == "Calidad del escenario" for t in at.title)
    at.button(key="rail_Vista espacial").click().run()
    assert not at.exception and not at.error
    assert set(at.dataframe[0].value.prism_id) == {"EXTERNAL-P1"}
    at.button(key="rail_Inicio").click().run()
    assert any(t.value == "Panorama del escenario" for t in at.title)
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Prismas del escenario"] == "1" and metrics["Mediciones disponibles"] == "1"
    assert metrics["Episodios candidatos"] == "No calculados"
    at.button(key="rail_Bandeja de revisión").click().run()
    assert any(t.value == "Revisión del escenario" for t in at.title)
    assert not any(t.value == "Bandeja de revisión" for t in at.title)
    assert not at.dataframe
    # Simulate a different authenticated owner in the same browser state.
    _, new_token, _ = engineer(app)
    at.session_state["token"] = new_token
    at.session_state["current_page"] = "Inicio"
    at.run()
    assert not at.exception and not at.error
    assert at.session_state["active_scenario"] == "historical"
    assert "scenario_external_frame" not in at.session_state
    assert any(t.value == "Panorama de revisión" for t in at.title)
    pd.testing.assert_frame_equal(app.reader.rows, original)
    assert app.reader.verify() == 17


def synthetic_panel(c, token):
    from gsreview.presentation.views import _render_synthetic_panel

    _render_synthetic_panel(c, token)


def test_synthetic_panel_generates_reproducible_preview_and_audit_only(app):
    before = app.reader.rows.copy(deep=True)
    at = AppTest.from_function(synthetic_panel, args=(app, app.test_admin), default_timeout=25).run()
    at.number_input(key="syn_prisms").set_value(4)
    at.number_input(key="syn_days").set_value(3)
    at.selectbox(key="syn_cadence").select(24)
    next(b for b in at.button if b.label == "Generar datos sintéticos").click().run()
    assert not at.exception and not at.error
    result = at.session_state["synthetic_scenario"]
    assert result["summary"]["prismas"] == 4
    assert at.metric[0].value == "4" and len(at.get("plotly_chart")) == 1
    assert set(at.dataframe[0].value.prism_id) == {"SYN-W01", "SYN-W02", "SYN-W03", "SYN-W04"}
    records = result["records"].copy(deep=True)
    next(b for b in at.button if b.label == "Generar datos sintéticos").click().run()
    pd.testing.assert_frame_equal(at.session_state["synthetic_scenario"]["records"], records)
    pd.testing.assert_frame_equal(app.reader.rows, before)
    events = app.reviews.audit(app.test_admin)
    assert sum(e["action"] == "synthetic_data_generated" for e in events) == 2

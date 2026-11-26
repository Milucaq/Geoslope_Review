"""D.1 acceptance: real SQLite persistence, immutable archives and encrypted recovery."""

import json
import subprocess
import sys
from datetime import date

import pandas as pd
import pytest
from sqlalchemy import select
from streamlit.testing.v1 import AppTest

from conftest import engineer
from test_phase_c_workflow import observations, decision
from gsreview.application.persistence import PersistenceService, restore_state
from gsreview.application.scenario_reports import report_payload
from gsreview.application.workflow import data_version
from gsreview.domain.rules import ValidationError
from gsreview.infrastructure.store import workspace_records

pytest_plugins = ["test_john_henry_workspace"]


def state(frame):
    return {"active_scenario": "john_henry", "jh_records": frame, "scenario_jh_valid": True,
            "jh_asset": "mesh-v1", "jh_slope_config": ("mesh-v1", 35, 1),
            "scenario_jh_settings": {"seed": 42, "sector": 1, "count": 4},
            "scenario_analysis_cutoff": frame.timestamp.max().isoformat()}


def test_scenario_restores_in_another_process_and_preserves_floats_and_results(app):
    frame = observations()
    raw = state(frame)
    raw["scenario_science_result"] = {"scores": frame, "signature": data_version(frame)}
    raw["scenario_forecast_result"] = {"request": ("john_henry", "hash", "P1", 24, True), "future": frame}
    saved = app.persistence.save_scenario(app.test_admin, "John Henry guardado", raw)
    fresh = PersistenceService(app.auth).scenario(app.test_admin, saved["id"])
    restored = {}
    restore_state(restored, fresh)
    pd.testing.assert_frame_equal(restored["jh_records"], frame)
    assert data_version(restored["jh_records"]) == data_version(frame)
    assert restored["jh_slope_config"] == ("mesh-v1", 35, 1)
    assert isinstance(restored["scenario_forecast_result"]["request"], tuple)
    # Independent Python process, no Streamlit cache or inherited objects.
    script = (
        "import sqlite3,sys,json; "
        "from gsreview.application.persistence import decode,restore_state; "
        "from gsreview.application.workflow import data_version; "
        "c=sqlite3.connect(sys.argv[1]); "
        "snapshot=decode(json.loads(c.execute('SELECT payload FROM workspace_records').fetchone()[0])); "
        "c.close(); state={}; restore_state(state,snapshot); "
        "print(json.dumps({'name':snapshot['name'],'hash':data_version(state['jh_records']),"
        "'score_hash':data_version(state['scenario_science_result']['scores'])}))"
    )
    result = subprocess.run([sys.executable, "-c", script, str(app.store.path)], capture_output=True, text=True, check=True)
    recovered = json.loads(result.stdout)
    assert recovered == {"name": "John Henry guardado", "hash": data_version(frame), "score_hash": data_version(frame)}
    with pytest.raises(ValidationError):
        app.persistence.save_scenario(app.test_admin, "stale", raw | {"scenario_saved_id": saved["id"]})
    updated = app.persistence.save_scenario(app.test_admin, "Actualizado", restored)
    assert updated["revision"] == 2 and updated["created_at"] == saved["created_at"]
    _, token, _ = engineer(app)
    assert app.persistence.listing(token, "scenario") == []
    with pytest.raises(ValidationError):
        app.persistence.scenario(token, saved["id"])


def test_report_deduplicates_is_immutable_and_has_version_lineage(app):
    frame = observations()
    payload = report_payload(app.auth, app.scenario_reviews, app.test_admin, "external", frame, {})
    saved = app.persistence.save_report(app.test_admin, payload, "Conclusión", "Observaciones", "request-one")
    assert app.persistence.save_report(app.test_admin, payload, "Otra conclusión", "", "request-one") == saved
    payload["observations"][0]["easting"] = 999
    assert app.persistence.listing(app.test_admin, "report")[0]["snapshot"]["observations"][0]["easting"] != 999
    revision = app.persistence.save_report(app.test_admin, payload, "Nueva edición", "", "request-two", saved["id"])
    assert revision["version"] == 2 and revision["parent"] == saved["id"]
    for conclusions, parent in [("", None), ("ok", "foreign")]:
        with pytest.raises(ValidationError):
            app.persistence.save_report(app.test_admin, payload, conclusions, "", "bad", parent)
    _, token, _ = engineer(app)
    assert app.persistence.listing(token, "report") == []
    with pytest.raises(ValidationError):
        app.persistence.save_report(token, payload, "ok", "", "foreign")


def test_encrypted_backup_restores_workspace_and_reviews_and_accepts_legacy(app):
    frame = observations()
    app.persistence.save_scenario(app.test_admin, "Case", state(frame))
    app.scenario_reviews.save(app.test_admin, "john_henry", frame, "P1", frame.timestamp.max(), "test-model", "test-analysis", decision())
    payload = report_payload(app.auth, app.scenario_reviews, app.test_admin, "john_henry", frame, {})
    app.persistence.save_report(app.test_admin, payload, "Conclusión", "", "report")
    backup = app.backups.create(app.test_admin).read_bytes()
    assert b"Conclusi" not in backup
    app.scenario_reviews.repository.path.unlink()  # Only the fixture's temporary database.
    with app.store.tx() as c:
        c.execute(workspace_records.delete())
    app.backups.restore(app.test_admin, backup)
    with app.store.tx() as c:
        rows = c.execute(select(workspace_records)).all()
    assert len(rows) == 2
    assert len(app.scenario_reviews.repository.records(
        payload["generated_by"]["actor_id"], "john_henry", data_version(frame))) == 1
    decoded = json.loads(app.cipher.decrypt(backup.decode()))
    assert len(decoded["scenario_reviews"]) == 1
    # Old schema-1 envelope without additive records remains accepted.
    decoded["tables"].pop("workspace_records")
    decoded.pop("scenario_reviews")
    # Recreate a valid test session after restore revoked tokens.
    import pyotp
    app.test_clock[0] += 31
    challenge, _ = app.auth.password_step("testadmin", app.test_password)
    token, _ = app.auth.second_step(challenge, pyotp.TOTP(app.test_secret).at(app.test_clock[0]))
    app.backups.restore(token, app.cipher.encrypt(json.dumps(decoded)).encode())
    with app.store.tx() as c:
        assert len(c.execute(select(workspace_records)).all()) == 2
    assert app.reader.verify() == 17


def report_app(c, frame):
    from gsreview.presentation.persistence import reports
    from gsreview.application.scenarios import SCENARIOS
    reports(c, c.test_admin, SCENARIOS["external"], frame)


def test_report_form_success_clears_and_failure_retains_then_reopens(app):
    frame = observations()
    at = AppTest.from_function(report_app, args=(app, frame)).run()
    assert not at.get("download_button")
    assert [b.label for b in at.button if b.proto.type == "primary"] == ["Guardar reporte"]
    at.text_input(key="report_search").set_value("NO MATCH").run()
    at.text_area(key="report_notes").set_value("Conservar borrador")
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    assert at.error and at.text_area(key="report_notes").value == "Conservar borrador"
    at.text_area(key="report_conclusions").set_value("Conclusión técnica")
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    assert not at.exception and not at.error
    assert at.text_area(key="report_conclusions").value == ""
    assert at.text_area(key="report_notes").value == ""
    assert at.session_state["report_tab"] == "Historial de reportes"
    tabs = at.get("tab_container")[0].proto.tab_container
    assert tabs.id and tabs.default_tab_index == 1  # Stateful frontend receives the new selection.
    assert at.text_input(key="report_search").value == ""
    assert at.selectbox(key="report_history_selection").value == at.session_state["report_selected"]
    assert len(app.persistence.listing(app.test_admin, "report")) == 1
    fresh = AppTest.from_function(report_app, args=(app, None)).run()
    assert not fresh.exception
    assert len(fresh.get("download_button")) == 3
    assert not fresh.json
    fresh.button(key="report_view_detail").click().run()
    assert fresh.json
    fresh.selectbox(key="report_filter_Estado").select("Sin revisión").run()
    assert len(fresh.get("download_button")) == 3
    fresh.text_input(key="report_search").set_value("NO MATCH").run()
    assert not fresh.get("download_button")


def test_scenario_validation_and_new_state_does_not_delete_saved_records(app):
    from gsreview.presentation.persistence import new_scenario
    import streamlit as st
    with pytest.raises(ValidationError):
        app.persistence.save_scenario(app.test_admin, "", state(observations()))
    with pytest.raises(ValidationError):
        app.persistence.save_scenario(app.test_admin, "Case", {"active_scenario": "external"})
    app.persistence.save_scenario(app.test_admin, "Case", state(observations()))
    st.session_state.scenario_saved_id = "old"
    new_scenario("external")
    assert "scenario_saved_id" not in st.session_state
    assert len(app.persistence.listing(app.test_admin, "scenario")) == 1


def controls_app(c):
    from gsreview.application.scenarios import SCENARIOS
    from gsreview.presentation.persistence import scenario_controls
    import streamlit as st
    scenario_controls(c, c.test_admin, SCENARIOS[st.session_state.get("active_scenario", "external")])


def test_save_open_new_controls_and_case_ownership(app):
    at = AppTest.from_function(controls_app, args=(app,)).run()
    at.button(key="saved_case_save").click().run()
    assert at.error
    for key, value in state(observations()).items():
        at.session_state[key] = value
    at.run()
    at.text_input(key="scenario_name").set_value("Caso UI")
    at.button(key="saved_case_save").click().run()
    assert not at.exception and at.success
    saved_id = at.session_state["scenario_saved_id"]
    at.button(key="saved_case_new").click().run()
    assert "jh_records" not in at.session_state
    at.button(key="saved_case_open").click().run()
    assert not at.exception and at.session_state["scenario_saved_id"] == saved_id
    assert at.text_input(key="scenario_name").value == "Caso UI"
    _, token, _ = engineer(app)
    with pytest.raises(ValidationError):
        app.persistence.save_scenario(token, "Forged", state(observations()) | {"scenario_saved_id": saved_id})
    with pytest.raises(ValidationError):
        app.persistence.save_scenario(app.test_admin, "Wrong family", {"active_scenario": "external", "jh_records": observations()})


def test_storage_failure_keeps_draft_and_new_version_archives_original(app, monkeypatch):
    frame = observations()
    at = AppTest.from_function(report_app, args=(app, frame)).run()
    at.text_area(key="report_conclusions").set_value("Original")
    save = app.persistence.save_report
    def unavailable(*args, **kwargs):
        raise OSError("Simulated disk unavailable")
    monkeypatch.setattr(app.persistence, "save_report", unavailable)
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    assert not at.exception and at.error
    assert at.text_area(key="report_conclusions").value == "Original"
    monkeypatch.setattr(app.persistence, "save_report", save)
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    original = app.persistence.listing(app.test_admin, "report")[0]
    at.button(key="report_new_version").click().run()
    assert not at.exception and at.session_state["report_parent"] == original["id"]
    assert at.get("tab_container")[0].proto.tab_container.default_tab_index == 0
    at.text_area(key="report_conclusions").set_value("Revisión nueva")
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    assert not at.exception and len(app.persistence.listing(app.test_admin, "report")) == 2
    assert app.persistence.listing(app.test_admin, "report")[0] == original
    at.date_input(key="report_after").set_value(date(2030, 1, 1)).run()
    assert not at.exception
    assert not any(x.label == "Descargar JSON guardado" for x in at.get("download_button"))


def john_henry_persistent_app(c):
    from gsreview.presentation.john_henry_workspace import render_john_henry_workspace
    render_john_henry_workspace(c, c.test_admin)


def test_generated_terrain_analysis_review_report_survive_reopening(app, small_terrain, monkeypatch):
    from gsreview.presentation import john_henry_workspace as workspace
    from gsreview.application.workflow import matching_scores, matching_forecast
    monkeypatch.setattr(workspace.components, "declare_component", lambda *a, **k: lambda **kw: None)
    at = AppTest.from_function(john_henry_persistent_app, args=(app,)).run()
    next(n for n in at.number_input if n.label == "Prismas simulados").set_value(4)
    next(n for n in at.number_input if n.label == "Días simulados").set_value(3)
    next(b for b in at.button if b.label == "Generar escenario sobre terreno real").click().run()
    assert not at.exception and at.session_state["jh_records"].prism_id.nunique() == 4
    frame = at.session_state["jh_records"]
    raw = {k: at.session_state[k] for k in ("jh_records", "jh_asset", "jh_slope_config", "scenario_jh_settings", "scenario_jh_valid")}
    raw["active_scenario"] = "john_henry"
    # Explicitly simulated scientific transport: this test makes no accuracy claim.
    scores = frame[["source_record_id", "prism_id", "timestamp"]].copy()
    scores["model_version"] = "simulated-test-only"
    scores["model_eligible"] = True
    scores["model_ineligibility_reason"] = ""
    scores["isolation_forest_score"] = .125
    scores["isolation_forest_marked_q99"] = pd.Series(False, index=scores.index, dtype="boolean")
    raw["scenario_science_result"] = {"scenario": "john_henry", "signature": data_version(frame), "scores": scores}
    raw["scenario_forecast_result"] = {"request": ("john_henry", data_version(frame), str(frame.prism_id.iloc[0]), 24, True),
        "cutoff": frame.timestamp.max().isoformat(), "future": pd.DataFrame({"q10": [1.], "q50": [2.], "q90": [3.],
            "timestamp": [frame.timestamp.max()+pd.Timedelta(hours=24)], "model": ["chronos2"]}),
        "metrics": pd.DataFrame(), "report": {"model_versions": {"chronos2": "simulated-test-only"}}}
    app.scenario_reviews.save(app.test_admin, "john_henry", frame, str(frame.prism_id.iloc[0]), frame.timestamp.max(),
        "simulated-test-only", "test-analysis", decision())
    saved = app.persistence.save_scenario(app.test_admin, "Instrumentación controlada", raw)
    reopened = {}
    restore_state(reopened, PersistenceService(app.auth).scenario(app.test_admin, saved["id"]))
    assert len(saved["reviews"]) == 1
    pd.testing.assert_frame_equal(matching_scores(reopened, "john_henry", frame)["scores"], scores)
    assert matching_forecast(reopened, "john_henry", frame)["future"].q50.iloc[0] == 2.
    def forbidden(*args, **kwargs):
        raise AssertionError("Reopening saved data must not execute models or instrumentation")
    monkeypatch.setattr(app.science, "anomalies", forbidden)
    monkeypatch.setattr(app.science, "forecasts", forbidden)
    monkeypatch.setattr(app.synthetic, "generate", forbidden)
    fresh = AppTest.from_function(john_henry_persistent_app, args=(app,))
    for key, value in reopened.items():
        fresh.session_state[key] = value
    fresh.run()
    assert not fresh.exception and fresh.session_state["scenario_jh_valid"]
    pd.testing.assert_frame_equal(fresh.session_state["jh_records"], frame)
    payload = report_payload(app.auth, app.scenario_reviews, app.test_admin, "john_henry", frame, reopened)
    report = app.persistence.save_report(app.test_admin, payload, "Prueba de archivo, sin interpretación geotécnica", "", "generated")
    assert report["snapshot"]["anomalies"][0]["isolation_forest_score"] == .125
    assert len(report["snapshot"]["human_reviews"]) == 1


def historical_report_app(c):
    from gsreview.presentation.persistence import reports
    from gsreview.application.scenarios import SCENARIOS
    reports(c, c.test_admin, SCENARIOS["historical"], None)


def test_historical_export_can_be_archived_without_changing_frozen_data(app):
    at = AppTest.from_function(historical_report_app, args=(app,), default_timeout=20).run()
    at.text_area(key="report_conclusions").set_value("Revisión del histórico")
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    assert not at.exception and not at.error
    saved = app.persistence.listing(app.test_admin, "report")[0]
    assert saved["snapshot"]["historical_export"]["manifest_hash"]
    assert app.reader.verify() == 17

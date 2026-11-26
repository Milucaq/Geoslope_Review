"""End-to-end scenario UX and independent durable reviews, on controlled data."""

import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool
from streamlit.testing.v1 import AppTest

from conftest import engineer
from gsreview.application.workflow import (
    data_version, at_cutoff, quality_summary, analysis_context, context_id,
    matching_forecast, matching_scores, scenario_frame,
)
from gsreview.application.scenario_review import ScenarioReviewService
from gsreview.application.scenario_reports import report_payload, report_html
from gsreview.analytics.experiment_summary import summarize_experiments
from gsreview.domain.rules import ReviewInput, ValidationError, AccessDenied
from gsreview.infrastructure.scenario_reviews import ScenarioReviews


def observations():
    rows = []
    for prism in ("P1", "P2"):
        for i, date in enumerate(pd.date_range("2026-01-01", periods=60, freq="6h", tz="UTC")):
            rows.append({"source_record_id": f"{prism}-{i}", "prism_id": prism, "timestamp": date,
                         "easting": 100.+i/1000, "northing": 200., "rl": 10.,
                         "movement_rate_mm_per_day": 0., "elapsed_hours": i*6,
                         "reported_3d_movement_mm": 2+.5*i+np.sin(i)})
    return pd.DataFrame(rows)


def decision(version=0, status="Revisado", comment="Revisar el contexto instrumental; no diagnóstico."):
    return ReviewInput(status=status, relevance="Indeterminado", comment=comment,
                       quality_comment="Solicitar inspección", follow_up="Verificar datos", expected_version=version)


def test_data_versions_scope_cutoffs_and_missing_quality():
    frame = observations()
    signature = data_version(frame)
    assert signature == data_version(frame.sample(frac=1, random_state=1))
    changed = frame.copy()
    changed.loc[0, "easting"] += 1
    assert data_version(changed) != signature
    assert len(at_cutoff(frame, frame.timestamp.min())) == 2
    assert quality_summary(None)["prisms"] == 0
    assert quality_summary(frame)["known"] == 120
    assert quality_summary(frame.drop(columns="reported_3d_movement_mm"))["missing"] == 120
    context = analysis_context(frame, "external", "P1", frame.timestamp.max())
    assert len(context_id(context)) == 64
    for scenario, prism, cutoff in [("historical", "P1", frame.timestamp.max()),
                                    ("external", "foreign", frame.timestamp.max()),
                                    ("external", "P1", "2000-01-01")]:
        with pytest.raises(ValidationError):
            analysis_context(frame, scenario, prism, cutoff)
    with pytest.raises(ValidationError):
        at_cutoff(frame, pd.NaT)
    state = {"scenario_external_frame": frame, "jh_records": frame}
    assert scenario_frame(state, "external") is frame
    assert scenario_frame(state, "john_henry") is None
    state["scenario_jh_valid"] = True
    assert scenario_frame(state, "john_henry") is frame


def test_saved_results_match_data_prism_scenario_and_cutoff():
    frame = observations()
    cutoff = frame.timestamp.max().isoformat()
    score = {"scenario": "external", "signature": data_version(frame), "scores": frame}
    forecast = {"request": ("external", data_version(frame), "P1", 24, False, cutoff), "cutoff": cutoff}
    state = {"scenario_science_result": score, "scenario_forecast_result": forecast}
    assert matching_scores(state, "external", frame) is score
    assert matching_forecast(state, "external", frame, "P1", cutoff) is forecast
    assert not matching_forecast(state, "john_henry", frame)
    assert not matching_forecast(state, "external", frame, "P2")
    assert not matching_forecast(state, "external", frame, "P1", frame.timestamp.min())
    assert not matching_scores(state, "john_henry", frame)
    trace = forecast | {"report": {"model_versions": {"chronos2": "test-revision", "linear": "1"}}}
    at = AppTest.from_function(review_trace_app, args=(frame, trace)).run()
    assert not at.exception and not at.error
    assert "test-revision" in at.session_state["trace_probe"]["model_version"]
    assert at.session_state["trace_probe"]["data_version"] == data_version(frame)


def review_trace_app(frame, forecast):
    import streamlit as st
    from gsreview.presentation.workflow import review_context
    from gsreview.application.scenarios import SCENARIOS
    st.session_state.scenario_forecast_result = forecast
    st.session_state.trace_probe = review_context(frame, SCENARIOS["external"])


def test_reviews_are_durable_versioned_user_and_dataset_isolated(app):
    frame = observations()
    before = app.store.list("episode_reviews")
    cutoff = frame.timestamp.max()
    service = app.scenario_reviews
    assert service.listing(app.test_admin, "external", frame) == []
    assert not service.repository.path.exists()  # Read-only dashboard does not create a database.
    saved = service.save(app.test_admin, "external", frame, "P1", cutoff, "model-test", "analysis-test", decision())
    assert saved["version"] == 1
    reopened = ScenarioReviewService(app.auth, service.repository.path)
    assert reopened.listing(app.test_admin, "external", frame) == [saved]
    with pytest.raises(ValidationError, match="cambió"):
        reopened.save(app.test_admin, "external", frame, "P1", cutoff, "model-test", "analysis-test", decision())
    reopened.save(app.test_admin, "external", frame, "P1", cutoff, "model-test", "analysis-test", decision(1, "Requiere más información"))
    assert [r["version"] for r in service.listing(app.test_admin, "external", frame)] == [1, 2]
    _, token, _ = engineer(app)
    assert service.listing(token, "external", frame) == []
    assert service.listing(app.test_admin, "john_henry", frame) == []
    changed = frame.copy()
    changed.loc[0, "reported_3d_movement_mm"] += 10
    assert service.listing(app.test_admin, "external", changed) == []
    assert app.store.list("episode_reviews") == before
    assert app.reader.verify() == 17
    with pytest.raises(AccessDenied):
        service.listing("invalid", "external", frame)
    with pytest.raises(ValidationError):
        service.listing(app.test_admin, "historical", frame)
    with pytest.raises(ValidationError):
        service.save(app.test_admin, "external", frame, "P1", cutoff, "m", "a", decision(comment=""))


def test_review_schema_rejects_unknown_versions_and_history_is_immutable(app, tmp_path):
    frame = observations()
    app.scenario_reviews.save(app.test_admin, "external", frame, "P1", frame.timestamp.max(), "m", "a", decision())
    engine = create_engine("sqlite:///"+str(app.scenario_reviews.repository.path), poolclass=NullPool)
    try:
        for command in ("UPDATE scenario_reviews SET actor='other'", "DELETE FROM scenario_reviews"):
            with pytest.raises(IntegrityError, match="append-only"):
                with engine.begin() as c:
                    c.execute(text(command))
        with engine.begin() as c:
            assert c.exec_driver_sql("PRAGMA user_version").scalar() == 1
            c.exec_driver_sql("PRAGMA user_version=2")
        with pytest.raises(ValidationError, match="no soportado"):
            app.scenario_reviews.listing(app.test_admin, "external", frame)
    finally:
        engine.dispose()
    unknown = tmp_path / "unrecognized.db"
    other = create_engine("sqlite:///"+str(unknown), poolclass=NullPool)
    try:
        with other.begin() as c:
            c.exec_driver_sql("CREATE TABLE unrelated (id INT)")
        with pytest.raises(ValidationError, match="no reconocida"):
            ScenarioReviews(unknown).records("test", "external", "hash")
    finally:
        other.dispose()


def test_reports_include_owned_reviews_escape_html_and_reject_stale_results(app):
    frame = observations()
    app.scenario_reviews.save(app.test_admin, "external", frame, "P1", frame.timestamp.max(), "m", "a",
                              decision(comment="<script>alert('x')</script>"))
    payload = report_payload(app.auth, app.scenario_reviews, app.test_admin, "external", frame, {})
    assert payload["data_version"] == data_version(frame)
    assert not payload["anomalies"] and not payload["forecast"]
    assert len(payload["human_reviews"]) == 1
    html = report_html(payload)
    assert "<script>" not in html and "&lt;script&gt;" in html
    json.dumps(payload, allow_nan=False)
    with pytest.raises(ValidationError):
        report_payload(app.auth, app.scenario_reviews, app.test_admin, "historical", frame, {})


def test_experimental_summary_uses_actual_denominators_and_keeps_reference_separate(tmp_path):
    source = Path(__file__).resolve().parents[1] / "reports/science/synthetic_backtest.csv"
    summary, comparison = summarize_experiments(source)
    assert len(summary) == 9 and len(comparison) == 6
    assert comparison.chronos_lower_mae.all() and comparison.chronos_lower_rmse.all()
    week = summary.loc[summary.model.eq("chronos2") & summary.horizon_hours.eq(168)].iloc[0]
    assert week.coverage == pytest.approx(2/3)
    assert week.observed_targets == 84
    malformed = pd.read_csv(source)
    for case in (malformed.drop(columns="fold"), pd.concat([malformed, malformed.iloc[:1]]),
                 malformed.assign(data_origin="field"), malformed.assign(observed_targets=0),
                 malformed.loc[malformed.model.ne("linear")], malformed.assign(interval_coverage=2)):
        path = tmp_path / "bad.csv"
        case.to_csv(path, index=False)
        with pytest.raises(ValidationError):
            summarize_experiments(path)


def test_authenticated_scenario_flow_from_data_to_durable_decision_and_download(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    frame = observations()
    uploaded = SimpleNamespace(name="controlled.csv", type="text/csv", getvalue=lambda: frame.to_csv(index=False).encode())
    from gsreview.presentation import external_spatial_workspace
    monkeypatch.setattr(external_spatial_workspace.st, "file_uploader", lambda *a, **k: uploaded)
    at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=30)
    at.session_state["token"] = app.test_admin
    at.run()
    at.selectbox(key="scenario_selector").select("external").run()
    assert any("No se muestran indicadores históricos" in x.value for x in at.info)
    at.button(key="flow_prepare").click().run()
    assert not at.exception and not at.error
    at.button(key="flow_external_view").click().run()
    at.selectbox(key="hu110_prism").select("P2").run()
    assert not at.exception and not at.error
    assert at.session_state["scenario_selected_prism"] == "P2"
    at.button(key="detail_analyze_external").click().run()
    assert at.selectbox(key="science_prism_external").value == "P2"
    # Baselines are available on this path; inference numerical correctness is covered separately.
    at.button(key="science_continue_external").click().run()
    assert any(t.value == "Revisión del escenario" for t in at.title)
    next(t for t in at.text_area if t.label == "Observaciones del especialista").set_value("Solicito verificación de referencia instrumental.")
    next(s for s in at.selectbox if s.label == "Estado de revisión humana").select("Requiere más información")
    next(b for b in at.button if b.label == "Guardar decisión").click().run()
    assert not at.exception and not at.error
    assert any("Decisión guardada" in x.value for x in at.success)
    at.button(key="flow_report").click().run()
    assert not at.exception and not at.error
    assert not at.get("download_button")  # Exports require an immutable archived edition.
    at.text_area(key="report_conclusions").set_value("Solicito revisión instrumental; no diagnóstico de falla.")
    next(b for b in at.button if b.label == "Guardar reporte").click().run()
    assert not at.exception and not at.error
    assert len(at.get("download_button")) == 3
    at.button(key="report_view_detail").click().run()
    assert at.json
    at.button(key="rail_Inicio").click().run()
    assert at.session_state["active_scenario"] == "external"
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Prismas del escenario"] == "2" and metrics["Revisiones humanas guardadas"] == "1"
    assert metrics["Episodios candidatos"] == "No calculados"
    assert app.reader.verify() == 17


def detail_app(frame, scores, forecast, cutoff):
    import streamlit as st
    from gsreview.presentation.science import render_prism_detail
    st.session_state.scenario_science_result = scores
    st.session_state.scenario_forecast_result = forecast
    render_prism_detail(None, None, "external", frame, "P1", cutoff)


def test_prism_detail_combines_only_matching_measurement_model_and_scalar_forecast(monkeypatch):
    from gsreview.presentation import science
    frame = observations()
    cutoff = frame.timestamp.max()
    # Explicit transport/view fixture; these values are not scientific experiment results.
    scores = frame[["source_record_id", "prism_id", "timestamp"]].copy()
    scores["model_eligible"] = True
    scores["isolation_forest_score"] = .2
    scores["isolation_forest_marked_q99"] = False
    scores["model_ineligibility_reason"] = ""
    stored = {"scenario": "external", "signature": data_version(frame), "scores": scores}
    future = pd.DataFrame({"timestamp": pd.date_range(cutoff+pd.Timedelta(hours=6), periods=4, freq="6h"),
                           "model": "chronos2", "q10": 1., "q50": 2., "q90": 3.})
    forecast = {"request": ("external", data_version(frame), "P1", 24, True),
                "cutoff": cutoff.isoformat(), "future": future, "report": {"model_versions": {"chronos2": "test-double"}}}
    charts = []
    monkeypatch.setattr(science.st, "plotly_chart", lambda fig, **k: charts.append(fig))
    at = AppTest.from_function(detail_app, args=(frame, stored, forecast, cutoff)).run()
    assert not at.exception and not at.error
    assert any("Sin marca estadística" in x.value for x in at.markdown)
    assert any("Pronóstico disponible" in x.value for x in at.caption)
    chart = charts[-1]
    assert chart.data[0].connectgaps is False
    assert pd.to_datetime(chart.data[0].x, utc=True).max() <= cutoff
    assert chart.data[-1].line.dash == "dash"
    assert chart.data[-2].fill == "tonexty"
    assert pd.to_datetime(chart.data[-1].x, utc=True).min() > cutoff
    charts.clear()
    earlier = frame.timestamp.min()
    at = AppTest.from_function(detail_app, args=(frame, {}, forecast, earlier)).run()
    assert len(charts[-1].data) == 1
    assert not any("Pronóstico disponible" in x.value for x in at.caption)


def prediction_app(c, frame):
    from gsreview.presentation.science import render_anomalies
    render_anomalies(c, "test", "external", frame)


def test_unavailable_chronos_is_explicit_and_never_substituted(monkeypatch, tmp_path):
    from unittest.mock import Mock
    from gsreview.application.chronos import LocalChronos
    c = SimpleNamespace(app_root=tmp_path, science=SimpleNamespace(forecasts=Mock()))
    at = AppTest.from_function(prediction_app, args=(c, observations())).run()
    at.checkbox(key="science_chronos_external").check().run()
    assert any("no disponible" in x.value for x in at.info)
    at.button(key="science_forecast_external").click().run()
    assert not at.exception and any("no disponible" in x.value for x in at.error)
    c.science.forecasts.assert_not_called()
    monkeypatch.setenv("RENDER", "true")
    ready, message = LocalChronos(tmp_path).availability()
    assert not ready and "Render" in message


def test_two_browser_reviews_detect_conflict_and_drafts_do_not_cross_prisms(app, monkeypatch):
    monkeypatch.setenv("GEOSLOPE_RUNTIME", str(app.runtime))
    frame = observations()
    def browser():
        at = AppTest.from_file(str(app.app_root / "app.py"), default_timeout=30)
        at.session_state["token"] = app.test_admin
        at.session_state["scenario_owner"] = app.test_admin
        at.session_state["active_scenario"] = "external"
        at.session_state["scenario_external_frame"] = frame
        at.session_state["current_page"] = "Bandeja de revisión"
        return at.run()
    first, second = browser(), browser()
    def submit(at, comment):
        next(x for x in at.text_area if x.label == "Observaciones del especialista").set_value(comment)
        next(x for x in at.selectbox if x.label == "Estado de revisión humana").select("Revisado")
        return next(x for x in at.button if x.label == "Guardar decisión").click().run()
    submit(second, "Decisión de la segunda pestaña")
    submit(first, "Borrador obsoleto de la primera pestaña")
    assert any("cambió" in x.value for x in first.error)
    assert len(app.scenario_reviews.listing(app.test_admin, "external", frame)) == 1
    first.button(key="scenario_review_reload").click().run()
    assert next(x for x in first.text_area if x.label == "Observaciones del especialista").value == "Decisión de la segunda pestaña"
    submit(first, "Actualización tras recargar")
    assert not first.exception and not first.error
    assert len(app.scenario_reviews.listing(app.test_admin, "external", frame)) == 2
    first.selectbox(key="scenario_review_prism").select("P2").run()
    assert next(x for x in first.text_area if x.label == "Observaciones del especialista").value == ""


def missing_position_app(frame):
    from gsreview.presentation.science import render_prism_detail
    render_prism_detail(None, None, "john_henry", frame, "P1", frame.timestamp.max())


def test_prism_detail_keeps_last_valid_coordinates_when_measurement_is_missing(monkeypatch):
    from gsreview.presentation import science
    frame = observations().loc[lambda data: data.prism_id.eq("P1")].head(2).copy()
    frame["model_eligible"] = [True, False]
    frame.loc[frame.index[-1], ["easting", "northing", "rl"]] = 999.
    frame.loc[frame.index[-1], "reported_3d_movement_mm"] = np.nan
    output = []
    monkeypatch.setattr(science.st, "write", lambda *args, **kwargs: output.extend(args))
    at = AppTest.from_function(missing_position_app, args=(frame,)).run()
    assert not at.exception and not at.error
    coordinates = next(item for item in output if isinstance(item, dict) and "easting" in item)
    assert coordinates["easting"] == "100.0" and coordinates["northing"] == "200.0"
    assert coordinates["rl"] == "10.0"
    assert any("magnitud escalar ausente" in x.value for x in at.caption)

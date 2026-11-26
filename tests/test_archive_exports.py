"""Archived exports use saved evidence, never a live model or mutable scenario."""

import copy
import io
import json

import pandas as pd
from pypdf import PdfReader
from streamlit.testing.v1 import AppTest

from gsreview.application.scenario_reports import report_payload
from gsreview.application.workflow import data_version
from gsreview.infrastructure.archive_pdf import archive_pdf
from gsreview.infrastructure.store import Store, workspace_records
from test_durable_workspace import controls_app
from test_phase_c_workflow import observations, decision


def saved_evidence(app):
    """Small, explicitly simulated scientific result transport for PDF acceptance."""
    frame = observations()
    scores = frame.groupby("prism_id").tail(1)[["source_record_id", "prism_id", "timestamp"]].copy()
    scores["model_version"] = "simulated-test-only"
    scores["model_eligible"] = True
    scores["isolation_forest_score"] = [None, .125]
    scores["isolation_forest_marked_q99"] = [None, False]
    cutoff = frame.timestamp.max().isoformat()
    future = pd.DataFrame({"model": ["chronos2"], "timestamp": [frame.timestamp.max()+pd.Timedelta(hours=24)],
                           "q10": [1.25], "q50": [2.5], "q90": [3.75]})
    metrics = pd.DataFrame({"model": ["chronos2"], "fold": [1], "cutoff": [cutoff], "mae_mm": [1.25],
                            "rmse_mm": [2.5], "interval_coverage": [.5]})
    state = {"scenario_science_result": {"scenario": "external", "signature": data_version(frame), "scores": scores},
             "scenario_forecast_result": {"request": ("external", data_version(frame), "P1", 24, True),
                "future": future, "metrics": metrics, "cutoff": cutoff,
                "report": {"model_versions": {"chronos2": "simulated-test-only"}}}}
    app.scenario_reviews.save(app.test_admin, "external", frame, "P1", cutoff, "simulated-test-only", "test", decision())
    return report_payload(app.auth, app.scenario_reviews, app.test_admin, "external", frame, state)


def test_pdf_preserves_saved_quantiles_notes_versions_and_absent_values(app, monkeypatch, tmp_path):
    payload = saved_evidence(app)
    original = app.persistence.save_report(app.test_admin, payload, "Conclusión <script>texto</script> & revisión α",
        "Observación con acentos y saltos.\n"*100, "pdf-one")
    before = copy.deepcopy(original)
    def forbidden(*args, **kwargs):
        raise AssertionError("Export must not invoke AI or generate new measurements")
    monkeypatch.setattr(app.science, "anomalies", forbidden)
    monkeypatch.setattr(app.science, "forecasts", forbidden)
    monkeypatch.setattr(app.synthetic, "generate", forbidden)
    pdf = archive_pdf(original)
    path = tmp_path / "archived.pdf"
    path.write_bytes(pdf)
    reader = PdfReader(io.BytesIO(pdf))
    text = "\n".join(page.extract_text() for page in reader.pages)
    assert pdf.startswith(b"%PDF-") and len(reader.pages) >= 3
    for value in ("Conclusión", "<script>texto</script>", "simulated-test-only", "0.125", "1.25", "2.5", "3.75",
                  "No disponible", "SHA256", "Revisiones humanas", original["id"]):
        assert value in text
    assert all("Página" in page.extract_text() for page in reader.pages)
    assert original == before
    payload["forecast"][0]["q50"] = 999
    archived = app.persistence.listing(app.test_admin, "report")[0]
    assert archived == before
    assert text == "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(archive_pdf(archived))).pages)


def test_additive_migration_preserves_existing_authentication_and_historical_reviews(app):
    # Only the fixture's temporary database simulates a pre-D.1 installation.
    originals = {name: app.store.list(name) for name in ("users", "episode_reviews", "data_imports")}
    workspace_records.drop(app.store.engine)
    reopened = Store(app.store.path)
    assert reopened.list("workspace_records") == []
    for name, rows in originals.items():
        assert reopened.list(name) == rows
    assert app.auth.authorize(app.test_admin, "read")["id"] == originals["users"][0]["id"]
    reopened.engine.dispose()
    assert app.reader.verify() == 17


def test_render_notice_does_not_claim_durable_storage(app, monkeypatch):
    monkeypatch.setenv("RENDER", "true")
    at = AppTest.from_function(controls_app, args=(app,)).run()
    assert not at.exception
    assert any("Render" in message.value and "almacenamiento temporal" in message.value for message in at.warning)
    assert not any("almacenamiento local de esta instalación" in message.value for message in at.caption)


def test_pdf_snapshot_is_independent_of_subsequent_report_editions(app):
    payload = saved_evidence(app)
    first = app.persistence.save_report(app.test_admin, payload, "Edición original", "", "first-pdf")
    payload["forecast"][0]["q50"] = 7.5
    second = app.persistence.save_report(app.test_admin, payload, "Segunda edición", "", "second-pdf", first["id"])
    saved = {r["id"]: r for r in app.persistence.listing(app.test_admin, "report")}
    assert saved[first["id"]]["snapshot"]["forecast"][0]["q50"] == 2.5
    assert saved[second["id"]]["snapshot"]["forecast"][0]["q50"] == 7.5
    assert saved[second["id"]]["parent"] == first["id"]
    # JSON is the complete immutable source of the human-readable PDF.
    assert json.loads(json.dumps(saved[first["id"]])) == first

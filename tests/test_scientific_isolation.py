"""Numerical equivalence, temporal causality and trust boundaries for inference."""

from pathlib import Path
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from gsreview.analytics.artifacts import FrozenReader
from gsreview.analytics.causal_features import TARGET, causal_features
from gsreview.analytics.isolation import FrozenIsolationForest
from gsreview.analytics.synthetic import SyntheticConfig, generate_synthetic_monitoring_data
from gsreview.application.science import ScienceService
from gsreview.application.csv_import import validate_csv
from gsreview.domain.rules import AccessDenied, ValidationError


@pytest.fixture(scope="module")
def trusted_model():
    root = Path(__file__).resolve().parents[1]
    reader = FrozenReader(root / "ci_artifacts", root / "config/frozen_manifest.json")
    return FrozenIsolationForest(reader)


def measurements():
    return generate_synthetic_monitoring_data(SyntheticConfig(
        n_prisms=4, days=15, cadence_hours=6, seed=13,
    ))["records"]


def test_all_7178_historical_rows_reproduce_features_scores_and_unknowns(trusted_model):
    report = trusted_model.validation
    assert report["rows"] == 7178 and report["features"] == 17
    assert report["max_feature_absolute_error"] < 1e-12
    assert report["max_score_absolute_error"] < 1e-12
    assert report["eligibility_and_q99_marks_exact"]
    assert trusted_model.reader.verify() == 17


def test_new_inference_is_causal_isolated_and_does_not_fit(trusted_model, monkeypatch):
    raw = measurements()
    before = raw.copy(deep=True)
    monkeypatch.setattr(trusted_model.pipeline, "fit", Mock(side_effect=AssertionError("no training")))
    features = causal_features(raw)
    cutoff = raw.timestamp.sort_values().iloc[len(raw)//2]
    prefix = raw.loc[raw.timestamp.le(cutoff)].sample(frac=1, random_state=2)
    partial = causal_features(prefix)
    pd.testing.assert_frame_equal(
        features.loc[features.timestamp.le(pd.Timestamp(cutoff, tz="UTC"))].reset_index(drop=True), partial,
    )
    scored = trusted_model.infer(raw)
    missing = scored.loc[~scored.model_eligible]
    assert len(missing) > 0 and scored.model_eligible.any()
    assert missing.isolation_forest_score.isna().all()
    assert missing.isolation_forest_marked_q99.isna().all()
    # The supplied synthetic scores/rates cannot become model inputs.
    altered = raw.copy()
    altered["movement_rate_mm_per_day"] = 1e9
    altered["isolation_forest_score"] = 1e9
    pd.testing.assert_frame_equal(scored, trusted_model.infer(altered))
    one_prism = raw.loc[raw.prism_id.eq(raw.prism_id.iloc[0])]
    only = trusted_model.infer(one_prism)
    pd.testing.assert_frame_equal(
        scored.loc[scored.prism_id.eq(raw.prism_id.iloc[0])].reset_index(drop=True), only,
    )
    pd.testing.assert_frame_equal(raw, before)
    trusted_model.pipeline.fit.assert_not_called()


@pytest.mark.parametrize("case", ["target", "empty", "id", "date", "inf", "text", "duplicate", "time"])
def test_invalid_measurements_are_rejected_before_inference(case):
    frame = measurements().head(4).copy()
    if case == "target":
        frame = frame.drop(columns=TARGET)
    elif case == "empty":
        frame = frame.iloc[:0]
    elif case == "id":
        frame.loc[frame.index[0], "prism_id"] = ""
    elif case == "date":
        frame.loc[frame.index[0], "timestamp"] = pd.NaT
    elif case in {"inf", "text"}:
        frame[TARGET] = np.inf if case == "inf" else "not-numeric"
    elif case == "duplicate":
        frame["source_record_id"] = "duplicate"
    else:
        frame["timestamp"] = frame.timestamp.iloc[0]
    with pytest.raises(ValidationError):
        causal_features(frame)


def test_legacy_csv_remains_visualizable_but_scalar_is_never_integrated():
    header = "source_record_id,prism_id,timestamp,easting,northing,rl,movement_rate_mm_per_day,elapsed_hours"
    row = "R1,P1,2026-01-01,1,2,3,9999,24"
    legacy = validate_csv((header + "\n" + row).encode())
    with pytest.raises(ValidationError, match="escalar"):
        causal_features(legacy)
    scalar = validate_csv((header + "," + TARGET + "\n" + row + ",1.25").encode())
    assert scalar[TARGET].iloc[0] == 1.25
    empty = validate_csv((header + "," + TARGET + "\n" + row + ",").encode())
    assert empty[TARGET].isna().all()
    for value in ("inf", "oops", "NaN"):
        with pytest.raises(ValidationError, match="escalar"):
            validate_csv((header + "," + TARGET + "\n" + row + "," + value).encode())


def test_artifacts_and_versions_fail_closed_before_unpickling(trusted_model, monkeypatch):
    from gsreview.analytics import isolation

    load = Mock(side_effect=AssertionError("untrusted load"))
    monkeypatch.setattr(isolation._TrustedUnpickler, "load", load)
    monkeypatch.setattr(isolation, "version", lambda _: "incompatible")
    with pytest.raises(ValidationError, match="versión incompatible"):
        FrozenIsolationForest(trusted_model.reader)
    load.assert_not_called()
    reader = Mock()
    reader.verify.side_effect = ValidationError("Artefacto alterado")
    with pytest.raises(ValidationError, match="alterado"):
        FrozenIsolationForest(reader)
    load.assert_not_called()


def test_science_service_enforces_auth_and_scenario_and_preserves_simulated_labels(trusted_model):
    auth = Mock()
    auth.authorize.side_effect = AccessDenied("denied")
    service = ScienceService(auth, trusted_model.reader)
    with pytest.raises(AccessDenied):
        service.anomalies("invalid", "external", measurements())
    assert service._model is None
    auth.authorize.side_effect = None
    service._model = trusted_model
    for scenario in ("historical", "untrusted"):
        with pytest.raises(ValidationError):
            service.anomalies("test", scenario, measurements())
    raw = measurements()
    original = raw.copy(deep=True)
    scores, report = service.anomalies("test", "john_henry", raw)
    assert set(scores.scenario_id) == {"john_henry"}
    assert set(scores.data_origin) == {"synthetic"}
    assert set(scores.inference_origin) == {"frozen_isolation_forest"}
    assert "causal_state" not in scores
    pd.testing.assert_frame_equal(raw, original)
    assert report == trusted_model.validation


def test_constant_missing_gaps_and_insufficient_history_never_invent_scores(trusted_model):
    raw = measurements().iloc[:80].copy()
    raw[TARGET] = 1.
    assert not trusted_model.infer(raw).model_eligible.any()  # MAD=0 has no z-score.
    raw[TARGET] = np.nan
    assert trusted_model.infer(raw).isolation_forest_score.isna().all()
    raw = measurements().head(2)
    raw.loc[raw.index[-1], "timestamp"] = raw.timestamp.iloc[0] + pd.Timedelta(days=20)
    result = trusted_model.infer(raw)
    assert result.isolation_forest_score.isna().all()
    assert "hueco prolongado" in result.model_ineligibility_reason.iloc[-1]


def test_new_inference_cannot_use_a_model_before_its_training_boundary(trusted_model):
    raw = measurements()
    raw["timestamp"] -= pd.Timedelta(days=20*365)
    result = trusted_model.infer(raw)
    assert not result.model_available_at_observation.any()
    assert not result.model_eligible.any()
    assert result.isolation_forest_score.isna().all()
    assert result.isolation_forest_marked_q99.isna().all()
    assert result.model_ineligibility_reason.str.contains("modelo no disponible").all()


def science_app(c, frame):
    import streamlit as st
    from gsreview.presentation.science import render_anomalies

    current = st.session_state.get("test_frame", frame)
    render_anomalies(c, "test", "external", current)


def test_scientific_panel_runs_real_inference_and_baselines_then_hides_stale_results(trusted_model):
    from types import SimpleNamespace
    from streamlit.testing.v1 import AppTest

    service = ScienceService(Mock(), trusted_model.reader)
    service._model = trusted_model
    raw = measurements()
    at = AppTest.from_function(science_app, args=(SimpleNamespace(science=service), raw), default_timeout=30).run()
    at.button(key="science_run_external").click().run()
    assert not at.exception and not at.error
    assert at.session_state["scenario_science_result"]["validation"]["rows"] == 7178
    assert len(at.dataframe) == 1
    at.button(key="science_forecast_external").click().run()
    assert not at.exception and not at.error
    result = at.session_state["scenario_forecast_result"]
    assert set(result["future"].model) == {"persistence", "linear"}
    assert result["report"]["runtime"]["engine"] == "baselines_only"
    assert len(at.dataframe) == 3
    # A replacement file with the same prism IDs cannot inherit displayed scores.
    changed = raw.copy()
    changed[TARGET] += 100
    at.session_state["test_frame"] = changed
    at.run()
    assert not at.dataframe
    service.anomalies = Mock(side_effect=ValidationError("test blocked"))
    at.button(key="science_run_external").click().run()
    assert any("test blocked" in e.value for e in at.error)
    assert "scenario_science_result" not in at.session_state
    service.forecasts = Mock(side_effect=ValidationError("test frequency blocked"))
    at.button(key="science_forecast_external").click().run()
    assert any("frequency blocked" in e.value for e in at.error)
    assert "scenario_forecast_result" not in at.session_state
    at.session_state["test_frame"] = changed.drop(columns=TARGET)
    at.run()
    assert not at.button and not at.dataframe

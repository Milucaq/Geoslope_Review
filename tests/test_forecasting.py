"""Temporal contracts and numerical reference forecasts; no model downloads in CI."""

import numpy as np
import pandas as pd
import pytest

from gsreview.analytics.causal_features import TARGET
from gsreview.analytics.forecasting import (
    regular_series, baseline_quantiles, forecast_and_evaluate, validate_quantiles,
)
from gsreview.domain.rules import ValidationError


def series(n=120):
    return pd.DataFrame({"prism_id": "P1", "timestamp": pd.date_range("2026-01-01", periods=n, freq="6h"),
                         TARGET: 2 + .5*np.arange(n, dtype=float)})


@pytest.mark.parametrize("hours,steps", [(24, 4), (72, 12), (168, 28)])
def test_horizons_follow_real_frequency_and_linear_reference_is_exact(hours, steps):
    data, step, actual = regular_series(series(), "P1", hours)
    assert actual == steps and step*steps == pd.Timedelta(hours=hours)
    forecasts, metrics = forecast_and_evaluate(data, step, actual)
    linear = forecasts.loc[forecasts.model.eq("linear")]
    np.testing.assert_allclose(linear.q50, 2+.5*np.arange(120, 120+steps))
    assert len(metrics) == 6 and set(metrics.model) == {"persistence", "linear"}
    assert metrics.loc[metrics.model.eq("linear"), "mae_mm"].max() < 1e-12
    assert metrics.loc[metrics.model.eq("linear"), "rmse_mm"].max() < 1e-12
    assert forecasts.timestamp.max()-data.timestamp.max() == pd.Timedelta(hours=hours)
    persistence = forecasts.loc[forecasts.model.eq("persistence")]
    np.testing.assert_allclose(persistence.q50, series()[TARGET].iloc[-1])


@pytest.mark.parametrize("case", ["short", "unknown", "duplicate", "irregular", "infinite", "horizon", "fractional"])
def test_unsafe_series_are_blocked_without_silent_resampling(case):
    frame, horizon = series(), 24
    if case == "short":
        frame = frame.head(10)
    elif case == "unknown":
        frame[TARGET] = np.nan
    elif case == "duplicate":
        frame.loc[1, "timestamp"] = frame.timestamp.iloc[0]
    elif case == "irregular":
        frame.loc[10, "timestamp"] += pd.Timedelta(minutes=1)
    elif case == "infinite":
        frame[TARGET] = np.inf
    elif case == "horizon":
        horizon = 48
    else:
        frame["timestamp"] = pd.date_range("2026-01-01", periods=len(frame), freq="10h")
    with pytest.raises(ValidationError):
        regular_series(frame, "P1", horizon)


def test_quantile_shapes_order_and_finiteness_are_enforced():
    for q in (np.ones((3, 2)), [[3, 2, 1]], [[np.nan, 2, 3]], [[1, np.inf, 3]]):
        with pytest.raises(ValidationError):
            validate_quantiles(q, 1)


def test_backtesting_engine_sees_only_prefixes_and_missing_truth_is_not_scored():
    data, step, steps = regular_series(series(), "P1", 24)
    data.loc[108, TARGET] = np.nan

    class RecordingEngine:
        def predict_many(self, jobs):
            self.jobs = jobs
            return [np.tile([0., 10., 100.], (job["steps"], 1)) for job in jobs]

    engine = RecordingEngine()
    forecasts, metrics = forecast_and_evaluate(data, step, steps, engine)
    assert set(forecasts.model) == {"persistence", "linear", "chronos2"}
    assert [len(job["history"]) for job in engine.jobs] == [108, 112, 116, 120]
    for job in engine.jobs:
        np.testing.assert_allclose(job["history"], data[TARGET].iloc[:len(job["history"])], equal_nan=True)
    assert metrics.loc[metrics.fold.eq(1), "observed_targets"].eq(3).all()
    chronological = metrics.cutoff.drop_duplicates().tolist()
    assert chronological == sorted(chronological)
    # A future perturbation cannot alter any earlier fold forecast/calibration.
    original = baseline_quantiles(data[TARGET].iloc[:108], 4, "linear")
    data.loc[108:, TARGET] = 1e8
    np.testing.assert_allclose(original, baseline_quantiles(data[TARGET].iloc[:108], 4, "linear"), equal_nan=True)


def test_unknown_baseline_intervals_and_absent_folds_stay_unknown():
    data, step, steps = regular_series(series(25), "P1", 168)
    future, metrics = forecast_and_evaluate(data, step, steps)
    assert metrics.empty
    assert future.loc[future.timestamp.eq(future.timestamp.max()), ["q10", "q90"]].isna().all().all()
    assert np.isfinite(future.q50).all()
    with pytest.raises(ValidationError):
        baseline_quantiles([np.nan]*30, 4, "linear")
    with pytest.raises(ValidationError):
        baseline_quantiles([1, 2, 3, 4], 4, "invented")


def test_bad_worker_response_is_not_replaced_with_baseline_predictions():
    data, step, steps = regular_series(series(), "P1", 24)
    class Incomplete:
        def predict_many(self, jobs):
            return []
    with pytest.raises(ValidationError, match="incompleta"):
        forecast_and_evaluate(data, step, steps, Incomplete())

"""Scalar forecasts and chronological evaluation; no 3D or collapse inference."""

import numpy as np
import pandas as pd

from gsreview.analytics.causal_features import TARGET
from gsreview.domain.rules import ValidationError


HORIZONS = (24, 72, 168)


def regular_series(frame, prism, hours):
    if hours not in HORIZONS or TARGET not in frame:
        raise ValidationError("Horizonte o magnitud escalar no disponible.")
    data = frame.loc[frame.prism_id.eq(prism), ["timestamp", TARGET]].copy()
    try:
        data["timestamp"] = pd.to_datetime(data.timestamp, utc=True, errors="raise")
        data[TARGET] = pd.to_numeric(data[TARGET], errors="raise").astype(float)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Serie temporal inválida.") from exc
    data = data.sort_values("timestamp").reset_index(drop=True)
    if (len(data) < 24 or data.timestamp.isna().any()
            or data.timestamp.duplicated().any() or np.isinf(data[TARGET]).any()
            or data[TARGET].notna().sum() < 20):
        raise ValidationError("Se requieren 24 fechas distintas, al menos 20 magnitudes conocidas y sin infinitos.")
    intervals = np.diff(pd.DatetimeIndex(data.timestamp).asi8)
    if not np.all(intervals == intervals[0]) or intervals[0] <= 0:
        raise ValidationError("Frecuencia irregular: pronóstico bloqueado. No se interpola ni se rellena la serie.")
    step = pd.Timedelta(int(intervals[0]), unit="ns")
    quotient, remainder = divmod(pd.Timedelta(hours=hours).value, step.value)
    if remainder or not 1 <= quotient <= 1024:
        raise ValidationError("La frecuencia no permite representar exactamente el horizonte solicitado (máximo 1024 pasos).")
    return data, step, int(quotient)


def _point(values, steps, kind):
    values = np.asarray(values, dtype=float)
    valid = np.isfinite(values)
    if valid.sum() < 3:
        raise ValidationError("Historia conocida insuficiente para referencia temporal.")
    if kind == "persistence":
        return np.repeat(values[valid][-1], steps)
    if kind != "linear":
        raise ValidationError("Modelo de referencia desconocido.")
    x = np.arange(len(values), dtype=float)[valid]
    y = values[valid]
    xc = x-x.mean()
    slope = np.dot(xc, y-y.mean()) / np.dot(xc, xc)
    return y.mean() + slope*(np.arange(len(values), len(values)+steps)-x.mean())


def baseline_quantiles(history, steps, kind):
    """Horizon-specific rolling residual intervals using the training prefix only.

    These empirical intervals are descriptive and not guaranteed to attain 80%.
    If <8 calibration errors exist, interval bounds remain unknown (NaN).
    """
    history = np.asarray(history, dtype=float)
    point = _point(history, steps, kind)
    output = np.column_stack([np.full(steps, np.nan), point, np.full(steps, np.nan)])
    origins = np.arange(8, len(history))
    if not len(origins):
        return output
    # Prefix coefficients: equivalent to OLS, but avoid repeated polynomial fits.
    valid = np.isfinite(history)
    x = np.arange(len(history), dtype=float)
    count = np.cumsum(valid)[origins-1]
    sx = np.cumsum(np.where(valid, x, 0.))[origins-1]
    sy = np.cumsum(np.where(valid, history, 0.))[origins-1]
    sxx = np.cumsum(np.where(valid, x*x, 0.))[origins-1]
    sxy = np.cumsum(np.where(valid, x*history, 0.))[origins-1]
    denominator = count*sxx-sx*sx
    slope = np.divide(count*sxy-sx*sy, denominator,
                      out=np.full(len(origins), np.nan), where=denominator > 0)
    intercept = np.divide(sy-slope*sx, count, out=np.full(len(origins), np.nan), where=count > 0)
    last = pd.Series(history).ffill().to_numpy()[origins-1]
    for h in range(1, steps+1):
        known = origins+h-1 < len(history)
        target_index = origins[known]+h-1
        prediction = last[known] if kind == "persistence" else intercept[known]+slope[known]*target_index
        residual = history[target_index]-prediction
        residual = residual[np.isfinite(residual) & (count[known] >= 8)]
        if len(residual) >= 8:
            low, high = np.quantile(residual, [.1, .9])
            output[h-1, 0] = min(point[h-1], point[h-1]+low)
            output[h-1, 2] = max(point[h-1], point[h-1]+high)
    return output


def validate_quantiles(values, steps, allow_unknown=False):
    q = np.asarray(values, dtype=float)
    if (q.shape != (steps, 3) or not np.isfinite(q[:, 1]).all()
            or np.isinf(q).any() or (not allow_unknown and not np.isfinite(q).all())
            or np.any(q[:, 0] > q[:, 1]) or np.any(q[:, 1] > q[:, 2])):
        raise ValidationError("Cuantiles no finitos, cruzados o con forma incompatible.")
    return q


def forecast_and_evaluate(series, step, steps, engine=None, folds=3):
    """Nonoverlapping rolling-origin folds; every model sees identical prefixes.

    The optional engine accepts a batch of jobs so CPU weights load once per run.
    No calibrator/model sees validation suffixes while creating predictions.
    """
    values = series[TARGET].to_numpy(float)
    cutoffs = [i for i in range(len(values)-folds*steps, len(values), steps)
               if i >= 24 and np.isfinite(values[:i]).sum() >= 20]
    jobs = [{"history": values[:i].tolist(), "steps": steps} for i in cutoffs+[len(values)]]
    chronos = engine.predict_many(jobs) if engine is not None else None
    if chronos is not None and len(chronos) != len(jobs):
        raise ValidationError("Respuesta Chronos incompleta.")
    scores, forecasts = [], []
    for fold, cutoff in enumerate(cutoffs+[len(values)]):
        history = values[:cutoff].copy()
        predictions = {
            "persistence": baseline_quantiles(history, steps, "persistence"),
            "linear": baseline_quantiles(history, steps, "linear"),
        }
        if chronos is not None:
            predictions["chronos2"] = validate_quantiles(chronos[fold], steps)
        for model, raw in predictions.items():
            q = validate_quantiles(raw, steps, allow_unknown=model != "chronos2")
            if cutoff == len(values):
                for h in range(steps):
                    forecasts.append({"model": model, "timestamp": series.timestamp.iloc[-1]+(h+1)*step,
                                      "q10": q[h, 0], "q50": q[h, 1], "q90": q[h, 2]})
            else:
                truth = values[cutoff:cutoff+steps]
                known = np.isfinite(truth)
                intervals = known & np.isfinite(q[:, 0]) & np.isfinite(q[:, 2])
                error = truth[known]-q[known, 1]
                scores.append({"model": model, "fold": fold+1,
                               "cutoff": series.timestamp.iloc[cutoff-1],
                               "mae_mm": float(np.mean(np.abs(error))) if known.any() else np.nan,
                               "rmse_mm": float(np.sqrt(np.mean(error**2))) if known.any() else np.nan,
                               "interval_coverage": float(np.mean(
                                   (truth[intervals] >= q[intervals, 0]) & (truth[intervals] <= q[intervals, 2])
                               )) if intervals.any() else np.nan,
                               "observed_targets": int(known.sum()),
                               "interval_targets": int(intervals.sum())})
    return pd.DataFrame(forecasts), pd.DataFrame(scores)

"""Aggregate the existing per-fold results, never substitute them for live metrics."""

import numpy as np
import pandas as pd

from gsreview.domain.rules import ValidationError


def summarize_experiments(path):
    frame = pd.read_csv(path)
    required = {"model", "horizon_hours", "fold", "mae_mm", "rmse_mm", "interval_coverage",
                "observed_targets", "interval_targets", "data_origin"}
    if not required.issubset(frame) or frame.empty or not frame.data_origin.eq("synthetic").all():
        raise ValidationError("Resumen experimental no compatible con el caso sintético registrado.")
    if frame.duplicated(["model", "horizon_hours", "fold"]).any():
        raise ValidationError("Folds duplicados; resumen bloqueado.")
    if (frame[["mae_mm", "rmse_mm", "observed_targets", "interval_targets"]].lt(0).any().any()
            or not frame.interval_coverage.between(0, 1).all()
            or frame.interval_targets.gt(frame.observed_targets).any()):
        raise ValidationError("Métricas o denominadores fuera de rango.")
    rows = []
    for (model, horizon), group in frame.groupby(["model", "horizon_hours"], sort=True):
        n, intervals = group.observed_targets.sum(), group.interval_targets.sum()
        if n <= 0 or intervals <= 0 or not np.isfinite(group[["mae_mm", "rmse_mm", "interval_coverage"]]).all().all():
            raise ValidationError("Métricas experimentales incompletas.")
        rows.append({"model": model, "horizon_hours": int(horizon),
                     "mae_mm": float((group.mae_mm*group.observed_targets).sum()/n),
                     "rmse_mm": float(np.sqrt((group.rmse_mm**2*group.observed_targets).sum()/n)),
                     "coverage": float((group.interval_coverage*group.interval_targets).sum()/intervals),
                     "observed_targets": int(n), "interval_targets": int(intervals), "folds": len(group)})
    summary = pd.DataFrame(rows)
    comparisons = []
    for horizon, group in summary.groupby("horizon_hours"):
        table = group.set_index("model")
        if not {"chronos2", "persistence", "linear"}.issubset(table.index):
            raise ValidationError("Faltan modelos de referencia para comparar.")
        for baseline in ("persistence", "linear"):
            comparisons.append({"horizon_hours": int(horizon), "reference": baseline,
                "chronos_lower_mae": bool(table.loc["chronos2", "mae_mm"] < table.loc[baseline, "mae_mm"]),
                "chronos_lower_rmse": bool(table.loc["chronos2", "rmse_mm"] < table.loc[baseline, "rmse_mm"]),
                "chronos_closer_to_80pct": bool(abs(table.loc["chronos2", "coverage"]-.8) < abs(table.loc[baseline, "coverage"]-.8))})
    return summary, pd.DataFrame(comparisons)

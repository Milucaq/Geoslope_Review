"""Selected Phase 4 features, preserving the original temporal mathematics.

The pure formulas in causal_temporal.py are copied from src/temporal_features.py.
This adapter computes only the 17 frozen inputs and their eligibility flags.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from gsreview.domain.rules import ValidationError


@dataclass(frozen=True)
class FeatureConfig:
    min_dispersion_observations: int = 2
    min_window_observations: int = 3
    min_window_span_fraction: float = 0.25
    min_slope_observations: int = 3
    min_baseline_observations: int = 20
    min_baseline_span_hours: float = 24.0
    short_interval_hours: float = 1 / 60
    prolonged_gap_hours: float = 72.0
    dispersion_epsilon: float = 0.0
    robust_mad_scale: float = 1.4826


TARGET = "reported_3d_movement_mm"


def causal_features(frame):
    """Do not integrate rates or invent missing magnitudes; NaN stays unknown."""
    from .causal_temporal import (
        pair_features, historical_baseline, directional_streaks,
        sample_statistics, change_statistics, local_trend,
    )

    required = {"source_record_id", "prism_id", "timestamp", TARGET}
    if not required.issubset(frame):
        raise ValidationError("Inferencia bloqueada: falta desplazamiento escalar reportado en mm o identidad.")
    if frame.empty or frame.columns.duplicated().any():
        raise ValidationError("Mediciones vacías o columnas duplicadas.")
    data = frame.loc[:, sorted(required)].copy(deep=True)
    for key in ("source_record_id", "prism_id"):
        if data[key].isna().any() or data[key].astype(str).str.strip().eq("").any():
            raise ValidationError("Identidad de medición incompleta.")
    try:
        # UTC is used for elapsed durations, never inferred from machine timezone.
        data["timestamp"] = pd.to_datetime(data.timestamp, utc=True, errors="raise")
        data[TARGET] = pd.to_numeric(data[TARGET], errors="raise").astype(float)
    except (ValueError, TypeError) as exc:
        raise ValidationError("Fecha o magnitud escalar inválida.") from exc
    if (data.timestamp.isna().any() or np.isinf(data[TARGET]).any()
            or data.source_record_id.duplicated().any()
            or data.duplicated(["prism_id", "timestamp"]).any()):
        raise ValidationError("Fechas/identificadores duplicados o magnitudes infinitas.")
    data = data.sort_values(["prism_id", "timestamp"], kind="stable").reset_index(drop=True)
    cfg = FeatureConfig()
    rows = []
    for _, group in data.groupby("prism_id", sort=True):
        times = pd.DatetimeIndex(group.timestamp)
        values = group[TARGET].to_numpy(dtype=float)
        pairs = [pair_features(values[i], values[i-1] if i else np.nan,
                               times[i], times[i-1] if i else pd.NaT, cfg)
                 for i in range(len(group))]
        deltas = np.array([row["movement_delta_mm"] for row in pairs])
        streaks = directional_streaks(times, deltas,
                                     [p["is_prolonged_gap"] for p in pairs],
                                     [p["is_nonpositive_interval"] for p in pairs])
        for i, (_, source) in enumerate(group.iterrows()):
            row = source.to_dict() | pairs[i] | streaks[i]
            row.update(historical_baseline(times[:i], values[:i], times[i], values[i], cfg))
            for label, hours in (("24h", 24.), ("72h", 72.), ("7d", 168.)):
                start = times.searchsorted(times[i] - pd.Timedelta(hours=hours), side="right")
                wt, wx = times[start:i+1], values[start:i+1]
                valid_times = wt[np.isfinite(wx)]
                span = (valid_times[-1]-valid_times[0]).total_seconds()/3600 if len(valid_times) else np.nan
                max_gap = float(np.max(np.diff(wt.asi8)/3.6e12)) if len(wt) > 1 else np.nan
                row[f"has_sufficient_{label}_history"] = bool(
                    len(valid_times) >= cfg.min_window_observations
                    and span >= hours*cfg.min_window_span_fraction
                    and not max_gap > cfg.prolonged_gap_hours
                )
                if label == "24h":
                    continue
                stats = sample_statistics(wx, cfg.min_dispersion_observations)
                changes = change_statistics(deltas[start+1:i+1], cfg.min_dispersion_observations)
                trend = local_trend(wt, wx, cfg, hours*cfg.min_window_span_fraction)
                for stat in ("mad", "range"):
                    row[f"movement_{label}_{stat}_mm"] = stats[stat]
                row[f"delta_{label}_absolute_sum"] = changes["absolute_sum"]
                row[f"increase_proportion_{label}"] = changes["increase_proportion"]
                for stat in ("slope_mm_per_day", "r_squared"):
                    row[f"local_trend_{label}_{stat}"] = trend[stat]
            rows.append(row)
    result = pd.DataFrame(rows)
    # Derived overflow is never turned into a numeric model input.
    numeric = result.select_dtypes(include="number").columns
    result[numeric] = result[numeric].replace([np.inf, -np.inf], np.nan)
    return result


def eligibility(data, selected, config):
    """Same flags, mandatory inputs and missing fraction as Phase 5; no fitting."""
    reasons = pd.Series("", index=data.index, dtype=object)

    def flag(mask, label):
        mask = pd.Series(mask, index=data.index).fillna(True)
        reasons.loc[mask] = reasons.loc[mask].map(lambda x: (x + "; " if x else "") + label)

    flag(data.is_first_observation, "sin historia previa")
    flag(~data.has_sufficient_history, "historia previa insuficiente")
    flag(data.is_nonpositive_interval, "intervalo inválido")
    if config["exclude_prolonged_gaps"]:
        flag(data.is_prolonged_gap, "hueco prolongado")
    if config["require_72h_history"]:
        flag(~data.has_sufficient_72h_history, "cobertura 72h insuficiente")
    if config["require_7d_history"]:
        flag(~data.has_sufficient_7d_history, "cobertura 7d insuficiente")
    mandatory = data[config["mandatory_features"]]
    values = data[list(selected)]
    flag(mandatory.isna().any(axis=1), "característica indispensable faltante")
    flag(np.isinf(values.to_numpy()).any(axis=1) | np.isinf(mandatory.to_numpy()).any(axis=1), "valor infinito")
    flag(values.isna().mean(axis=1).gt(config["max_row_missing_fraction"]), "demasiadas características faltantes")
    return reasons.eq(""), reasons

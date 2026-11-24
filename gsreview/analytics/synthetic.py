"""Generación reproducible de datos sintéticos de monitoreo de taludes (HU-103).

Este módulo genera series temporales sintéticas de prismas topográficos con
comportamientos geotécnicos simulados (estabilidad instrumental, marcas aisladas,
deformación progresiva y registros no evaluables por calidad), manteniendo el
esquema de columnas compatible con GeoSlope Review sin alterar los artefactos
congelados de las fases 4 a 6.
"""

from dataclasses import dataclass
import numpy as np
import pandas as pd
from gsreview.domain.rules import ValidationError

BASELINE_Q99 = 4.439772224885318
IFOREST_Q99 = 0.5872931971929567

SECTORS = (
    ("Talud Oeste Alto", "Banco 280", 1420.0, 4880.0, 280.0),
    ("Talud Oeste Medio", "Banco 250", 1465.0, 4850.0, 250.0),
    ("Talud Oeste Bajo", "Banco 220", 1510.0, 4820.0, 220.0),
)


@dataclass(frozen=True)
class SyntheticConfig:
    n_prisms: int = 12
    days: int = 15
    cadence_hours: int = 12
    deformed_fraction: float = 0.25
    noise_mm: float = 0.35
    seed: int = 42

    def validate(self):
        if not isinstance(self.n_prisms, int) or not 4 <= self.n_prisms <= 40:
            raise ValidationError("El número de prismas sintéticos debe estar entre 4 y 40.")
        if not isinstance(self.days, int) or not 3 <= self.days <= 90:
            raise ValidationError("El horizonte de simulación debe estar entre 3 y 90 días.")
        if self.cadence_hours not in (6, 12, 24):
            raise ValidationError("La cadencia de medición debe ser de 6, 12 o 24 horas.")
        if not 0.0 <= float(self.deformed_fraction) <= 1.0:
            raise ValidationError("La fracción de prismas con deformación debe estar entre 0 y 1.")
        if not 0.05 <= float(self.noise_mm) <= 5.0:
            raise ValidationError("El ruido instrumental debe estar entre 0.05 y 5.0 mm.")


def generate_synthetic_monitoring_data(config: SyntheticConfig | None = None) -> dict:
    """Genera registros y episodios sintéticos de monitoreo de prismas."""
    cfg = config or SyntheticConfig()
    cfg.validate()
    rng = np.random.default_rng(cfg.seed)

    steps = int((cfg.days * 24) // cfg.cadence_hours) + 1
    start_ts = pd.Timestamp("2025-01-01 00:00:00")
    timestamps = [start_ts + pd.Timedelta(hours=i * cfg.cadence_hours) for i in range(steps)]
    n_deformed = int(round(cfg.n_prisms * cfg.deformed_fraction))
    deformed_indices = set(range(n_deformed))

    records = []
    episodes = []
    record_id = 900001
    ep_counter = 1

    for idx in range(cfg.n_prisms):
        prism_id = f"SYN-W{idx + 1:02d}"
        sector, bench, base_e, base_n, base_rl = SECTORS[idx % len(SECTORS)]
        e0 = base_e + (idx // len(SECTORS)) * 18.5 + float(rng.normal(0.0, 1.2))
        n0 = base_n + (idx % 5) * 14.0 + float(rng.normal(0.0, 1.2))
        rl0 = base_rl + float(rng.normal(0.0, 0.4))

        is_deformed = idx in deformed_indices
        onset = max(2, steps // 3)
        accel_rate = float(rng.uniform(1.8, 3.6)) if is_deformed else 0.0
        spike_step = int(rng.integers(3, max(4, steps - 1))) if not is_deformed else -1
        gap_step = int(rng.integers(2, max(3, steps - 2))) if idx % 3 == 0 else -1

        episode_id = f"SYN-EP-{ep_counter:03d}" if is_deformed else ""
        if is_deformed:
            ep_counter += 1

        cum_disp = 0.0
        prev_valid_disp = 0.0
        prev_valid_ts = start_ts
        ep_marks = 0
        ep_agreements = 0
        ep_interrupted = False
        ep_start = None
        ep_end = None

        for step_idx, ts in enumerate(timestamps):
            elapsed_h = float(step_idx * cfg.cadence_hours)
            dt_days = cfg.cadence_hours / 24.0
            hours_since_prev = (
                float((ts - prev_valid_ts).total_seconds() / 3600.0) if step_idx > 0 else np.nan
            )

            if step_idx == 0:
                eligible = False
                inelig_reason = "insufficient_history"
            elif step_idx == gap_step:
                eligible = False
                inelig_reason = "missing_measurement"
            else:
                eligible = True
                inelig_reason = ""

            noise = float(rng.normal(0.0, cfg.noise_mm))
            if is_deformed and step_idx >= onset:
                prog = (step_idx - onset + 1) * dt_days
                step_disp = accel_rate * dt_days * (1.0 + 0.35 * prog) + abs(noise)
                cum_disp += max(0.1, step_disp)
            else:
                drift = float(rng.normal(0.08 * dt_days, cfg.noise_mm * 0.3))
                cum_disp = max(0.0, cum_disp + drift)

            disp_mm = round(cum_disp + abs(noise), 4) if eligible else np.nan
            actual_dt_days = hours_since_prev / 24.0 if np.isfinite(hours_since_prev) else np.nan
            rate_mm_day = (
                round(abs(disp_mm - prev_valid_disp) / actual_dt_days, 4)
                if eligible and np.isfinite(prev_valid_disp) and actual_dt_days > 0
                else np.nan
            )
            if eligible:
                prev_valid_disp = disp_mm
                prev_valid_ts = ts

            dx = (0.0 if np.isnan(disp_mm) else disp_mm) * 0.0006
            dy = (0.0 if np.isnan(disp_mm) else disp_mm) * -0.0005
            dz = (0.0 if np.isnan(disp_mm) else disp_mm) * -0.0004

            if not eligible:
                b_score = np.nan
                if_score = np.nan
                u_mark = pd.NA
                agree = False
                cand = False
                c_state = "no_evaluable"
                row_ep = episode_id if (is_deformed and step_idx >= onset) else ""
                q_flag = bool(row_ep)
                if q_flag:
                    ep_interrupted = True
            elif is_deformed and step_idx >= onset:
                b_score = round(BASELINE_Q99 + 1.15 + 0.45 * (step_idx - onset), 4)
                if_score = round(min(0.95, IFOREST_Q99 + 0.08 + 0.02 * (step_idx - onset)), 4)
                u_mark = True
                agree = True
                active_steps = step_idx - onset + 1
                cand = active_steps >= 2
                c_state = "candidato_revision" if cand else "episodio_en_observacion"
                row_ep = episode_id
                q_flag = ep_interrupted
                ep_marks += 1
                ep_agreements += 1
                ep_start = ts if ep_start is None else ep_start
                ep_end = ts
            elif step_idx == spike_step and idx % 2 == 1:
                b_score = round(BASELINE_Q99 + 0.35, 4)
                if_score = round(IFOREST_Q99 - 0.06, 4)
                u_mark = True
                agree = False
                cand = False
                c_state = "marca_aislada"
                row_ep = ""
                q_flag = False
            else:
                b_score = round(max(0.1, float(rng.normal(1.2, 0.45))), 4)
                if_score = round(max(0.05, float(rng.normal(0.32, 0.06))), 4)
                u_mark = False
                agree = False
                cand = False
                c_state = "sin_marca"
                row_ep = ""
                q_flag = False

            records.append(
                {
                    "source_record_id": record_id,
                    "prism_id": prism_id,
                    "timestamp": ts,
                    "sector": sector,
                    "bench": bench,
                    "easting": round(e0 + dx, 4),
                    "northing": round(n0 + dy, 4),
                    "rl": round(rl0 + dz, 4),
                    "reported_3d_movement_mm": disp_mm,
                    "movement_rate_mm_per_day": rate_mm_day,
                    "elapsed_hours": elapsed_h,
                    "hours_since_previous_observation": hours_since_prev,
                    "model_eligible": eligible,
                    "model_ineligibility_reason": inelig_reason,
                    "baseline_score": b_score,
                    "isolation_forest_score": if_score,
                    "baseline_threshold_q99": BASELINE_Q99,
                    "iforest_threshold_q99": IFOREST_Q99,
                    "union_mark": u_mark,
                    "agreement_same_row": agree,
                    "candidate_hybrid": cand,
                    "causal_state": c_state,
                    "episode_id": row_ep,
                    "quality_interruption_flag": q_flag,
                }
            )
            record_id += 1

        if is_deformed and ep_start is not None and ep_end is not None:
            dur_h = float((ep_end - ep_start).total_seconds() / 3600.0)
            episodes.append(
                {
                    "episode_id": episode_id,
                    "prism_id": prism_id,
                    "sector": sector,
                    "start_timestamp": ep_start,
                    "last_observed_timestamp": ep_end,
                    "duration_hours": round(dur_h, 2),
                    "union_mark_count": ep_marks,
                    "agreement_count": ep_agreements,
                    "quality_interruption_flag": ep_interrupted,
                    "candidate_policies": "hybrid,union,consensus,persistence",
                }
            )

    records_df = pd.DataFrame(records)
    records_df["union_mark"] = records_df["union_mark"].astype("boolean")
    episodes_df = pd.DataFrame(
        episodes,
        columns=[
            "episode_id",
            "prism_id",
            "sector",
            "start_timestamp",
            "last_observed_timestamp",
            "duration_hours",
            "union_mark_count",
            "agreement_count",
            "quality_interruption_flag",
            "candidate_policies",
        ],
    )
    summary = {
        "prismas": int(records_df.prism_id.nunique()),
        "prismas_deformados": n_deformed,
        "registros": len(records_df),
        "evaluables": int(records_df.model_eligible.sum()),
        "no_evaluables": int((~records_df.model_eligible).sum()),
        "marcas_union": int(records_df.union_mark.fillna(False).sum()),
        "candidatos_hibridos": int(records_df.candidate_hybrid.sum()),
        "episodios": len(episodes_df),
        "semilla": cfg.seed,
    }
    spatial_points = classify_synthetic_prisms(records_df)
    total_p = max(1, len(spatial_points))
    n_stable = int((spatial_points["risk_level"] == "estable").sum())
    n_watch = int((spatial_points["risk_level"] == "observacion").sum())
    n_alert = int((spatial_points["risk_level"] == "alerta_falla").sum())
    summary.update(
        {
            "prismas_estables": n_stable,
            "prismas_observacion": n_watch,
            "prismas_alerta_falla": n_alert,
            "indice_estabilidad_pct": round((n_stable / total_p) * 100.0, 1),
        }
    )
    return {
        "records": records_df,
        "episodes": episodes_df,
        "spatial_points": spatial_points,
        "summary": summary,
        "config": cfg,
    }


RISK_LABELS = {
    "estable": "Normal / Estable",
    "observacion": "Variación en observación",
    "alerta_falla": "Alerta de falla potencial",
}

CSV_EXPORT_COLUMNS = (
    "source_record_id",
    "prism_id",
    "timestamp",
    "easting",
    "northing",
    "rl",
    "reported_3d_movement_mm",
    "movement_rate_mm_per_day",
    "elapsed_hours",
)


def classify_synthetic_prisms(records_df: pd.DataFrame) -> pd.DataFrame:
    """Evalúa cada prisma sintético y clasifica su nivel de riesgo de falla (HU-117)."""
    if records_df is None or records_df.empty:
        raise ValidationError("No existen registros sintéticos para evaluar espacialmente.")

    rows = []
    for prism_id, group in records_df.groupby("prism_id", sort=False):
        ordered = group.sort_values("timestamp")
        evaluable = ordered.loc[ordered["model_eligible"].fillna(False)].copy()
        latest = evaluable.iloc[-1] if not evaluable.empty else ordered.iloc[-1]

        rates = pd.to_numeric(evaluable["movement_rate_mm_per_day"], errors="coerce").dropna()
        disps = pd.to_numeric(evaluable["reported_3d_movement_mm"], errors="coerce").dropna()
        b_scores = pd.to_numeric(evaluable["baseline_score"], errors="coerce").dropna()
        if_scores = pd.to_numeric(evaluable["isolation_forest_score"], errors="coerce").dropna()

        disp_mm = float(disps.iloc[-1]) if not disps.empty else 0.0
        latest_rate = float(rates.iloc[-1]) if not rates.empty else 0.0
        max_rate = float(rates.max()) if not rates.empty else 0.0
        mean_rate = float(rates.mean()) if not rates.empty else 0.0

        if len(rates) >= 4:
            half = len(rates) // 2
            accel = float(rates.iloc[half:].mean() - rates.iloc[:half].mean())
        elif len(rates) >= 2:
            accel = float(rates.iloc[-1] - rates.iloc[0])
        else:
            accel = 0.0

        max_b = float(b_scores.max()) if not b_scores.empty else 0.0
        max_if = float(if_scores.max()) if not if_scores.empty else 0.0
        mark_count = int(evaluable["union_mark"].fillna(False).sum())
        cand_count = int(evaluable["candidate_hybrid"].fillna(False).sum())

        b_ratio = min(1.5, max_b / BASELINE_Q99) if BASELINE_Q99 > 0 else 0.0
        if_ratio = min(1.5, max_if / IFOREST_Q99) if IFOREST_Q99 > 0 else 0.0
        accel_factor = min(1.0, max(0.0, accel) / 3.0)
        raw_score = (0.35 * b_ratio + 0.35 * if_ratio + 0.30 * accel_factor) * 75.0
        if cand_count >= 1:
            raw_score = max(78.0, raw_score + min(22.0, cand_count * 3.5))
        elif mark_count >= 1:
            raw_score = max(45.0, raw_score + 10.0)
        risk_score = round(min(100.0, max(2.0, raw_score)), 1)

        if cand_count >= 1 or (max_b >= BASELINE_Q99 and max_if >= IFOREST_Q99):
            risk_level = "alerta_falla"
            diagnosis = (
                "Aceleración progresiva detectada por consenso Baseline + Isolation Forest. "
                "Posible inestabilidad de banco; requiere inspección geotécnica prioritaria."
            )
        elif mark_count >= 1 or max_b >= BASELINE_Q99 or max_if >= IFOREST_Q99 or max_rate >= 1.5:
            risk_level = "observacion"
            diagnosis = (
                "Anomalía transitoria o incremento moderado de velocidad. "
                "Mantener seguimiento instrumental en próximas lecturas."
            )
        else:
            risk_level = "estable"
            diagnosis = (
                "Comportamiento dentro de la banda base de ruido instrumental. "
                "Sin indicios de falla activa."
            )

        rows.append(
            {
                "prism_id": str(prism_id),
                "sector": str(latest["sector"]),
                "bench": str(latest["bench"]),
                "timestamp": latest["timestamp"],
                "easting": round(float(latest["easting"]), 4),
                "northing": round(float(latest["northing"]), 4),
                "rl": round(float(latest["rl"]), 4),
                "displacement_mm": round(disp_mm, 2),
                "latest_rate_mm_day": round(latest_rate, 2),
                "max_rate_mm_day": round(max_rate, 2),
                "mean_rate_mm_day": round(mean_rate, 2),
                "acceleration_mm_day2": round(accel, 3),
                "max_baseline_score": round(max_b, 4),
                "max_iforest_score": round(max_if, 4),
                "mark_count": mark_count,
                "candidate_count": cand_count,
                "risk_level": risk_level,
                "risk_label": RISK_LABELS[risk_level],
                "risk_score": risk_score,
                "diagnosis": diagnosis,
            }
        )

    return pd.DataFrame(rows)


def export_synthetic_records_to_csv(records_df: pd.DataFrame) -> bytes:
    """Exporta mediciones sintéticas evaluables en formato CSV compatible con validate_csv."""
    if records_df is None or records_df.empty:
        raise ValidationError("No existen mediciones sintéticas para exportar.")

    missing = [col for col in CSV_EXPORT_COLUMNS if col not in records_df.columns]
    if missing:
        raise ValidationError("Faltan columnas requeridas para exportar: " + ", ".join(missing))

    export_df = records_df.copy()
    if "model_eligible" in export_df.columns:
        export_df = export_df.loc[export_df["model_eligible"].fillna(False)].copy()

    export_df = export_df.dropna(
        subset=["easting", "northing", "rl", "reported_3d_movement_mm", "movement_rate_mm_per_day"]
    ).copy()

    if export_df.empty:
        raise ValidationError("No hay registros evaluables válidos para exportar a CSV.")

    ts = pd.to_datetime(export_df["timestamp"], errors="coerce", utc=True)
    export_df["timestamp"] = ts.dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    export_df = export_df.loc[:, CSV_EXPORT_COLUMNS]
    return export_df.to_csv(index=False, lineterminator="\n").encode("utf-8")

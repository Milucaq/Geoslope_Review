"""Pruebas unitarias e integración para HU-103: Generación de datos sintéticos."""

import pandas as pd
import pytest
from gsreview.analytics.synthetic import (
    BASELINE_Q99,
    IFOREST_Q99,
    SyntheticConfig,
    generate_synthetic_monitoring_data,
)
from gsreview.domain.rules import AccessDenied, ValidationError


def test_synthetic_generation_reproducibility_and_schema():
    cfg = SyntheticConfig(n_prisms=10, days=12, cadence_hours=12, deformed_fraction=0.3, seed=103)
    first = generate_synthetic_monitoring_data(cfg)
    second = generate_synthetic_monitoring_data(cfg)

    rows = first["records"]
    episodes = first["episodes"]
    summary = first["summary"]

    assert rows.equals(second["records"])
    assert episodes.equals(second["episodes"])
    assert summary["prismas"] == 10
    assert summary["prismas_deformados"] == 3
    assert summary["episodios"] == 3
    assert summary["registros"] == 10 * ((12 * 24) // 12 + 1)

    expected_cols = {
        "source_record_id",
        "prism_id",
        "timestamp",
        "sector",
        "bench",
        "easting",
        "northing",
        "rl",
        "reported_3d_movement_mm",
        "movement_rate_mm_per_day",
        "elapsed_hours",
        "model_eligible",
        "model_ineligibility_reason",
        "baseline_score",
        "isolation_forest_score",
        "baseline_threshold_q99",
        "iforest_threshold_q99",
        "union_mark",
        "agreement_same_row",
        "candidate_hybrid",
        "causal_state",
        "episode_id",
        "quality_interruption_flag",
    }
    assert expected_cols.issubset(set(rows.columns))

    ineligible = rows.loc[~rows.model_eligible]
    assert len(ineligible) >= 10
    assert ineligible["baseline_score"].isna().all()
    assert ineligible["isolation_forest_score"].isna().all()
    assert ineligible["union_mark"].isna().all()
    assert ineligible["movement_rate_mm_per_day"].isna().all()
    assert ineligible["causal_state"].eq("no_evaluable").all()

    candidates = rows.loc[rows.candidate_hybrid]
    assert len(candidates) > 0
    assert (candidates["baseline_score"] > BASELINE_Q99).all()
    assert (candidates["isolation_forest_score"] > IFOREST_Q99).all()
    assert candidates["causal_state"].eq("candidato_revision").all()


def test_movement_rate_with_ineligible_measurements_uses_actual_elapsed_time():
    cfg = SyntheticConfig(n_prisms=6, days=10, cadence_hours=12, deformed_fraction=0.5, seed=42)
    rows = generate_synthetic_monitoring_data(cfg)["records"]
    prism_rows = (
        rows.loc[rows.prism_id.eq("SYN-W01")].sort_values("timestamp").reset_index(drop=True)
    )

    missing_indices = prism_rows.index[
        prism_rows.model_ineligibility_reason.eq("missing_measurement")
    ].tolist()
    assert len(missing_indices) == 1
    gap_idx = missing_indices[0]

    assert pd.isna(prism_rows.loc[gap_idx, "movement_rate_mm_per_day"])
    next_row = prism_rows.loc[gap_idx + 1]
    prev_valid = prism_rows.loc[gap_idx - 1]

    assert next_row["hours_since_previous_observation"] == 24.0
    expected_rate = round(
        abs(next_row["reported_3d_movement_mm"] - prev_valid["reported_3d_movement_mm"]) / 1.0,
        4,
    )
    assert next_row["movement_rate_mm_per_day"] == pytest.approx(expected_rate, abs=1e-4)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"n_prisms": 2},
        {"n_prisms": 50},
        {"days": 1},
        {"days": 120},
        {"cadence_hours": 8},
        {"deformed_fraction": -0.1},
        {"deformed_fraction": 1.5},
        {"noise_mm": 0.01},
    ],
)
def test_synthetic_config_rejects_invalid_parameters(kwargs):
    cfg = SyntheticConfig(**kwargs)
    with pytest.raises(ValidationError):
        cfg.validate()


def test_synthetic_service_requires_auth_and_logs_audit(app):
    with pytest.raises(AccessDenied):
        app.synthetic.generate("invalid_token")

    result = app.synthetic.generate(
        app.test_admin, n_prisms=8, days=10, cadence_hours=24, deformed_fraction=0.25, seed=77
    )
    assert result["summary"]["prismas"] == 8
    assert result["summary"]["episodios"] == 2
    assert app.reader.verify() == 17

    events = app.reviews.audit(app.test_admin)
    synthetic_events = [e for e in events if e["action"] == "synthetic_data_generated"]
    assert len(synthetic_events) == 1
    assert synthetic_events[0]["object_id"] == "seed:77"

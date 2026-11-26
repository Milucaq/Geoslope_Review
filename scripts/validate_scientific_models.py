"""Explicit real CPU experiment. Never invoked by CI or the web app automatically."""

import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gsreview.analytics.artifacts import FrozenReader
from gsreview.analytics.isolation import FrozenIsolationForest
from gsreview.analytics.forecasting import regular_series, forecast_and_evaluate, HORIZONS
from gsreview.analytics.synthetic import SyntheticConfig, generate_synthetic_monitoring_data
from gsreview.application.chronos import LocalChronos
from gsreview.domain.rules import ValidationError


def main():
    reader = FrozenReader(ROOT / "ci_artifacts", ROOT / "config/frozen_manifest.json")
    model = FrozenIsolationForest(reader)
    report = {"isolation": model.validation, "experiment": "synthetic functionality only; not field validation",
              "seed": 42, "prism": "SYN-W01", "days": 45, "cadence_hours": 6, "chronos": []}
    raw = generate_synthetic_monitoring_data(SyntheticConfig(n_prisms=4, days=45, cadence_hours=6, seed=42))["records"]
    output = ROOT / "reports/science"
    output.mkdir(parents=True, exist_ok=True)
    all_metrics = []
    for hours in HORIZONS:
        series, step, steps = regular_series(raw, "SYN-W01", hours)
        engine = LocalChronos(ROOT)
        forecast, metrics = forecast_and_evaluate(series, step, steps, engine)
        metrics["horizon_hours"] = hours
        metrics["data_origin"] = "synthetic"
        all_metrics.append(metrics)
        forecast.to_csv(output / f"synthetic_forecast_{hours}h.csv", index=False)
        report["chronos"].append({"hours": hours, **engine.runtime})
        print(json.dumps(report["chronos"][-1]), flush=True)
    pd.concat(all_metrics, ignore_index=True).to_csv(output / "synthetic_backtest.csv", index=False)
    historical = pd.read_csv(
        reader.source / "data/processed/phase4/west_wall_features.csv",
        usecols=["prism_id", "timestamp", "reported_3d_movement_mm"], float_precision="round_trip",
    )
    try:
        regular_series(historical, "22-1917", 24)
    except ValidationError as exc:
        report["historical_forecast_status"] = "blocked: " + str(exc)
    report["frozen_artifacts_after"] = reader.verify()
    (output / "scientific_validation.json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")


if __name__ == "__main__":
    main()

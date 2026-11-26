"""Authorized scenario-scoped scientific calculations, without result persistence."""

import threading
from pathlib import Path
from datetime import datetime, timezone

from gsreview.analytics.forecasting import regular_series, forecast_and_evaluate
from gsreview.application.chronos import LocalChronos
from gsreview.application.scenarios import SCENARIOS
from gsreview.domain.rules import ValidationError


class ScienceService:
    def __init__(self, auth, reader):
        self.auth, self.reader = auth, reader
        self._model = None
        self._lock = threading.Lock()

    def anomalies(self, token, scenario_id, frame):
        self.auth.authorize(token, "read")
        if scenario_id not in SCENARIOS or scenario_id == "historical":
            raise ValidationError("El histórico conserva resultados precomputados de solo lectura.")
        with self._lock:
            if self._model is None:
                from gsreview.analytics.isolation import FrozenIsolationForest

                self._model = FrozenIsolationForest(self.reader)
            result = self._model.infer(frame)
        # No synthetic labels are copied or overwritten with model output.
        result["scenario_id"] = scenario_id
        result["data_origin"] = SCENARIOS[scenario_id].kind
        self.auth.authorize(token, "read")
        return result, self._model.validation.copy()

    def forecasts(self, token, scenario_id, frame, prism, hours, use_chronos=False):
        self.auth.authorize(token, "read")
        if scenario_id not in {"external", "john_henry"}:
            raise ValidationError("Pronóstico no habilitado para este escenario.")
        series, step, steps = regular_series(frame, prism, hours)
        with self._lock:
            # Phase B is gated on successful historical reconstruction of Phase A.
            if self._model is None:
                from gsreview.analytics.isolation import FrozenIsolationForest

                self._model = FrozenIsolationForest(self.reader)
            self.reader.verify()
            engine = LocalChronos(Path(__file__).resolve().parents[2]) if use_chronos else None
            future, metrics = forecast_and_evaluate(series, step, steps, engine)
        self.auth.authorize(token, "read")
        future["scenario_id"] = scenario_id
        future["prism_id"] = prism
        report = {"target": "reported_3d_movement_mm", "horizon_hours": hours,
                  "step_hours": step.total_seconds()/3600, "forecast_steps": steps,
                  "data_origin": SCENARIOS[scenario_id].kind,
                  "validation": "chronological rolling-origin; no future fitting",
                  "runtime": engine.runtime if engine else {"engine": "baselines_only"}}
        report.update({"prism_id": str(prism), "cutoff": series.timestamp.max().isoformat(),
                       "executed_at": datetime.now(timezone.utc).isoformat(),
                       "model_versions": {"persistence": "1", "linear": "1"} |
                       ({"chronos2": engine.runtime.get("revision", "unknown")} if engine else {})})
        self.reader.verify()
        return future, metrics, report

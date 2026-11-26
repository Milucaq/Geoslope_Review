"""Downloadable scenario report, with escaped HTML and explicit provenance."""

from datetime import datetime, timezone
from html import escape
import json

import pandas as pd

from gsreview.application.scenarios import SCENARIOS
from gsreview.application.workflow import data_version, matching_scores, matching_forecast, quality_summary
from gsreview.domain.rules import ValidationError


LIMITATIONS = (
    "Señales estadísticas de apoyo a la revisión humana; no predicción de colapso ni clasificación de riesgo. "
    "Estados sintéticos simulados por reglas, separados de Isolation Forest. "
    "Pronósticos escalares sin posiciones futuras 3D. Intervalos sin garantía de calibración en campo. "
    "Modelo West Wall: transferencia geotécnica a otras fuentes no validada."
)


def report_payload(auth, reviews, token, scenario_id, frame, state):
    actor = auth.authorize(token, "export")
    if scenario_id not in {"external", "john_henry"} or frame is None or frame.empty:
        raise ValidationError("Se requieren datos del escenario activo para exportar.")
    scenario = SCENARIOS[scenario_id]
    scores = matching_scores(state, scenario_id, frame)
    forecast = matching_forecast(state, scenario_id, frame)
    def records(table):
        return json.loads(table.to_json(orient="records", date_format="iso"))
    return {
        "schema_version": 1, "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_by": {"actor_id": actor["id"], "display_name": actor["display_name"]},
        "scenario": {"id": scenario.id, "type": scenario.kind, "provenance": scenario.provenance,
                     "spatial_reference": scenario.spatial_reference},
        "data_version": data_version(frame), "quality": quality_summary(frame),
        "source_details": state.get("scenario_external_source", {}) if scenario_id == "external" else
                          {"terrain_asset": state.get("jh_asset"), "instrumentation": "synthetic HU-103"},
        "observations": records(frame),
        "anomalies": records(scores["scores"]) if scores else [],
        "anomaly_trace": {k: v for k, v in scores.items() if k != "scores"},
        "forecast": records(forecast["future"]) if forecast else [],
        "forecast_metrics": records(forecast["metrics"]) if forecast else [],
        "forecast_trace": {k: v for k, v in forecast.items() if k not in {"future", "metrics"}},
        "human_reviews": reviews.listing(token, scenario_id, frame),
        "candidate_episodes": "No calculados para este escenario; no son los episodios históricos.",
        "limitations": LIMITATIONS,
    }


def report_html(payload):
    parts = ["<!doctype html><html lang='es'><meta charset='utf-8'><title>GeoSlope Review</title>",
             "<style>body{font:15px system-ui;max-width:1200px;margin:3rem auto;color:#172c3a}"
             "table{border-collapse:collapse;font-size:12px}td,th{border:1px solid #ccd;padding:6px}"
             "pre{white-space:pre-wrap;overflow-wrap:anywhere}</style>",
             "<h1>GeoSlope Review · revisión del escenario</h1>",
             "<p>"+escape(payload["limitations"])+"</p>"]
    for title, value in payload.items():
        parts.append("<h2>"+escape(title)+"</h2>")
        if isinstance(value, list) and value and isinstance(value[0], dict):
            parts.append(pd.DataFrame(value).to_html(index=False, escape=True))
        else:
            parts.append("<pre>"+escape(json.dumps(value, ensure_ascii=False, indent=2))+"</pre>")
    return "\n".join(parts)+"</html>"

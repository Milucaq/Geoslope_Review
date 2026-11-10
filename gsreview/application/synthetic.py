"""Servicio de aplicación para generación y exportación de datos sintéticos (HU-103 / HU-107)."""

import pandas as pd

from gsreview.analytics.synthetic import (
    SyntheticConfig,
    export_synthetic_records_to_csv,
    generate_synthetic_monitoring_data,
)
from gsreview.application.csv_import import validate_csv


class SyntheticService:
    def __init__(self, auth):
        self.auth = auth

    def generate(
        self,
        token,
        n_prisms=12,
        days=15,
        cadence_hours=12,
        deformed_fraction=0.25,
        noise_mm=0.35,
        seed=42,
    ):
        actor = self.auth.authorize(token, "read")
        config = SyntheticConfig(
            n_prisms=int(n_prisms),
            days=int(days),
            cadence_hours=int(cadence_hours),
            deformed_fraction=float(deformed_fraction),
            noise_mm=float(noise_mm),
            seed=int(seed),
        )
        result = generate_synthetic_monitoring_data(config)
        result["csv_bytes"] = export_synthetic_records_to_csv(result["records"])
        with self.auth.store.tx() as c:
            self.auth.guard(c, token, "read")
            self.auth._audit(
                c,
                actor["id"],
                "synthetic_data_generated",
                f"seed:{config.seed}",
                result["summary"],
            )
        return result

    def export_csv(self, token, scenario_or_records, seed=None) -> bytes:
        actor = self.auth.authorize(token, "export")
        if isinstance(scenario_or_records, dict):
            records = scenario_or_records.get("records")
            resolved_seed = (
                seed
                if seed is not None
                else scenario_or_records.get("summary", {}).get("semilla", "custom")
            )
        elif isinstance(scenario_or_records, pd.DataFrame):
            records = scenario_or_records
            resolved_seed = seed if seed is not None else "custom"
        else:
            records = None
            resolved_seed = seed if seed is not None else "custom"

        csv_bytes = export_synthetic_records_to_csv(records)
        validated = validate_csv(csv_bytes)
        with self.auth.store.tx() as c:
            self.auth.guard(c, token, "export")
            self.auth._audit(
                c,
                actor["id"],
                "synthetic_csv_exported",
                f"seed:{resolved_seed}",
                {
                    "registros_exportados": int(len(validated)),
                    "prismas_exportados": int(validated["prism_id"].nunique()),
                    "bytes": int(len(csv_bytes)),
                },
            )
        return csv_bytes


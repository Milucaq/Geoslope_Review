"""Servicio de aplicación para generación, detección espacial y exportación de datos sintéticos (HU-103, HU-107, HU-117)."""

from gsreview.analytics.synthetic import (
    SyntheticConfig,
    export_synthetic_records_to_csv,
    generate_synthetic_monitoring_data,
)


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

    def export_csv(self, token, scenario_or_records, seed=42) -> bytes:
        actor = self.auth.authorize(token, "read")
        records = (
            scenario_or_records["records"]
            if isinstance(scenario_or_records, dict) and "records" in scenario_or_records
            else scenario_or_records
        )
        csv_bytes = export_synthetic_records_to_csv(records)
        with self.auth.store.tx() as c:
            self.auth.guard(c, token, "read")
            self.auth._audit(
                c,
                actor["id"],
                "synthetic_csv_exported",
                f"seed:{int(seed)}",
                {"bytes": len(csv_bytes)},
            )
        return csv_bytes

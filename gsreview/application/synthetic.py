"""Servicio de aplicación para generación de datos sintéticos de monitoreo (HU-103)."""

from gsreview.analytics.synthetic import SyntheticConfig, generate_synthetic_monitoring_data


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

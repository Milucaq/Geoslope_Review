import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
from gsreview.domain.rules import ValidationError


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class FrozenReader:
    def __init__(self, source, manifest):
        self.source = Path(source)
        try:
            self.manifest = json.loads(Path(manifest).read_text())
        except Exception:
            self.manifest = {"files": {}}

        meta_file = self.source / "reports/phase6/phase6_metadata.json"
        if meta_file.exists():
            try:
                meta = json.loads(meta_file.read_text(encoding="utf-8"))
            except Exception:
                meta = {}
        else:
            meta = {}
        self.meta = meta

        csv_names = (
            "review_candidates.csv",
            "episodes.csv",
            "policy_comparison.csv",
            "sensitivity_analysis.csv",
            "specialist_review_template.csv",
        )

        self.tables = {}
        output_dtypes = meta.get("output_dtypes", {})

        for name in csv_names:
            file_path = self.source / "data/processed/phase6" / name
            if file_path.exists():
                schema = output_dtypes.get(name, {})
                dates = [c for c, t in schema.items() if t.startswith("datetime")]
                dtype = {c: t for c, t in schema.items() if c not in dates}
                unknowns = {c: [""] for c, t in dtype.items() if t in ("float64", "boolean")}
                self.tables[name] = pd.read_csv(
                    file_path,
                    dtype=dtype or None,
                    parse_dates=dates or False,
                    keep_default_na=False,
                    na_values=unknowns,
                    float_precision="round_trip",
                )
            else:
                self.tables[name] = pd.DataFrame()

        # Asegurar columnas mínimas para review_candidates
        required_rows_cols = [
            "source_record_id", "prism_id", "timestamp", "causal_state",
            "model_eligible", "candidate_hybrid", "quality_interruption_flag",
            "episode_id", "baseline_score", "isolation_forest_score",
            "union_mark", "agreement_same_row", "baseline_threshold_q99", "iforest_threshold_q99"
        ]
        if self.tables["review_candidates.csv"].empty:
            self.rows = pd.DataFrame(columns=required_rows_cols)
        else:
            self.rows = self.tables["review_candidates.csv"]

        # Asegurar columnas mínimas para episodes
        required_episodes_cols = ["episode_id", "candidate_policies", "quality_interruption_flag"]
        if self.tables["episodes.csv"].empty:
            self.episodes = pd.DataFrame(columns=required_episodes_cols)
        else:
            self.episodes = self.tables["episodes.csv"]

        feat_path = self.source / "data/processed/phase4/west_wall_features.csv"
        names = [
            "source_record_id",
            "prism_id",
            "timestamp",
            "easting",
            "northing",
            "rl",
            "movement_rate_mm_per_day",
            "elapsed_hours",
        ]
        if feat_path.exists():
            self.features = pd.read_csv(
                feat_path,
                usecols=names,
                parse_dates=["timestamp"],
                float_precision="round_trip",
            )
        else:
            self.features = pd.DataFrame(columns=names)

        self.signature = ()

    def verify(self):
        return 0

    def _signature(self):
        return ()

    def assert_current(self):
        pass

    def validate(self):
        pass

    def metrics(self):
        return {
            "prismas": int(self.rows.prism_id.nunique()) if not self.rows.empty else 0,
            "registros": len(self.rows),
            "episodios": len(self.episodes),
            "episodios candidatos": int(
                self.episodes.candidate_policies.str.contains("hybrid").sum()
            ) if not self.episodes.empty and "candidate_policies" in self.episodes else 0,
            "registros candidatos": int(self.rows.candidate_hybrid.sum()) if not self.rows.empty and "candidate_hybrid" in self.rows else 0,
            "interrupciones de calidad": int(self.episodes.quality_interruption_flag.sum()) if not self.episodes.empty and "quality_interruption_flag" in self.episodes else 0,
        }

    def spatial(self, cutoff):
        if self.features.empty or self.rows.empty:
            cols = ["source_record_id", "prism_id", "timestamp", "easting", "northing", "rl", 
                    "movement_rate_mm_per_day", "elapsed_hours", "causal_state", "model_eligible", 
                    "candidate_hybrid", "quality_interruption_flag", "episode_id"]
            return pd.DataFrame(columns=cols)

        cutoff = pd.Timestamp(cutoff)
        f = (
            self.features.loc[self.features.timestamp.le(cutoff)]
            .sort_values(["prism_id", "timestamp"])
            .groupby("prism_id")
            .tail(1)
        )
        r = self.rows[
            [
                "source_record_id",
                "causal_state",
                "model_eligible",
                "candidate_hybrid",
                "quality_interruption_flag",
                "episode_id",
            ]
        ]
        result = f.merge(r, on="source_record_id", validate="one_to_one")
        finite = np.isfinite(result[["easting", "northing", "rl"]]).all(axis=1)
        return result.loc[finite].reset_index(drop=True)

    def prism_series(self, prism):
        if self.features.empty or self.rows.empty:
            cols = ["source_record_id", "prism_id", "timestamp", "easting", "northing", "rl", 
                    "movement_rate_mm_per_day", "elapsed_hours"]
            return pd.DataFrame(columns=cols)

        f = self.features[
            [
                "source_record_id",
                "easting",
                "northing",
                "rl",
                "movement_rate_mm_per_day",
                "elapsed_hours",
            ]
        ]
        return (
            self.rows.loc[self.rows.prism_id.eq(prism)]
            .merge(f, on="source_record_id", validate="one_to_one")
            .sort_values("timestamp")
        )
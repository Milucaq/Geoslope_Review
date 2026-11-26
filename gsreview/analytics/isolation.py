"""Inference only, from the fixed local manifest; never accept uploaded pickles."""

import hashlib
import io
import json
from importlib.metadata import version

import numpy as np
import pandas as pd
from joblib.numpy_pickle import NumpyUnpickler, _validate_fileobject_and_memmap
from sklearn.base import BaseEstimator, TransformerMixin

from gsreview.analytics.causal_features import causal_features, eligibility
from gsreview.domain.rules import ValidationError


class FrozenFeatureSelector(TransformerMixin, BaseEstimator):
    """Compatibility for the original pickled selector; only transform is needed."""

    def __init__(self, columns):
        self.columns = columns

    def transform(self, frame):
        return frame.loc[:, self.columns].astype(float)


class _TrustedUnpickler(NumpyUnpickler):
    def find_class(self, module, name):
        if (module, name) == ("src.model_preprocessing", "FeatureSelector"):
            return FrozenFeatureSelector
        if module == "src" or module.startswith("src."):
            raise ValidationError("Clase científica original no soportada.")
        return super().find_class(module, name)


class FrozenIsolationForest:
    """Block new inference unless both features and historical scores reproduce.

    Joblib 1.5.3's reader is used to remap the sole original custom class without
    importing arbitrary sibling src packages or altering sys.modules/sys.path.
    All 17 files are verified, and the exact deserialized bytes are hash-checked.
    """

    def __init__(self, reader):
        self.reader = reader
        reader.verify()
        source = reader.source
        self.metadata = json.loads((source / "models/phase5/model_metadata.json").read_text())
        self.config = json.loads((source / "config/phase5.json").read_text())
        self.selected = json.loads((source / "models/phase5/selected_features.json").read_text())["selected_features"]
        for package, expected in self.metadata["versions"].items():
            if version(package) != expected:
                raise ValidationError("Inferencia bloqueada: versión incompatible de " + package)
        relative = "models/phase5/isolation_forest.joblib"
        raw = (source / relative).read_bytes()
        if hashlib.sha256(raw).hexdigest() != reader.manifest["files"][relative]:
            raise ValidationError("Modelo alterado antes de deserializar.")
        buffer = io.BytesIO(raw)
        with _validate_fileobject_and_memmap(buffer, "frozen-isolation", None) as (handle, _):
            self.pipeline = _TrustedUnpickler("frozen-isolation", handle, True).load()
        if (len(self.selected) != 17 or self.selected != self.metadata["features"]
                or self.pipeline.named_steps["select"].columns != self.selected):
            raise ValidationError("Contrato de características incompatible.")
        self.threshold = self.metadata["thresholds"]["isolation_forest"]["q99"]
        self.validation = self._validate_history()
        reader.verify()

    def _score(self, features):
        eligible, reasons = eligibility(features, self.selected, self.config)
        output = features[["source_record_id", "prism_id", "timestamp"]].copy()
        output["model_eligible"] = eligible
        output["model_ineligibility_reason"] = reasons
        output["isolation_forest_score"] = np.nan
        if eligible.any():
            values = -self.pipeline.score_samples(features.loc[eligible])
            if not np.isfinite(values).all():
                raise ValidationError("Transformación o score no finito; inferencia bloqueada.")
            output.loc[eligible, "isolation_forest_score"] = values
        marks = pd.Series(pd.NA, index=output.index, dtype="boolean")
        marks.loc[eligible] = output.loc[eligible, "isolation_forest_score"].gt(self.threshold)
        output["isolation_forest_marked_q99"] = marks
        output["model_version"] = self.metadata["model_version"]
        output["inference_origin"] = "frozen_isolation_forest"
        return output

    def _validate_history(self):
        frozen = pd.read_csv(
            self.reader.source / "data/processed/phase4/west_wall_features.csv",
            float_precision="round_trip", low_memory=False,
        ).sort_values(["prism_id", "timestamp"], kind="stable").reset_index(drop=True)
        regenerated = causal_features(frozen)
        errors = []
        for feature in self.selected:
            actual, expected = regenerated[feature].to_numpy(float), frozen[feature].to_numpy(float)
            if not np.allclose(actual, expected, rtol=1e-12, atol=1e-12, equal_nan=True):
                raise ValidationError("Reproducción causal incompatible: " + feature)
            finite = np.isfinite(actual) & np.isfinite(expected)
            errors.append(float(np.max(np.abs(actual[finite]-expected[finite]))) if finite.any() else 0.)
        scored = self._score(regenerated).set_index("source_record_id")
        historical = self.reader.rows.set_index("source_record_id").loc[scored.index]
        actual = scored.isolation_forest_score.to_numpy(float)
        expected = historical.isolation_forest_score.to_numpy(float)
        if (not np.array_equal(scored.model_eligible, historical.model_eligible)
                or not np.allclose(actual, expected, rtol=1e-12, atol=1e-12, equal_nan=True)
                or not scored.isolation_forest_marked_q99.equals(
                    historical.isolation_forest_score.gt(self.threshold).astype("boolean").where(historical.model_eligible)
                )):
            raise ValidationError("Resultados históricos no reproducibles; inferencia bloqueada.")
        finite = np.isfinite(actual)
        return {"rows": len(scored), "features": len(self.selected),
                "max_feature_absolute_error": max(errors),
                "max_score_absolute_error": float(np.max(np.abs(actual[finite]-expected[finite]))),
                "rtol": 1e-12, "atol": 1e-12, "eligibility_and_q99_marks_exact": True}

    def infer(self, frame):
        self.reader.verify()
        result = self._score(causal_features(frame))
        available_from = pd.Timestamp(self.metadata["split_cutoffs"]["train_end_exclusive"], tz="UTC")
        available = result.timestamp.ge(available_from)
        result["model_available_at_observation"] = available
        result.loc[~available, "model_eligible"] = False
        result.loc[~available, "model_ineligibility_reason"] = "modelo no disponible en la fecha observada"
        result.loc[~available, "isolation_forest_score"] = np.nan
        result.loc[~available, "isolation_forest_marked_q99"] = pd.NA
        self.reader.verify()
        return result

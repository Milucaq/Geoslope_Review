"""Scenario data versions and shared analysis context, independent of widgets."""

import hashlib
import json

import numpy as np
import pandas as pd

from gsreview.analytics.causal_features import TARGET
from gsreview.domain.rules import ValidationError


def data_version(frame):
    if frame is None or frame.empty:
        return ""
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data.timestamp, utc=True)
    data = data.sort_values(["prism_id", "timestamp", "source_record_id"], kind="stable")
    # Include geometry and provenance columns as well as scalar observations.
    data = data.reindex(sorted(data.columns), axis=1)
    digest = hashlib.sha256("|".join(data.columns).encode())
    digest.update(pd.util.hash_pandas_object(data, index=False).values.tobytes())
    return digest.hexdigest()


def scenario_frame(state, scenario_id):
    if scenario_id == "external":
        return state.get("scenario_external_frame")
    if scenario_id == "john_henry" and state.get("scenario_jh_valid", False):
        return state.get("jh_records")
    return None


def at_cutoff(frame, cutoff):
    dates = pd.to_datetime(frame.timestamp, utc=True)
    cutoff = pd.to_datetime(cutoff, utc=True)
    if pd.isna(cutoff):
        raise ValidationError("Fecha de corte inválida.")
    return frame.loc[dates.le(cutoff)].copy()


def matching_scores(state, scenario_id, frame):
    stored = state.get("scenario_science_result", {})
    if stored.get("scenario") == scenario_id and stored.get("signature") == data_version(frame):
        return stored
    return {}


def matching_forecast(state, scenario_id, frame, prism=None, cutoff=None):
    stored = state.get("scenario_forecast_result", {})
    request = stored.get("request", ())
    if len(request) < 5 or request[0] != scenario_id or request[1] != data_version(frame):
        return {}
    if prism is not None and request[2] != prism:
        return {}
    if cutoff is not None and stored.get("cutoff") != pd.to_datetime(cutoff, utc=True).isoformat():
        return {}
    return stored


def analysis_context(frame, scenario_id, prism, cutoff, model_version="not_run", analysis_id="not_run"):
    if scenario_id not in {"external", "john_henry"} or frame is None or prism not in set(frame.prism_id):
        raise ValidationError("Contexto de revisión ajeno al escenario activo.")
    prefix = at_cutoff(frame.loc[frame.prism_id.eq(prism)], cutoff)
    if prefix.empty:
        raise ValidationError("El prisma no tiene observaciones al corte.")
    return {"scenario_id": scenario_id, "data_version": data_version(frame), "prism_id": str(prism),
            "cutoff": pd.to_datetime(cutoff, utc=True).isoformat(), "model_version": str(model_version),
            "analysis_id": str(analysis_id)}


def context_id(context):
    return hashlib.sha256(json.dumps(context, sort_keys=True).encode()).hexdigest()


def quality_summary(frame):
    if frame is None or frame.empty:
        return {"prisms": 0, "measurements": 0, "sectors": None, "known": 0, "missing": 0}
    values = pd.to_numeric(frame[TARGET], errors="coerce") if TARGET in frame else pd.Series(np.nan, index=frame.index)
    sector = "sector_topografico" if "sector_topografico" in frame else "sector" if "sector" in frame else None
    return {"prisms": frame.prism_id.nunique(), "measurements": len(frame),
            "sectors": frame[sector].nunique() if sector else None,
            "known": int(np.isfinite(values).sum()), "missing": int((~np.isfinite(values)).sum())}

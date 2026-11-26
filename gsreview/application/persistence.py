"""Durable, owner-scoped scenario snapshots and immutable report editions."""

from datetime import datetime, timezone
import hashlib
import io
import json
import uuid

import pandas as pd
from sqlalchemy import select

from gsreview.domain.rules import ValidationError
from gsreview.infrastructure.store import workspace_records as records
from gsreview.application.scenarios import select_scenario


def encode(value):
    if isinstance(value, pd.DataFrame):
        floats = {col: [None if pd.isna(v) else float(v) for v in value[col]]
                  for col in value.select_dtypes(include="floating")}
        return {"__frame__": value.to_json(orient="table", date_format="iso", date_unit="ns"),
                "floats": floats, "dtypes": {col: str(dtype) for col, dtype in value.dtypes.items()}}
    if isinstance(value, dict):
        return {str(k): encode(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [encode(v) for v in value]
    return value


def decode(value):
    if isinstance(value, dict):
        if "__frame__" in value:
            frame = pd.read_json(io.StringIO(value["__frame__"]), orient="table")
            for col, values in value["floats"].items():
                frame[col] = pd.array(values, dtype=frame[col].dtype)
            frame = frame.astype(value.get("dtypes", {}))
            return frame
        return {k: decode(v) for k, v in value.items()}
    if isinstance(value, list):
        return [decode(v) for v in value]
    return value


STATE_KEYS = ("scenario_external_frame", "scenario_external_source", "jh_records", "jh_asset",
              "jh_slope_config", "scenario_jh_settings", "scenario_jh_valid", "scenario_analysis_cutoff",
              "scenario_selected_prism", "scenario_science_result", "scenario_forecast_result")


def restore_state(state, snapshot):
    for key in list(state):
        if key.startswith(("scenario_", "science_", "jh_", "hu110_", "report_")) and key not in {"scenario_owner"}:
            del state[key]
    select_scenario(state, snapshot["type"])
    state.update(snapshot["state"])
    if "jh_slope_config" in state:
        state["jh_slope_config"] = tuple(state["jh_slope_config"])
    if state.get("scenario_forecast_result"):
        state["scenario_forecast_result"]["request"] = tuple(state["scenario_forecast_result"]["request"])
    state["scenario_saved_id"] = snapshot["id"]
    state["scenario_saved_revision"] = snapshot["revision"]
    state["scenario_selector"] = snapshot["type"]
    state["scenario_name"] = snapshot["name"]


class PersistenceService:
    def __init__(self, auth):
        self.auth = auth

    def _rows(self, connection, actor, kind):
        rows = connection.execute(select(records).where(records.c.actor == actor, records.c.kind == kind)
                                  .order_by(records.c.revision)).mappings()
        return [json.loads(row["payload"]) for row in rows]

    def listing(self, token, kind):
        actor = self.auth.authorize(token, "export" if kind == "report" else "read")
        with self.auth.store.tx() as connection:
            self.auth.guard(connection, token, "export" if kind == "report" else "read")
            rows = self._rows(connection, actor["id"], kind)
        return [decode(row) for row in rows]

    def scenario(self, token, object_id):
        found = [row for row in self.listing(token, "scenario") if row["id"] == object_id]
        if not found:
            raise ValidationError("Escenario no disponible para este usuario.")
        return found[-1]

    def save_scenario(self, token, name, state):
        actor = self.auth.authorize(token, "read")
        if not name.strip() or len(name) > 150 or state.get("active_scenario") not in {"external", "john_henry"}:
            raise ValidationError("Indica un nombre válido para un escenario nuevo.")
        from gsreview.application.workflow import scenario_frame, data_version
        frame = scenario_frame(state, state["active_scenario"])
        if frame is None or frame.empty:
            raise ValidationError("No hay mediciones que guardar.")
        with self.auth.store.tx() as connection:
            self.auth.guard(connection, token, "read")
            existing = self._rows(connection, actor["id"], "scenario")
            object_id = state.get("scenario_saved_id") or uuid.uuid4().hex
            previous = [r for r in existing if r["id"] == object_id]
            if state.get("scenario_saved_id") and not previous:
                raise ValidationError("Escenario no disponible para este usuario.")
            if previous and previous[-1]["type"] != state["active_scenario"]:
                raise ValidationError("Crea un escenario nuevo para cambiar el tipo.")
            revision = previous[-1]["revision"] if previous else 0
            if revision != state.get("scenario_saved_revision", 0):
                raise ValidationError("El escenario cambió en otra sesión; ábrelo antes de actualizarlo.")
            now = datetime.now(timezone.utc).isoformat()
            keys = [key for key in STATE_KEYS if not (
                state["active_scenario"] == "external" and key.startswith(("jh_", "scenario_jh_")) or
                state["active_scenario"] == "john_henry" and key.startswith("scenario_external_"))]
            payload = {"id": object_id, "name": name.strip(), "owner": actor["id"],
                       "type": state["active_scenario"], "revision": revision+1,
                       "created_at": previous[-1]["created_at"] if previous else now, "updated_at": now,
                       "state": {key: encode(state[key]) for key in keys if key in state}}
            from gsreview.application.scenario_review import ScenarioReviewService
            payload["reviews"] = ScenarioReviewService(self.auth, self.auth.store.path.parent / "scenario_reviews.db").repository.records(
                actor["id"], state["active_scenario"], data_version(frame)) if frame is not None else []
            connection.execute(records.insert().values(key=uuid.uuid4().hex, actor=actor["id"], kind="scenario",
                object_id=object_id, revision=revision+1, payload=json.dumps(payload, allow_nan=False), created_at=now))
            self.auth._audit(connection, actor["id"], "scenario_saved", object_id, {"revision": revision+1})
        return decode(payload)

    def save_report(self, token, payload, conclusions, notes, request_id, parent=None):
        actor = self.auth.authorize(token, "export")
        if not conclusions.strip() or len(conclusions) > 6000 or len(notes) > 6000 or not request_id:
            raise ValidationError("Las conclusiones son obligatorias (máximo 6000 caracteres por campo).")
        if payload.get("generated_by", {}).get("actor_id") != actor["id"]:
            raise ValidationError("El contenido del reporte no pertenece al usuario.")
        key = hashlib.sha256((actor["id"]+request_id).encode()).hexdigest()
        with self.auth.store.tx() as connection:
            self.auth.guard(connection, token, "export")
            cached = connection.execute(select(records.c.payload).where(records.c.key == key)).scalar()
            if cached:
                return json.loads(cached)
            previous = [r for r in self._rows(connection, actor["id"], "report") if r["id"] == parent]
            if parent and not previous:
                raise ValidationError("Reporte anterior no disponible.")
            now = datetime.now(timezone.utc).isoformat()
            report = {"id": uuid.uuid4().hex, "created_at": now, "owner": actor["id"], "parent": parent,
                      "version": previous[-1]["version"]+1 if previous else 1,
                      "conclusions": conclusions.strip(), "specialist_notes": notes,
                      "snapshot": payload}
            serialized = json.dumps(report, allow_nan=False)
            connection.execute(records.insert().values(key=key, actor=actor["id"], kind="report", object_id=report["id"],
                revision=report["version"], payload=serialized, created_at=now))
            self.auth._audit(connection, actor["id"], "report_archived", report["id"], {"version": report["version"]})
        # Return the committed JSON edition, detached from mutable caller objects.
        return json.loads(serialized)

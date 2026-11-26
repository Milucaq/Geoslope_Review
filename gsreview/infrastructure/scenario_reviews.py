"""Independent schema v1 for append-only scenario reviews; no historical migration."""

import json
from pathlib import Path
import uuid
import os

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from gsreview.domain.rules import ValidationError


class ScenarioReviews:
    def __init__(self, path):
        self.path = Path(path)

    def _engine(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            pass
        else:
            os.close(descriptor)
        return create_engine("sqlite:///" + str(self.path), poolclass=NullPool,
                             connect_args={"timeout": 20})

    def _schema(self, connection):
        version = connection.exec_driver_sql("PRAGMA user_version").scalar()
        if version not in (0, 1):
            raise ValidationError("Esquema de revisiones de escenario no soportado; no se migró ni alteró.")
        if version == 0:
            tables = connection.exec_driver_sql("SELECT name FROM sqlite_master WHERE type='table'").all()
            if tables:
                raise ValidationError("Base no reconocida; inicialización bloqueada.")
            connection.exec_driver_sql(
                "CREATE TABLE scenario_reviews (id TEXT PRIMARY KEY, actor TEXT NOT NULL, "
                "scenario TEXT NOT NULL, data_version TEXT NOT NULL, context TEXT NOT NULL, "
                "version INTEGER NOT NULL, payload TEXT NOT NULL, created_at TEXT NOT NULL, "
                "UNIQUE(actor, context, version))"
            )
            connection.exec_driver_sql("CREATE INDEX review_scope ON scenario_reviews(actor, scenario, data_version)")
            for verb in ("UPDATE", "DELETE"):
                connection.exec_driver_sql(
                    f"CREATE TRIGGER immutable_review_{verb.lower()} BEFORE {verb} ON scenario_reviews "
                    "BEGIN SELECT RAISE(ABORT,'Scenario reviews are append-only'); END"
                )
            connection.exec_driver_sql("PRAGMA user_version=1")

    def records(self, actor, scenario, data_version):
        if not self.path.exists():
            return []
        engine = self._engine()
        try:
            with engine.begin() as connection:
                self._schema(connection)
                rows = connection.execute(text(
                    "SELECT payload FROM scenario_reviews WHERE actor=:actor AND scenario=:scenario "
                    "AND data_version=:data_version ORDER BY created_at, version"
                ), {"actor": actor, "scenario": scenario, "data_version": data_version}).scalars()
                return [json.loads(row) for row in rows]
        finally:
            engine.dispose()

    def append(self, actor, context, expected_version, payload):
        engine = self._engine()
        try:
            with engine.connect() as connection:
                connection.exec_driver_sql("BEGIN IMMEDIATE")
                try:
                    self._schema(connection)
                    current = connection.execute(text(
                        "SELECT COALESCE(MAX(version),0) FROM scenario_reviews WHERE actor=:actor AND context=:context"
                    ), {"actor": actor, "context": context}).scalar()
                    if current != expected_version:
                        raise ValidationError("La revisión cambió. Recarga antes de guardar otra versión.")
                    saved = payload | {"version": current+1, "review_id": uuid.uuid4().hex}
                    connection.execute(text(
                        "INSERT INTO scenario_reviews VALUES (:id,:actor,:scenario,:data_version,:context,:version,:payload,:created_at)"
                    ), {"id": saved["review_id"], "actor": actor, "scenario": saved["scenario_id"],
                        "data_version": saved["data_version"], "context": context, "version": current+1,
                        "payload": json.dumps(saved, ensure_ascii=False, allow_nan=False), "created_at": saved["created_at"]})
                    connection.commit()
                    return saved
                except Exception:
                    connection.rollback()
                    raise
        finally:
            engine.dispose()

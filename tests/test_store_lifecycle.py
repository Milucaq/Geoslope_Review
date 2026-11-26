"""Real SQLite handles must close, without losing transactions or constraints."""

import sqlite3

import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from gsreview.infrastructure.store import Store


def test_connections_close_after_commit_and_rollback_and_data_survives(tmp_path):
    path = tmp_path / "isolated.db"
    store = Store(path)
    opened, closed = [], []
    event.listen(store.engine, "connect", lambda connection, _: opened.append(connection))
    event.listen(store.engine, "close", lambda connection, _: closed.append(connection))
    try:
        with store.tx() as connection:
            connection.execute(text("INSERT INTO app_metadata VALUES ('committed', 'yes')"))
        with pytest.raises(RuntimeError, match="rollback"):
            with store.tx() as connection:
                connection.execute(text("INSERT INTO app_metadata VALUES ('rolled_back', 'no')"))
                raise RuntimeError("rollback")
        assert store.user_count() == 0
        assert {row["key"] for row in store.list("app_metadata")} == {
            "schema_version", "committed",
        }
        assert len(opened) == len(closed) == 4
        for raw in opened:
            with pytest.raises(sqlite3.ProgrammingError, match="closed"):
                raw.execute("SELECT 1")
        reopened = Store(path)
        try:
            assert {row["key"] for row in reopened.list("app_metadata")} == {
                "schema_version", "committed",
            }
        finally:
            reopened.engine.dispose()
    finally:
        store.engine.dispose()


def test_every_new_connection_keeps_wal_foreign_keys_and_audit_immutable(tmp_path):
    store = Store(tmp_path / "isolated.db")
    try:
        for _ in range(2):
            with store.tx() as connection:
                assert connection.scalar(text("PRAGMA foreign_keys")) == 1
                assert connection.scalar(text("PRAGMA journal_mode")) == "wal"
        with store.tx() as connection:
            store.audit(connection, "synthetic-actor", "test", now=1)
        with pytest.raises(IntegrityError, match="append-only"):
            with store.tx() as connection:
                connection.execute(text("DELETE FROM audit_log"))
        assert len(store.list("audit_log")) == 1
    finally:
        store.engine.dispose()

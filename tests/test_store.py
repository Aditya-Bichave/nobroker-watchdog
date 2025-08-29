import sqlite3
import pytest

from nobroker_watchdog.store import StateStore


def test_state_store_closes_on_context_exit(tmp_path):
    db = tmp_path / "state.db"
    with StateStore(str(db)) as store:
        store.upsert_notification("1", "fp")
        assert store.already_notified("1", "fp") is True
    with pytest.raises(sqlite3.ProgrammingError):
        store.conn.execute("SELECT 1")


def test_state_store_closes_on_exception(tmp_path):
    db = tmp_path / "state.db"
    with pytest.raises(RuntimeError):
        with StateStore(str(db)) as store:
            store.upsert_notification("1", "fp")
            raise RuntimeError("boom")
    with pytest.raises(sqlite3.ProgrammingError):
        store.conn.execute("SELECT 1")

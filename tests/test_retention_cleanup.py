from datetime import datetime, timedelta
import importlib
from pathlib import Path


def _setup_temp_db(tmp_path, monkeypatch, state_file: Path | None = None):
    monkeypatch.setenv("SENTINELAI_DB_URL", f"sqlite:///{tmp_path}/retention.db")
    cleanup_file = state_file or tmp_path / "cleanup_state.txt"
    cleanup_file.parent.mkdir(parents=True, exist_ok=True)
    if cleanup_file.exists():
        cleanup_file.unlink()
    monkeypatch.setenv("SENTINELAI_RETENTION_STATE_FILE", str(cleanup_file))

    import app.db as db
    import app.db_models as models

    importlib.reload(db)
    importlib.reload(models)

    db.Base.metadata.create_all(bind=db.engine)
    db._last_cleanup_date = None
    return db, models, cleanup_file


def test_cleanup_deletes_only_old_records(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINELAI_RETENTION_DAYS", "3")
    db, models, _ = _setup_temp_db(tmp_path, monkeypatch)

    from app.config import settings

    settings.retention_days = 3

    session = db.SessionLocal()
    try:
        today = datetime.utcnow()
        old_timestamp = today - timedelta(days=settings.retention_days + 2)

        old_event = models.EventRecord(id="old", event_type="old", timestamp=old_timestamp)
        new_event = models.EventRecord(id="new", event_type="new", timestamp=today)

        old_snapshot = models.AnalysisSnapshot(
            mission_id="old",
            status="ok",
            summary="old",
            created_at=old_timestamp,
            event_count=1,
            window_minutes=60,
        )
        new_snapshot = models.AnalysisSnapshot(
            mission_id="new",
            status="ok",
            summary="new",
            created_at=today,
            event_count=1,
            window_minutes=60,
        )

        session.add_all([old_event, new_event, old_snapshot, new_snapshot])
        session.commit()

        db.maybe_cleanup_old_records(session)

        remaining_events = session.query(models.EventRecord).all()
        remaining_snapshots = session.query(models.AnalysisSnapshot).all()

        assert len(remaining_events) == 1
        assert remaining_events[0].id == "new"
        assert len(remaining_snapshots) == 1
        assert remaining_snapshots[0].mission_id == "new"
    finally:
        session.close()


def test_cleanup_runs_only_once_per_day(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINELAI_RETENTION_DAYS", "2")
    db, models, _ = _setup_temp_db(tmp_path, monkeypatch)

    from app.config import settings

    settings.retention_days = 2

    session = db.SessionLocal()
    try:
        today = datetime.utcnow()
        old_timestamp = today - timedelta(days=5)

        session.add_all(
            [
                models.EventRecord(id="old-1", event_type="old", timestamp=old_timestamp),
                models.AnalysisSnapshot(
                    mission_id="old-1",
                    status="ok",
                    summary="old",
                    created_at=old_timestamp,
                    event_count=1,
                    window_minutes=60,
                ),
            ]
        )
        session.commit()

        db.maybe_cleanup_old_records(session)

        assert session.query(models.EventRecord).count() == 0
        assert session.query(models.AnalysisSnapshot).count() == 0

        session.add_all(
            [
                models.EventRecord(id="old-2", event_type="old", timestamp=old_timestamp),
                models.AnalysisSnapshot(
                    mission_id="old-2",
                    status="ok",
                    summary="old",
                    created_at=old_timestamp,
                    event_count=1,
                    window_minutes=60,
                ),
            ]
        )
        session.commit()

        db.maybe_cleanup_old_records(session)

        assert session.query(models.EventRecord).count() == 1
        assert session.query(models.AnalysisSnapshot).count() == 1
    finally:
        session.close()


def test_cleanup_date_persists_across_restart(tmp_path, monkeypatch):
    monkeypatch.setenv("SENTINELAI_RETENTION_DAYS", "2")
    db, models, _ = _setup_temp_db(tmp_path, monkeypatch)

    from app.config import settings

    settings.retention_days = 2

    session = db.SessionLocal()
    try:
        today = datetime.utcnow()
        old_timestamp = today - timedelta(days=5)

        session.add(
            models.EventRecord(id="old", event_type="old", timestamp=old_timestamp)
        )
        session.commit()

        db.maybe_cleanup_old_records(session)
        assert session.query(models.EventRecord).count() == 0
    finally:
        session.close()

    import app.db as db_module
    import app.db_models as models_module

    importlib.reload(db_module)
    importlib.reload(models_module)
    db_module.Base.metadata.create_all(bind=db_module.engine)

    # Ensure the persisted cleanup date is respected after reload
    session = db_module.SessionLocal()
    try:
        today = datetime.utcnow()
        old_timestamp = today - timedelta(days=5)

        session.add(
            models_module.EventRecord(id="old-2", event_type="old", timestamp=old_timestamp)
        )
        session.commit()

        db_module.maybe_cleanup_old_records(session)

        assert session.query(models_module.EventRecord).count() == 1
    finally:
        session.close()

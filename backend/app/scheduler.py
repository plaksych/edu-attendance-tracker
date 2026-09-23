"""Standalone scheduler: python -m app.scheduler. Never imported by API lifespan."""

import logging
import signal
import threading

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.services.scheduler import run_tick

logger = logging.getLogger(__name__)
SCHEDULER_LOCK = 739_401
MAINTENANCE_LOCK = 739_402


def run_service(tick, lock_id: int, interval: int, stop=None, engine=None) -> None:
    """Leadership and business SQL use the same dedicated physical connection."""
    stop = stop or threading.Event()
    owned_engine = engine is None
    engine = engine or create_engine(settings.sqlalchemy_url, poolclass=NullPool,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=30000 -c lock_timeout=5000"})
    try:
        while not stop.is_set():
            try:
                with engine.connect() as connection:
                    acquired = connection.scalar(text("SELECT pg_try_advisory_lock(:key)"), {"key": lock_id})
                    pid = connection.scalar(text("SELECT pg_backend_pid()"))
                    connection.commit()
                    if acquired:
                        try:
                            while not stop.is_set():
                                if connection.invalidated:
                                    raise RuntimeError("leader_connection_invalidated")
                                if connection.scalar(text("SELECT pg_backend_pid()")) != pid:
                                    raise RuntimeError("leader_connection_changed")
                                connection.commit()
                                tick(connection)
                                stop.wait(interval)
                        finally:
                            try:
                                if not connection.invalidated:
                                    connection.rollback()
                                    connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": lock_id})
                                    connection.commit()
                            finally:
                                # Never return a possibly locked connection to a pool.
                                connection.invalidate()
            except Exception:
                logger.error("Service tick/leadership failed; reconnect and reacquire", exc_info=False)
            stop.wait(interval)
    finally:
        if owned_engine:
            engine.dispose()


def process_stop() -> threading.Event:
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_args: stop.set())
    return stop


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    run_service(run_tick, SCHEDULER_LOCK, settings.scheduler_interval_seconds, process_stop())


if __name__ == "__main__":
    main()

"""Stream worker runner — standalone consumer process.

Runs the Redis Stream consumers (alert, audit, dashboard) in a single asyncio
event loop, separate from the FastAPI API process. The API process only creates
the consumer groups in its lifespan; it must NOT run an infinite consume loop.
This module owns the actual consumption when run as a standalone process.

A lightweight dead-letter monitor is also started: it periodically logs the
depth of the dead-letter queue so failed messages (parked there by
``StreamWorker._dead_letter`` after ``max_retries``) are observable.

Run it as a separate process:

    python -m app.workers.run

Graceful shutdown: SIGINT/SIGTERM (Ctrl-C) cancels all loops, lets in-flight
message processing finish, and closes the DB and Redis connections.

Worker loop logic lives in ``app.workers.runner`` (shared with in-process mode).
This module only owns standalone-process setup: signal handling, DB/Redis init.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal

from app.core.logging_config import configure_logging
from app.infrastructure.database import close_db, init_db
from app.infrastructure.redis_client import close_redis, init_redis
from app.workers.runner import (
    DEAD_LETTER_POLL_SECONDS,
    _run_dead_letter_monitor,
    _run_worker,
    start_workers,
    stop_workers,
)

logger = logging.getLogger(__name__)

# Re-export helpers so existing tests that import from app.workers.run still work.
__all__ = [
    "DEAD_LETTER_POLL_SECONDS",
    "_run_worker",
    "_run_dead_letter_monitor",
    "run",
    "main",
]


def _install_signal_handlers(
    loop: asyncio.AbstractEventLoop, stop: asyncio.Event
) -> None:
    """Install SIGINT/SIGTERM handlers that set the stop event.

    ``loop.add_signal_handler`` is unavailable on Windows; fall back to
    ``signal.signal`` there.
    """

    def _request_stop() -> None:
        logger.info("shutdown_signal_received")
        stop.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _request_stop)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: _request_stop())


async def run() -> None:
    """Start all consumer loops and the DLQ monitor until shutdown."""
    configure_logging()
    await init_db()
    await init_redis()

    stop = asyncio.Event()
    _install_signal_handlers(asyncio.get_running_loop(), stop)

    tasks = start_workers(stop)
    try:
        await stop.wait()
    finally:
        await stop_workers(tasks)
        await close_redis()
        await close_db()


def main() -> None:
    """Console entrypoint."""
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run())


if __name__ == "__main__":
    main()

"""Shared worker lifecycle functions — used by BOTH run.py (standalone process)
and main.py (in-process asyncio tasks when workers_in_process=True).

Single responsibility: own the start/stop lifecycle of all stream worker tasks.
Neither entrypoint duplicates this logic.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging

from app.workers.alert_worker import AlertWorker
from app.workers.audit_worker import AuditWorker
from app.workers.base_worker import StreamWorker
from app.workers.dashboard_worker import DashboardWorker
from app.workers.dead_letter_handler import DeadLetterHandler

logger = logging.getLogger(__name__)

# How often (seconds) the dead-letter monitor reports queue depth.
DEAD_LETTER_POLL_SECONDS = 30


async def _run_worker(worker: StreamWorker, stop: asyncio.Event) -> None:
    """Continuously consume from a worker's stream until ``stop`` is set.

    Args:
        worker: The stream worker to drive.
        stop: Event that, when set, ends the consume loop.
    """
    await worker._create_group()
    logger.info("worker_started", extra={"stream": worker.stream_name})
    while not stop.is_set():
        try:
            await worker.consume(count=10, block=2000)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception(
                "worker_consume_error",
                extra={"stream": worker.stream_name, "error": str(exc)},
            )
            await asyncio.sleep(1)
    logger.info("worker_stopped", extra={"stream": worker.stream_name})


async def _run_dead_letter_monitor(
    handler: DeadLetterHandler, stop: asyncio.Event
) -> None:
    """Periodically log the dead-letter queue depth until ``stop`` is set.

    Args:
        handler: Dead-letter handler used to inspect the DLQ.
        stop: Event that, when set, ends the monitor loop.
    """
    logger.info("dead_letter_monitor_started")
    while not stop.is_set():
        try:
            count = await handler.get_dead_letter_count()
            if count:
                logger.warning("dead_letter_queue_depth", extra={"count": count})
            else:
                logger.debug("dead_letter_queue_empty")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("dead_letter_monitor_error", extra={"error": str(exc)})
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(stop.wait(), timeout=DEAD_LETTER_POLL_SECONDS)
    logger.info("dead_letter_monitor_stopped")


def start_workers(stop: asyncio.Event) -> list[asyncio.Task[None]]:
    """Create and return asyncio tasks for all stream workers and the DLQ monitor.

    Both ``run.py`` (standalone process) and ``main.py`` (in-process mode) call
    this to start the same set of workers.  The caller owns the ``stop`` event
    and is responsible for cancelling the returned tasks on shutdown.

    Args:
        stop: Event that, when set, signals all loops to exit cleanly.

    Returns:
        List of running asyncio tasks (one per worker + the DLQ monitor).
    """
    workers: list[StreamWorker] = [
        AlertWorker(),
        AuditWorker(),
        DashboardWorker(),
    ]
    dead_letter = DeadLetterHandler()

    tasks: list[asyncio.Task[None]] = [
        asyncio.create_task(_run_worker(w, stop)) for w in workers
    ]
    tasks.append(asyncio.create_task(_run_dead_letter_monitor(dead_letter, stop)))

    logger.info("worker_runner_ready", extra={"workers": len(workers)})
    return tasks


async def stop_workers(tasks: list[asyncio.Task[None]]) -> None:
    """Cancel all worker tasks and wait for them to finish.

    Args:
        tasks: Tasks returned by a prior ``start_workers`` call.
    """
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info("worker_runner_shutdown_complete")

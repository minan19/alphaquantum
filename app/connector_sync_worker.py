from __future__ import annotations

import logging
import time
from threading import Event, Thread
from uuid import uuid4

from app.connector_adapters import ConnectorAdapterRegistry
from app.engines.connector_engine import ConnectorEngine


class ConnectorSyncWorker:
    def __init__(
        self,
        *,
        engine: ConnectorEngine,
        adapters: ConnectorAdapterRegistry,
        poll_interval_seconds: int,
        retry_backoff_seconds: int,
        max_retries: int,
        leader_lock_enabled: bool = True,
        lease_seconds: int = 30,
        heartbeat_seconds: int = 10,
        worker_name: str = "connector-sync-worker",
    ) -> None:
        self._engine = engine
        self._adapters = adapters
        self._poll_interval_seconds = max(1, poll_interval_seconds)
        self._retry_backoff_seconds = max(5, retry_backoff_seconds)
        self._max_retries = max(1, max_retries)
        self._leader_lock_enabled = leader_lock_enabled
        self._lease_seconds = max(10, lease_seconds)
        self._heartbeat_seconds = max(3, min(heartbeat_seconds, self._lease_seconds - 1))
        self._worker_name = worker_name or "connector-sync-worker"
        self._owner_id = uuid4().hex
        self._is_leader = False
        self._next_heartbeat_at = 0.0
        self._stop_event = Event()
        self._thread: Thread | None = None
        self._logger = logging.getLogger("alpha_quantum.connector_worker")

    def start(self) -> None:
        if self.is_running():
            return
        self._stop_event.clear()
        self._thread = Thread(target=self._run_loop, name="connector-sync-worker", daemon=True)
        self._thread.start()
        self._logger.info(
            (
                "connector_sync_worker_started poll_interval=%s retry_backoff=%s "
                "max_retries=%s leader_lock=%s lease_seconds=%s heartbeat_seconds=%s owner=%s"
            ),
            self._poll_interval_seconds,
            self._retry_backoff_seconds,
            self._max_retries,
            self._leader_lock_enabled,
            self._lease_seconds,
            self._heartbeat_seconds,
            self._owner_id,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread is None:
            self._release_leadership()
            return
        self._thread.join(timeout=2.0)
        self._thread = None
        self._release_leadership()
        self._logger.info("connector_sync_worker_stopped")

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def is_leader(self) -> bool:
        if not self._leader_lock_enabled:
            return True
        return self._is_leader

    def run_once(self) -> bool:
        if not self._ensure_leadership():
            return False

        claimed = self._engine.claim_next_sync_job()
        if claimed is None:
            return False

        job, connector = claimed
        result = self._adapters.execute(connector, job)
        self._engine.finalize_sync_job(
            job=job,
            connector=connector,
            success=result.success,
            result_summary=result.summary,
            error_message=result.error_message,
            error_code=result.error_code,
            health_score=result.health_score,
            allow_retry=True,
            retry_backoff_seconds=self._retry_backoff_seconds,
            max_retries_default=self._max_retries,
        )
        return True

    def _run_loop(self) -> None:
        try:
            while not self._stop_event.is_set():
                try:
                    processed = self.run_once()
                except Exception:
                    self._logger.exception("connector_sync_worker_iteration_failed")
                    processed = False

                if processed:
                    continue
                self._stop_event.wait(self._poll_interval_seconds)
        finally:
            self._release_leadership()

    def _ensure_leadership(self) -> bool:
        if not self._leader_lock_enabled:
            return True

        now = time.monotonic()
        if self._is_leader:
            if now < self._next_heartbeat_at:
                return True
            renewed = self._engine.renew_worker_lease(
                worker_name=self._worker_name,
                owner_id=self._owner_id,
                lease_seconds=self._lease_seconds,
            )
            if renewed:
                self._next_heartbeat_at = now + self._heartbeat_seconds
                return True

            self._is_leader = False
            self._logger.warning(
                "connector_sync_worker_leadership_lost worker=%s owner=%s",
                self._worker_name,
                self._owner_id,
            )

        acquired = self._engine.acquire_worker_lease(
            worker_name=self._worker_name,
            owner_id=self._owner_id,
            lease_seconds=self._lease_seconds,
        )
        if acquired:
            self._is_leader = True
            self._next_heartbeat_at = now + self._heartbeat_seconds
            self._logger.info(
                "connector_sync_worker_leadership_acquired worker=%s owner=%s",
                self._worker_name,
                self._owner_id,
            )
            return True
        return False

    def _release_leadership(self) -> None:
        if not self._leader_lock_enabled:
            return
        if not self._is_leader:
            return
        try:
            self._engine.release_worker_lease(
                worker_name=self._worker_name,
                owner_id=self._owner_id,
            )
        except Exception:
            self._logger.exception(
                "connector_sync_worker_lease_release_failed worker=%s owner=%s",
                self._worker_name,
                self._owner_id,
            )
        finally:
            self._is_leader = False

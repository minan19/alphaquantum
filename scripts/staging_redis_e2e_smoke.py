from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import create_app


class SmokeFailure(RuntimeError):
    pass


def _check(condition: bool, label: str, detail: str, rows: list[tuple[str, str, str]]) -> None:
    rows.append(("PASS" if condition else "FAIL", label, detail))


class _TransientFailureRedisClient:
    def __init__(self, inner_client: object, transient_failures: int) -> None:
        self._inner_client = inner_client
        self._remaining = max(0, int(transient_failures))

    def _invoke(self, method: str, *args: object) -> object:
        if self._remaining > 0:
            self._remaining -= 1
            raise RuntimeError("simulated_redis_partition")
        return getattr(self._inner_client, method)(*args)

    def get(self, key: str) -> object:
        return self._invoke("get", key)

    def incr(self, key: str) -> object:
        return self._invoke("incr", key)

    def expire(self, key: str, ttl_seconds: int) -> object:
        return self._invoke("expire", key, ttl_seconds)

    def delete(self, key: str) -> object:
        return self._invoke("delete", key)


class _AlwaysFailRedisClient:
    def get(self, key: str) -> object:
        raise RuntimeError("simulated_redis_partition")

    def incr(self, key: str) -> object:
        raise RuntimeError("simulated_redis_partition")

    def expire(self, key: str, ttl_seconds: int) -> object:
        raise RuntimeError("simulated_redis_partition")

    def delete(self, key: str) -> object:
        raise RuntimeError("simulated_redis_partition")


def run_staging_redis_e2e_smoke(redis_url: str) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []

    with tempfile.TemporaryDirectory() as td:
        db_path = str(Path(td) / "staging_redis_e2e.db")
        run_id = uuid4().hex[:10]
        flood_username = f"flood_{run_id}"
        flood_password = os.environ.get("AQ_FLOOD_TEST_PASSWORD", "FloodUserPass123")

        env_keys = [
            "AQ_DATABASE_PATH",
            "AQ_AUTH_USERS",
            "AQ_ENABLE_DEMO_USERS",
            "AQ_JWT_SECRET",
            "AQ_ENV",
            "AQ_ALLOW_ALL_CORS",
            "AQ_AUTH_RATE_LIMIT_BACKEND",
            "AQ_AUTH_RATE_LIMIT_REDIS_URL",
            "AQ_AUTH_RATE_LIMIT_FAIL_OPEN",
            "AQ_AUTH_RATE_LIMIT_WINDOW_SECONDS",
            "AQ_AUTH_RATE_LIMIT_MAX_ATTEMPTS",
            "AQ_CONNECTOR_WORKER_ENABLED",
            "AQ_CONNECTOR_WORKER_LEADER_LOCK_ENABLED",
            "AQ_CONNECTOR_WORKER_LEASE_SECONDS",
            "AQ_CONNECTOR_WORKER_HEARTBEAT_SECONDS",
            "AQ_MARKET_OFFLINE",
            "AQ_MACRO_OFFLINE",
            "AQ_WEB_OFFLINE",
        ]
        original = {key: os.getenv(key) for key in env_keys}

        os.environ["AQ_DATABASE_PATH"] = db_path
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,"
            "manager:manager12345:manager,"
            "viewer:viewer12345:viewer,"
            f"{flood_username}:{flood_password}:viewer"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "staging-redis-e2e-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_ALLOW_ALL_CORS"] = "false"
        os.environ["AQ_AUTH_RATE_LIMIT_BACKEND"] = "redis"
        os.environ["AQ_AUTH_RATE_LIMIT_REDIS_URL"] = redis_url
        os.environ["AQ_AUTH_RATE_LIMIT_FAIL_OPEN"] = "false"
        os.environ["AQ_AUTH_RATE_LIMIT_WINDOW_SECONDS"] = "120"
        os.environ["AQ_AUTH_RATE_LIMIT_MAX_ATTEMPTS"] = "4"
        os.environ["AQ_CONNECTOR_WORKER_ENABLED"] = "false"
        os.environ["AQ_CONNECTOR_WORKER_LEADER_LOCK_ENABLED"] = "true"
        os.environ["AQ_CONNECTOR_WORKER_LEASE_SECONDS"] = "30"
        os.environ["AQ_CONNECTOR_WORKER_HEARTBEAT_SECONDS"] = "10"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        try:
            app_a = create_app()
            app_b = create_app()
            with TestClient(app_a) as client_a, TestClient(app_b) as client_b:
                limiter_backend_a = str(
                    getattr(client_a.app.state.auth_limiter, "_backend_name", "unknown")
                )
                limiter_backend_b = str(
                    getattr(client_b.app.state.auth_limiter, "_backend_name", "unknown")
                )
                _check(
                    limiter_backend_a == "redis" and limiter_backend_b == "redis",
                    "redis_backend_enabled",
                    f"instance_a={limiter_backend_a} instance_b={limiter_backend_b}",
                    rows,
                )

                flood_codes: list[int] = []
                for i in range(4):
                    active_client = client_a if i % 2 == 0 else client_b
                    response = active_client.post(
                        "/api/v1/auth/login",
                        json={"username": flood_username, "password": "wrong-password"},
                    )
                    flood_codes.append(response.status_code)
                _check(
                    all(code == 401 for code in flood_codes),
                    "distributed_login_flood_baseline",
                    f"codes={flood_codes}",
                    rows,
                )

                blocked_wrong = client_b.post(
                    "/api/v1/auth/login",
                    json={"username": flood_username, "password": "wrong-password"},
                )
                _check(
                    blocked_wrong.status_code == 429,
                    "distributed_login_flood_blocked",
                    f"status={blocked_wrong.status_code}",
                    rows,
                )

                blocked_valid = client_a.post(
                    "/api/v1/auth/login",
                    json={"username": flood_username, "password": flood_password},
                )
                _check(
                    blocked_valid.status_code == 429,
                    "distributed_login_flood_still_blocks_valid_until_window",
                    f"status={blocked_valid.status_code}",
                    rows,
                )

                manager_login_a = client_a.post(
                    "/api/v1/auth/login",
                    json={"username": "manager", "password": "manager12345"},
                )
                manager_login_b = client_b.post(
                    "/api/v1/auth/login",
                    json={"username": "manager", "password": "manager12345"},
                )
                _check(
                    manager_login_a.status_code == 200 and manager_login_b.status_code == 200,
                    "manager_auth_still_operational",
                    f"status_a={manager_login_a.status_code} status_b={manager_login_b.status_code}",
                    rows,
                )
                manager_token = manager_login_a.json().get("access_token", "")

                limiter_a = client_a.app.state.auth_limiter
                limiter_backend = getattr(limiter_a, "_backend", None)
                original_backend_client = getattr(limiter_backend, "_client", None)
                if limiter_backend is None or original_backend_client is None:
                    _check(
                        False,
                        "redis_chaos_backend_ready",
                        "missing_limiter_backend_or_client",
                        rows,
                    )
                else:
                    original_fail_open = bool(getattr(limiter_a, "_fail_open", True))
                    try:
                        limiter_a._fail_open = False
                        limiter_backend._client = _TransientFailureRedisClient(
                            original_backend_client,
                            transient_failures=2,
                        )
                        recovery_codes: list[int] = []
                        for delay in [0.0, 0.05, 0.10, 0.20]:
                            if delay > 0:
                                time.sleep(delay)
                            retry_response = client_a.post(
                                "/api/v1/auth/login",
                                json={"username": "manager", "password": "manager12345"},
                            )
                            recovery_codes.append(retry_response.status_code)
                            if retry_response.status_code == 200:
                                break
                        _check(
                            len(recovery_codes) > 0 and recovery_codes[0] == 503,
                            "redis_chaos_fail_closed_on_partition",
                            f"codes={recovery_codes}",
                            rows,
                        )
                        _check(
                            200 in recovery_codes,
                            "redis_chaos_reconnect_backoff_recovery",
                            f"codes={recovery_codes}",
                            rows,
                        )

                        limiter_a._fail_open = True
                        limiter_backend._client = _AlwaysFailRedisClient()
                        fail_open_response = client_a.post(
                            "/api/v1/auth/login",
                            json={"username": "manager", "password": "manager12345"},
                        )
                        _check(
                            fail_open_response.status_code == 200,
                            "redis_chaos_fail_open_policy",
                            f"status={fail_open_response.status_code}",
                            rows,
                        )
                    finally:
                        limiter_backend._client = original_backend_client
                        limiter_a._fail_open = original_fail_open

                create_connector = client_a.post(
                    "/api/v1/connectors",
                    headers={"Authorization": f"Bearer {manager_token}"},
                    json={
                        "company_name": "E2E Redis Co",
                        "connector_type": "finance_erp",
                        "provider": f"StagingRedisProvider-{run_id}",
                        "auth_mode": "oauth2",
                        "mapping": {
                            "id": "external_id",
                            "company": "company_name",
                            "type": "entry_type",
                            "amount": "amount",
                            "currency": "currency",
                            "date": "entry_date",
                        },
                    },
                )
                if create_connector.status_code != 201:
                    _check(
                        False,
                        "connector_create",
                        f"status={create_connector.status_code}",
                        rows,
                    )
                    return rows
                connector_id = int(create_connector.json()["id"])

                for _ in range(2):
                    create_job = client_a.post(
                        f"/api/v1/connectors/{connector_id}/sync-jobs",
                        headers={"Authorization": f"Bearer {manager_token}"},
                        json={
                            "trigger_mode": "manual",
                            "criticality": "high",
                            "max_attempts": 3,
                            "request_payload": {"source": "staging-redis-e2e"},
                        },
                    )
                    _check(
                        create_job.status_code == 201,
                        "sync_job_enqueue",
                        f"status={create_job.status_code}",
                        rows,
                    )

                worker_a = client_a.app.state.connector_sync_worker
                worker_b = client_b.app.state.connector_sync_worker

                processed_a = worker_a.run_once()
                _check(processed_a, "leader_instance_processes_job", f"processed={processed_a}", rows)
                _check(worker_a.is_leader(), "leader_lock_acquired_by_instance_a", "leader=True", rows)

                lease_after_a = client_a.app.state.connector_repository.get_worker_lease(
                    worker_name="connector-sync-worker"
                )
                lease_owner_a = str(lease_after_a.get("owner_id")) if lease_after_a else "none"
                _check(
                    lease_owner_a == getattr(worker_a, "_owner_id"),
                    "lease_owner_matches_instance_a",
                    f"owner={lease_owner_a}",
                    rows,
                )

                processed_b_while_a_alive = worker_b.run_once()
                _check(
                    processed_b_while_a_alive is False,
                    "standby_instance_blocked_while_leader_alive",
                    f"processed={processed_b_while_a_alive}",
                    rows,
                )

                worker_a.stop()
                processed_b_after_failover = worker_b.run_once()
                _check(
                    processed_b_after_failover,
                    "failover_instance_processes_after_leader_stop",
                    f"processed={processed_b_after_failover}",
                    rows,
                )
                _check(worker_b.is_leader(), "leader_lock_transferred_to_instance_b", "leader=True", rows)

                lease_after_b = client_b.app.state.connector_repository.get_worker_lease(
                    worker_name="connector-sync-worker"
                )
                lease_owner_b = str(lease_after_b.get("owner_id")) if lease_after_b else "none"
                _check(
                    lease_owner_b == getattr(worker_b, "_owner_id"),
                    "lease_owner_matches_instance_b",
                    f"owner={lease_owner_b}",
                    rows,
                )

                jobs_success = client_a.app.state.connector_engine.list_sync_jobs(
                    connector_id=connector_id,
                    status="success",
                    limit=10,
                )
                _check(
                    jobs_success.total == 2,
                    "all_jobs_completed_after_failover",
                    f"success_total={jobs_success.total}",
                    rows,
                )

                worker_b.stop()
        finally:
            for key in env_keys:
                value = original[key]
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    return rows


def _ensure_redis_connectivity(redis_url: str) -> None:
    try:
        import redis  # type: ignore
    except ImportError as exc:
        raise SmokeFailure("Redis package is not installed. Run: pip install redis") from exc

    try:
        client = redis.Redis.from_url(redis_url, decode_responses=True)
        client.ping()
    except Exception as exc:
        raise SmokeFailure(f"Redis connectivity failed for '{redis_url}': {exc}") from exc
    finally:
        close = getattr(locals().get("client", None), "close", None)
        if callable(close):
            close()


def _resolve_redis_url(cli_redis_url: str | None) -> str:
    if cli_redis_url and cli_redis_url.strip():
        return cli_redis_url.strip()
    env_value = os.getenv("AQ_STAGING_REDIS_URL") or os.getenv("AQ_AUTH_RATE_LIMIT_REDIS_URL")
    if env_value and env_value.strip():
        return env_value.strip()
    raise SmokeFailure("Redis URL is required. Use --redis-url or set AQ_STAGING_REDIS_URL.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Staging Redis E2E smoke: distributed login flood + connector lock failover."
    )
    parser.add_argument(
        "--redis-url",
        dest="redis_url",
        default=None,
        help="Redis connection URL (fallback: AQ_STAGING_REDIS_URL or AQ_AUTH_RATE_LIMIT_REDIS_URL).",
    )
    args = parser.parse_args()

    redis_url = _resolve_redis_url(args.redis_url)
    _ensure_redis_connectivity(redis_url)
    results = run_staging_redis_e2e_smoke(redis_url)

    fail_count = 0
    for status, label, detail in results:
        print(f"[{status}] {label} - {detail}")
        if status != "PASS":
            fail_count += 1
    print(f"SUMMARY total={len(results)} pass={len(results) - fail_count} fail={fail_count}")

    if fail_count > 0:
        raise SmokeFailure("Staging Redis E2E smoke failed.")

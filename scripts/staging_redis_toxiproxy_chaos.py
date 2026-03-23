from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from pathlib import Path
from urllib import error, request

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from app import create_app


class SmokeFailure(RuntimeError):
    pass


def _check(condition: bool, label: str, detail: str, rows: list[tuple[str, str, str]]) -> None:
    rows.append(("PASS" if condition else "FAIL", label, detail))


class ToxiproxyClient:
    def __init__(self, base_url: str) -> None:
        self._base_url = base_url.rstrip("/")

    def ensure_ready(self) -> None:
        payload = self._request("GET", "/version")
        version = str(
            payload.get("version")
            or payload.get("value")
            or payload.get("raw")
            or "unknown"
        )
        if not version:
            raise SmokeFailure("Toxiproxy is reachable but /version response is empty.")

    def recreate_proxy(self, *, name: str, listen: str, upstream: str) -> None:
        self.delete_proxy(name=name, ignore_not_found=True)
        self._request(
            "POST",
            "/proxies",
            {
                "name": name,
                "listen": listen,
                "upstream": upstream,
                "enabled": True,
            },
        )

    def delete_proxy(self, *, name: str, ignore_not_found: bool = False) -> None:
        try:
            self._request("DELETE", f"/proxies/{name}")
        except SmokeFailure as exc:
            if ignore_not_found and "HTTP 404" in str(exc):
                return
            raise

    def clear_toxics(self, *, proxy_name: str) -> None:
        payload = self._request("GET", f"/proxies/{proxy_name}")
        toxics = payload.get("toxics", [])
        for toxic in toxics:
            toxic_name = str(toxic.get("name", "")).strip()
            if not toxic_name:
                continue
            self.remove_toxic(proxy_name=proxy_name, toxic_name=toxic_name, ignore_not_found=True)

    def add_toxic(
        self,
        *,
        proxy_name: str,
        toxic_name: str,
        toxic_type: str,
        stream: str,
        attributes: dict[str, object],
    ) -> None:
        self._request(
            "POST",
            f"/proxies/{proxy_name}/toxics",
            {
                "name": toxic_name,
                "type": toxic_type,
                "stream": stream,
                "attributes": attributes,
            },
        )

    def add_disconnect_toxic(
        self,
        *,
        proxy_name: str,
        toxic_name: str,
        stream: str = "downstream",
    ) -> str:
        candidates: list[tuple[str, dict[str, object]]] = [
            ("reset_peer", {}),
            ("timeout", {"timeout": 1}),
        ]
        last_error: SmokeFailure | None = None
        for toxic_type, attributes in candidates:
            try:
                self.add_toxic(
                    proxy_name=proxy_name,
                    toxic_name=toxic_name,
                    toxic_type=toxic_type,
                    stream=stream,
                    attributes=attributes,
                )
                return toxic_type
            except SmokeFailure as exc:
                if "invalid toxic type" in str(exc):
                    last_error = exc
                    continue
                raise
        if last_error is not None:
            raise last_error
        raise SmokeFailure("Unable to add disconnect toxic: no valid toxic type candidate.")

    def remove_toxic(
        self,
        *,
        proxy_name: str,
        toxic_name: str,
        ignore_not_found: bool = False,
    ) -> None:
        try:
            self._request("DELETE", f"/proxies/{proxy_name}/toxics/{toxic_name}")
        except SmokeFailure as exc:
            if ignore_not_found and "HTTP 404" in str(exc):
                return
            raise

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        url = f"{self._base_url}{path}"
        data = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = request.Request(url=url, data=data, method=method, headers=headers)
        try:
            with request.urlopen(req, timeout=10) as response:
                raw = response.read().decode("utf-8").strip()
                if not raw:
                    return {}
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    return {"raw": raw}
                if isinstance(parsed, dict):
                    return parsed
                return {"value": parsed}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise SmokeFailure(f"Toxiproxy HTTP {exc.code} {method} {url}: {body}") from exc
        except error.URLError as exc:
            raise SmokeFailure(f"Toxiproxy request failed {method} {url}: {exc}") from exc


def _resolve_value(cli_value: str | None, env_key: str, default: str | None = None) -> str:
    if cli_value and cli_value.strip():
        return cli_value.strip()
    env_value = os.getenv(env_key)
    if env_value and env_value.strip():
        return env_value.strip()
    if default is not None:
        return default
    raise SmokeFailure(f"Required value missing: {env_key}")


def _resolve_float(cli_value: float | None, env_key: str, default: float) -> float:
    if cli_value is not None:
        return float(cli_value)
    raw = os.getenv(env_key)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw.strip())
    except ValueError as exc:
        raise SmokeFailure(f"Invalid float for {env_key}: {raw}") from exc


def _compose_proxy_redis_url(*, proxy_redis_url: str, socket_timeout_seconds: float) -> str:
    timeout_value = max(0.2, socket_timeout_seconds)
    joiner = "&" if "?" in proxy_redis_url else "?"
    return (
        f"{proxy_redis_url}{joiner}"
        f"socket_connect_timeout={timeout_value}&socket_timeout={timeout_value}&retry_on_timeout=False"
    )


def run_toxiproxy_chaos_smoke(
    *,
    toxiproxy_url: str,
    proxy_name: str,
    proxy_listen: str,
    proxy_upstream: str,
    proxy_redis_url: str,
    socket_timeout_seconds: float,
) -> list[tuple[str, str, str]]:
    rows: list[tuple[str, str, str]] = []
    toxiproxy = ToxiproxyClient(toxiproxy_url)
    toxiproxy.ensure_ready()
    toxiproxy.recreate_proxy(name=proxy_name, listen=proxy_listen, upstream=proxy_upstream)
    toxiproxy.clear_toxics(proxy_name=proxy_name)

    redis_url = _compose_proxy_redis_url(
        proxy_redis_url=proxy_redis_url,
        socket_timeout_seconds=socket_timeout_seconds,
    )
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
        "AQ_MARKET_OFFLINE",
        "AQ_MACRO_OFFLINE",
        "AQ_WEB_OFFLINE",
    ]
    original_env = {key: os.getenv(key) for key in env_keys}

    with tempfile.TemporaryDirectory() as td:
        os.environ["AQ_DATABASE_PATH"] = str(Path(td) / "staging_redis_chaos.db")
        os.environ["AQ_AUTH_USERS"] = (
            "admin:admin12345:admin,"
            "manager:manager12345:manager,"
            "viewer:viewer12345:viewer"
        )
        os.environ["AQ_ENABLE_DEMO_USERS"] = "false"
        os.environ["AQ_JWT_SECRET"] = "staging-redis-chaos-secret"
        os.environ["AQ_ENV"] = "development"
        os.environ["AQ_ALLOW_ALL_CORS"] = "false"
        os.environ["AQ_AUTH_RATE_LIMIT_BACKEND"] = "redis"
        os.environ["AQ_AUTH_RATE_LIMIT_REDIS_URL"] = redis_url
        os.environ["AQ_AUTH_RATE_LIMIT_FAIL_OPEN"] = "false"
        os.environ["AQ_AUTH_RATE_LIMIT_WINDOW_SECONDS"] = "120"
        os.environ["AQ_AUTH_RATE_LIMIT_MAX_ATTEMPTS"] = "4"
        os.environ["AQ_MARKET_OFFLINE"] = "true"
        os.environ["AQ_MACRO_OFFLINE"] = "true"
        os.environ["AQ_WEB_OFFLINE"] = "true"

        app = None
        client = None
        limiter = None
        original_fail_open = None
        try:
            app = create_app()
            client = TestClient(app)
            limiter = client.app.state.auth_limiter
            original_fail_open = bool(getattr(limiter, "_fail_open", True))

            baseline_login = client.post(
                "/api/v1/auth/login",
                json={"username": "manager", "password": "manager12345"},
            )
            _check(
                baseline_login.status_code == 200,
                "chaos_baseline_login",
                f"status={baseline_login.status_code}",
                rows,
            )

            toxic_reset = "hard_disconnect"
            toxic_reset_type = toxiproxy.add_disconnect_toxic(
                proxy_name=proxy_name,
                toxic_name=toxic_reset,
            )
            blocked_reset = client.post(
                "/api/v1/auth/login",
                json={"username": "manager", "password": "manager12345"},
            )
            _check(
                blocked_reset.status_code == 503,
                "chaos_hard_disconnect_fail_closed",
                f"status={blocked_reset.status_code} toxic={toxic_reset_type}",
                rows,
            )
            toxiproxy.remove_toxic(
                proxy_name=proxy_name,
                toxic_name=toxic_reset,
                ignore_not_found=True,
            )

            recovery_codes: list[int] = []
            for wait in [0.05, 0.10, 0.20, 0.40]:
                time.sleep(wait)
                recovered = client.post(
                    "/api/v1/auth/login",
                    json={"username": "manager", "password": "manager12345"},
                )
                recovery_codes.append(recovered.status_code)
                if recovered.status_code == 200:
                    break
            _check(
                200 in recovery_codes,
                "chaos_recovery_backoff",
                f"codes={recovery_codes}",
                rows,
            )

            toxic_latency = "high_latency"
            toxiproxy.add_toxic(
                proxy_name=proxy_name,
                toxic_name=toxic_latency,
                toxic_type="latency",
                stream="downstream",
                attributes={"latency": 2500, "jitter": 0},
            )
            blocked_latency = client.post(
                "/api/v1/auth/login",
                json={"username": "manager", "password": "manager12345"},
            )
            _check(
                blocked_latency.status_code == 503,
                "chaos_latency_timeout_fail_closed",
                f"status={blocked_latency.status_code}",
                rows,
            )
            toxiproxy.remove_toxic(
                proxy_name=proxy_name,
                toxic_name=toxic_latency,
                ignore_not_found=True,
            )

            if limiter is not None:
                limiter._fail_open = True

            toxic_fail_open = "fail_open_disconnect"
            toxic_fail_open_type = toxiproxy.add_disconnect_toxic(
                proxy_name=proxy_name,
                toxic_name=toxic_fail_open,
            )
            fail_open_login = client.post(
                "/api/v1/auth/login",
                json={"username": "manager", "password": "manager12345"},
            )
            _check(
                fail_open_login.status_code == 200,
                "chaos_fail_open_allows_auth",
                f"status={fail_open_login.status_code} toxic={toxic_fail_open_type}",
                rows,
            )
            toxiproxy.remove_toxic(
                proxy_name=proxy_name,
                toxic_name=toxic_fail_open,
                ignore_not_found=True,
            )
        finally:
            if limiter is not None and original_fail_open is not None:
                limiter._fail_open = original_fail_open
            if client is not None:
                client.close()
            for key in env_keys:
                original = original_env[key]
                if original is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original
            toxiproxy.clear_toxics(proxy_name=proxy_name)
            toxiproxy.delete_proxy(name=proxy_name, ignore_not_found=True)

    return rows


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=(
            "Staging Redis chaos smoke via Toxiproxy: hard disconnect + latency + "
            "fail-open/fail-closed + recovery backoff."
        )
    )
    parser.add_argument("--toxiproxy-url", default=None)
    parser.add_argument("--proxy-name", default=None)
    parser.add_argument("--proxy-listen", default=None)
    parser.add_argument("--proxy-upstream", default=None)
    parser.add_argument("--proxy-redis-url", default=None)
    parser.add_argument("--socket-timeout-seconds", type=float, default=None)
    args = parser.parse_args()

    toxiproxy_url = _resolve_value(
        args.toxiproxy_url,
        "AQ_TOXIPROXY_URL",
        default="http://127.0.0.1:8474",
    )
    proxy_name = _resolve_value(
        args.proxy_name,
        "AQ_CHAOS_REDIS_PROXY_NAME",
        default="aq_redis",
    )
    proxy_listen = _resolve_value(
        args.proxy_listen,
        "AQ_CHAOS_REDIS_PROXY_LISTEN",
        default="0.0.0.0:8666",
    )
    proxy_upstream = _resolve_value(
        args.proxy_upstream,
        "AQ_CHAOS_REDIS_UPSTREAM",
        default="127.0.0.1:6379",
    )
    proxy_redis_url = _resolve_value(
        args.proxy_redis_url,
        "AQ_CHAOS_REDIS_PROXY_URL",
        default="redis://127.0.0.1:8666/0",
    )
    socket_timeout_seconds = _resolve_float(
        args.socket_timeout_seconds,
        "AQ_CHAOS_REDIS_SOCKET_TIMEOUT_SECONDS",
        default=1.0,
    )

    results = run_toxiproxy_chaos_smoke(
        toxiproxy_url=toxiproxy_url,
        proxy_name=proxy_name,
        proxy_listen=proxy_listen,
        proxy_upstream=proxy_upstream,
        proxy_redis_url=proxy_redis_url,
        socket_timeout_seconds=socket_timeout_seconds,
    )

    fail_count = 0
    for status_value, label, detail in results:
        print(f"[{status_value}] {label} - {detail}")
        if status_value != "PASS":
            fail_count += 1
    print(f"SUMMARY total={len(results)} pass={len(results) - fail_count} fail={fail_count}")

    if fail_count > 0:
        raise SmokeFailure("Staging Redis Toxiproxy chaos smoke failed.")

from dataclasses import dataclass
import os


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


@dataclass(frozen=True)
class Settings:
    app_name: str
    app_version: str
    environment: str
    log_level: str
    allow_all_cors: bool
    cors_origins: list[str]
    cors_allow_credentials: bool
    database_path: str
    jwt_secret: str
    access_token_expire_minutes: int
    enable_demo_users: bool
    auth_rate_limit_window_seconds: int
    auth_rate_limit_max_attempts: int
    auth_rate_limit_backend: str
    auth_rate_limit_redis_url: str
    auth_rate_limit_fail_open: bool
    auth_users: str
    connector_worker_enabled: bool
    connector_worker_poll_interval_seconds: int
    connector_worker_retry_backoff_seconds: int
    connector_worker_max_retries: int
    connector_worker_leader_lock_enabled: bool
    connector_worker_lease_seconds: int
    connector_worker_heartbeat_seconds: int


def _parse_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _parse_int(value: str | None, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def get_settings() -> Settings:
    environment = os.getenv("AQ_ENV", "development")
    return Settings(
        app_name=os.getenv("AQ_APP_NAME", "Alpha Quantum"),
        app_version=os.getenv("AQ_APP_VERSION", "1.0.0"),
        environment=environment,
        log_level=os.getenv("AQ_LOG_LEVEL", "INFO").upper(),
        allow_all_cors=_parse_bool(os.getenv("AQ_ALLOW_ALL_CORS"), default=False),
        cors_origins=_parse_csv(os.getenv("AQ_CORS_ORIGINS")),
        cors_allow_credentials=_parse_bool(
            os.getenv("AQ_CORS_ALLOW_CREDENTIALS"), default=False
        ),
        database_path=os.getenv("AQ_DATABASE_PATH", "alpha_quantum.db"),
        jwt_secret=os.getenv("AQ_JWT_SECRET", "change-this-secret"),
        access_token_expire_minutes=_parse_int(
            os.getenv("AQ_ACCESS_TOKEN_EXPIRE_MINUTES"),
            default=120,
        ),
        enable_demo_users=_parse_bool(
            os.getenv("AQ_ENABLE_DEMO_USERS"),
            default=(environment == "development"),
        ),
        auth_rate_limit_window_seconds=_parse_int(
            os.getenv("AQ_AUTH_RATE_LIMIT_WINDOW_SECONDS"),
            default=60,
        ),
        auth_rate_limit_max_attempts=_parse_int(
            os.getenv("AQ_AUTH_RATE_LIMIT_MAX_ATTEMPTS"),
            default=5,
        ),
        auth_rate_limit_backend=os.getenv("AQ_AUTH_RATE_LIMIT_BACKEND", "memory"),
        auth_rate_limit_redis_url=os.getenv(
            "AQ_AUTH_RATE_LIMIT_REDIS_URL",
            "redis://127.0.0.1:6379/0",
        ),
        auth_rate_limit_fail_open=_parse_bool(
            os.getenv("AQ_AUTH_RATE_LIMIT_FAIL_OPEN"),
            default=True,
        ),
        auth_users=os.getenv("AQ_AUTH_USERS", ""),
        connector_worker_enabled=_parse_bool(
            os.getenv("AQ_CONNECTOR_WORKER_ENABLED"),
            default=False,
        ),
        connector_worker_poll_interval_seconds=_parse_int(
            os.getenv("AQ_CONNECTOR_WORKER_POLL_INTERVAL_SECONDS"),
            default=15,
        ),
        connector_worker_retry_backoff_seconds=_parse_int(
            os.getenv("AQ_CONNECTOR_WORKER_RETRY_BACKOFF_SECONDS"),
            default=60,
        ),
        connector_worker_max_retries=_parse_int(
            os.getenv("AQ_CONNECTOR_WORKER_MAX_RETRIES"),
            default=3,
        ),
        connector_worker_leader_lock_enabled=_parse_bool(
            os.getenv("AQ_CONNECTOR_WORKER_LEADER_LOCK_ENABLED"),
            default=True,
        ),
        connector_worker_lease_seconds=_parse_int(
            os.getenv("AQ_CONNECTOR_WORKER_LEASE_SECONDS"),
            default=30,
        ),
        connector_worker_heartbeat_seconds=_parse_int(
            os.getenv("AQ_CONNECTOR_WORKER_HEARTBEAT_SECONDS"),
            default=10,
        ),
    )

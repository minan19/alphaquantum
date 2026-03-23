from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute /api/v1/* success ratio from audit_logs and evaluate error budget."
    )
    parser.add_argument(
        "--db-path",
        default="alpha_quantum.db",
        help="SQLite DB path (default: alpha_quantum.db)",
    )
    parser.add_argument(
        "--lookback-hours",
        type=int,
        default=24,
        help="Lookback window in hours (default: 24)",
    )
    parser.add_argument(
        "--target-success-ratio",
        type=float,
        default=99.0,
        help="Target success ratio percentage (default: 99.0)",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    db_path = Path(args.db_path).expanduser().resolve()
    if not db_path.exists():
        print(f"ERROR db_not_found path={db_path}", file=sys.stderr)
        return 1

    now = int(time.time())
    start_ts = now - (max(1, args.lookback_hours) * 3600)

    conn = sqlite3.connect(str(db_path))
    try:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN status_code >= 200 AND status_code < 400 THEN 1 ELSE 0 END) AS success_count,
                SUM(CASE WHEN status_code >= 500 THEN 1 ELSE 0 END) AS server_error_count
            FROM audit_logs
            WHERE path LIKE '/api/v1/%'
              AND created_at >= ?
            """,
            (start_ts,),
        ).fetchone()
    finally:
        conn.close()

    total = int(row["total"] or 0)
    success_count = int(row["success_count"] or 0)
    server_error_count = int(row["server_error_count"] or 0)
    success_ratio = (success_count / total * 100.0) if total > 0 else 100.0
    error_budget_used = max(0.0, 100.0 - success_ratio)
    allowed_error = max(0.0, 100.0 - float(args.target_success_ratio))
    status = "PASS" if success_ratio >= float(args.target_success_ratio) else "FAIL"

    print(
        "ERROR_BUDGET_REPORT "
        f"status={status} "
        f"lookback_hours={args.lookback_hours} "
        f"total={total} "
        f"success_count={success_count} "
        f"server_error_count={server_error_count} "
        f"success_ratio={success_ratio:.2f}% "
        f"target={float(args.target_success_ratio):.2f}% "
        f"budget_used={error_budget_used:.2f}% "
        f"budget_allowed={allowed_error:.2f}%"
    )
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

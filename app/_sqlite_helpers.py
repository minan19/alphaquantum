"""F2: SQLite repository helpers — type-safe wrappers.

`cursor.lastrowid` is typed `int | None` by stdlib because pre-INSERT it
is None. After a successful INSERT against an INTEGER PRIMARY KEY column,
it's always a non-zero int. The previous code did:

    row_id = int(cur.lastrowid)

which mypy strict mode flags as `arg-type` (int(int|None) invalid). The
typical fixes — `cast(int, ...)`, `assert ... is not None`, inline
`# type: ignore` — all spread tribal knowledge across the repos.

This helper centralizes the assumption: after INSERT, lastrowid is non-None.

Usage:
    cursor.execute("INSERT INTO ...")
    row_id = new_row_id(cursor)
"""
from __future__ import annotations

import sqlite3


def new_row_id(cursor: sqlite3.Cursor) -> int:
    """Return cursor.lastrowid as a non-None int.

    Raises RuntimeError if lastrowid is None — would indicate the cursor
    didn't execute an INSERT (or the INSERT failed silently). Should never
    happen in well-formed repository code.
    """
    rid = cursor.lastrowid
    if rid is None:
        raise RuntimeError(
            "cursor.lastrowid is None — expected INSERT to produce a row id"
        )
    return int(rid)

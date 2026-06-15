"""M3: Copilot SQL guard — defense-in-depth read-only enforcement.

Mevcut copilot whitelist template'leri sadece SELECT üretir; bu modül
şu garantiyi defense-in-depth katmanı olarak ekler: çalıştırılmadan
önce SQL string yine de SELECT-only mu doğrulanır. Whitelist'in
bozulması (yeni template yazılırken hata) durumunda runtime'da yakalanır.
"""
from __future__ import annotations

import re


class ReadOnlyViolation(ValueError):
    """SQL salt-okunur değil — copilot reddetmeli."""


# DDL/DML/transaction kontrol keyword'leri — çoklu ifade kabul edilmez
# (statement separator `;` kullanım için ayrıca reddedilir).
_FORBIDDEN_KEYWORDS = (
    "INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "TRUNCATE",
    "CREATE", "REPLACE", "MERGE", "GRANT", "REVOKE",
    "ATTACH", "DETACH", "PRAGMA", "VACUUM", "REINDEX",
    "EXEC", "EXECUTE", "CALL",
)
_KEYWORD_BOUNDARY = re.compile(
    r"\b(" + "|".join(_FORBIDDEN_KEYWORDS) + r")\b",
    re.IGNORECASE,
)


def _strip_comments(sql: str) -> str:
    # `--` satır yorumu + `/* ... */` blok yorumu — keyword saklamayı engelle.
    sql = re.sub(r"--[^\n]*", " ", sql)
    sql = re.sub(r"/\*.*?\*/", " ", sql, flags=re.DOTALL)
    return sql


def assert_select_only(sql: str) -> None:
    """SQL yalnızca tek bir SELECT/WITH ifadesi olabilir.

    Reddedilir:
    - Boş veya whitespace-only
    - SELECT/WITH dışında başlayan
    - DDL/DML keyword içeren (yorum dışı)
    - Çoklu ifade (statement separator `;` ile)
    """
    if not sql or not sql.strip():
        raise ReadOnlyViolation("Boş SQL")

    stripped = _strip_comments(sql).strip()
    # Trailing semicolon zararsız; ortada `;` çoklu ifade demek.
    inner = stripped.rstrip(";").strip()
    if ";" in inner:
        raise ReadOnlyViolation("Çoklu SQL ifadesine izin yok")

    upper = inner.upper()
    if not (upper.startswith("SELECT") or upper.startswith("WITH")):
        raise ReadOnlyViolation("Sadece SELECT/WITH sorgularına izin var")

    match = _KEYWORD_BOUNDARY.search(inner)
    if match:
        raise ReadOnlyViolation(
            f"Yasaklı SQL anahtar kelimesi: {match.group(1).upper()}"
        )

"""Design Token Programı — Faz 1 · Seed.

`docs/design-tokens/wcag-report.json` (Faz 0 çıktısı, kilitli kaynak) içeriğini
`color_tokens` tablosuna idempotent upsert eder.

DEĞERLER FAZ 0'DAN BİREBİR GELİR — bu dosyada hex/sayı **gözle yazılmaz**, **yeniden
hesaplanmaz**, **yer tutucu konulmaz**. Yalnız anahtar→label/category eşlemesi
ve display sırası burada tanımlıdır (sunum metadata'sı).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.color_token_repository import ColorTokenRepository

# ----------------------------------------------------------------------------
# Anahtar metadata'sı (sunum bilgileri — değer DEĞİL).
# Faz 0 anahtar adlarıyla birebir eşleşir.
# ----------------------------------------------------------------------------

# (label, category, display_order) per (scope, key)
_CORE_META: dict[str, tuple[str, str, int]] = {
    "bg_primary":             ("Arkaplan — birincil",         "background", 10),
    "bg_secondary":           ("Arkaplan — ikincil",          "background", 11),
    "bg_tertiary":            ("Arkaplan — üçüncül",          "background", 12),
    "surface_01":             ("Yüzey 01",                    "surface",    20),
    "surface_02":             ("Yüzey 02",                    "surface",    21),
    "surface_03":             ("Yüzey 03",                    "surface",    22),
    "border":                 ("Kenarlık",                    "border",     30),
    "text_primary":           ("Metin — birincil (~15:1)",    "text",       40),
    "text_secondary":         ("Metin — ikincil (~8:1)",      "text",       41),
    "text_muted":             ("Metin — soluk (~4.5:1)",      "text",       42),
    "text_inverse":           ("Metin — ters",                "text",       43),
    "status_success":         ("Durum — başarı",              "status",     50),
    "status_success_surface": ("Durum — başarı yüzeyi",       "status",     51),
    "status_warning":         ("Durum — uyarı",               "status",     52),
    "status_warning_surface": ("Durum — uyarı yüzeyi",        "status",     53),
    "status_error":           ("Durum — hata (= negatif)",    "status",     54),
    "status_error_surface":   ("Durum — hata yüzeyi",         "status",     55),
    "status_info":            ("Durum — bilgi",               "status",     56),
    "status_info_surface":    ("Durum — bilgi yüzeyi",        "status",     57),
    "focus_ring":             ("Focus halkası",               "focus",      60),
}

# Modül scope'larında kullanılan kimlik anahtarları için ortak meta.
# Bazı anahtarlar yalnız bir modülde geçer (örn. on_brand sadece aq'da,
# cta_text_weight sadece corpos'ta) — eksik anahtarlar atlanır.
_MODULE_META: dict[str, tuple[str, str, int]] = {
    "brand":           ("Marka",                "brand",  10),
    "brand_hover":     ("Marka — hover",        "brand",  11),
    "cta":             ("CTA dolgu",            "cta",    20),
    "cta_hover":       ("CTA — hover",          "cta",    21),
    "cta_text":        ("CTA — metin rengi",    "cta",    22),
    "cta_text_weight": ("CTA — metin ağırlığı", "cta",    23),
    "on_brand":        ("Marka yüzeyi",         "brand",  30),
    "accent":          ("Aksan (veri)",         "accent", 40),
    "accent_light":    ("Aksan — açık",         "accent", 41),
    "link_back":       ("Çatıya geri-dönüş",    "accent", 50),
}


def _default_foundation_path() -> Path:
    """Faz 0 wcag-report.json varsayılan konum."""
    return Path(__file__).resolve().parent.parent / "docs" / "design-tokens" / "wcag-report.json"


def build_seed_items(
    foundation_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Faz 0 JSON dosyasından upsert payload'ı üret.

    Çıktı: ColorTokenRepository.upsert_many için hazır liste.
    Sıralama deterministic (scope → display_order → key).
    """
    path = foundation_path or _default_foundation_path()
    if not path.is_file():
        raise FileNotFoundError(
            f"Foundation kaynağı bulunamadı: {path}. "
            "Faz 0 çıktısı (docs/design-tokens/wcag-report.json) gerekli."
        )
    payload = json.loads(path.read_text(encoding="utf-8"))

    items: list[dict[str, Any]] = []

    # core
    core = payload.get("core", {})
    for key, raw_value in core.items():
        if key == "theme":  # JSON'da meta alanı, token değil
            continue
        if raw_value is None:  # null değerli token DB'ye yazılmaz
            continue
        meta = _CORE_META.get(key)
        if meta is None:
            # Foundation'a yeni anahtar eklenmiş ama burada metadata yoksa
            # explicit hata — sessiz veri kaybı olmasın.
            raise KeyError(
                f"core anahtarı {key!r} için metadata tanımlı değil. "
                "app/color_token_seed.py içindeki _CORE_META'yı güncelle."
            )
        label, category, order = meta
        items.append(
            {
                "scope": "core",
                "key": key,
                "value": str(raw_value),
                "label": label,
                "category": category,
                "display_order": order,
            }
        )

    # modules (aq / finos / corpos)
    modules = payload.get("modules", {})
    for scope, mod_tokens in modules.items():
        if scope not in ("aq", "finos", "corpos"):
            raise ValueError(f"JSON'da beklenmeyen modül scope: {scope!r}")
        for key, raw_value in mod_tokens.items():
            if key == "scope":  # JSON'da kendine referans, token değil
                continue
            if raw_value is None:  # link_back null olabilir (aq için)
                continue
            meta = _MODULE_META.get(key)
            if meta is None:
                raise KeyError(
                    f"Modül anahtarı {scope}.{key!r} için metadata tanımlı değil. "
                    "app/color_token_seed.py içindeki _MODULE_META'yı güncelle."
                )
            label, category, order = meta
            items.append(
                {
                    "scope": scope,
                    "key": key,
                    "value": str(raw_value),
                    "label": label,
                    "category": category,
                    "display_order": order,
                }
            )

    # deterministic sıralama
    items.sort(key=lambda it: (str(it["scope"]), int(it["display_order"]), str(it["key"])))
    return items


def seed_color_tokens(
    repo: ColorTokenRepository,
    foundation_path: Path | None = None,
) -> int:
    """Idempotent seed — tablo dolu olsa bile aynı sonucu üretir.

    Dönüş: upsert edilen satır sayısı.
    """
    items = build_seed_items(foundation_path=foundation_path)
    return repo.upsert_many(items)

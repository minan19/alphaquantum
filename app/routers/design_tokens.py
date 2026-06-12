"""Design Token Programı — Faz 1+4 · Read + Write endpoints.

GET /api/v1/design-tokens                 — public read (Faz 1)
PATCH /api/v1/design-tokens               — admin write (Faz 4)
POST /api/v1/design-tokens/reset          — admin factory reset (Faz 4)
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.color_token_repository import (
    VALID_SCOPES,
    ColorTokenRepository,
    GovernanceViolation,
    assert_governance,
)
from app.color_token_seed import build_seed_items
from app.models import (
    ColorTokenListResponse,
    ColorTokenPatchRequest,
    ColorTokenPatchResponse,
    ColorTokenResetRequest,
    ColorTokenResetResponse,
    ColorTokenResponse,
    ColorTokenRestoreRequest,
    ColorTokenRestoreResponse,
    ColorTokenScope,
    ColorTokenSnapshotCreateRequest,
    ColorTokenSnapshotCreateResponse,
    ColorTokenSnapshotListResponse,
    ColorTokenSnapshotSource,
    ColorTokenSnapshotSummary,
    UserProfile,
)
from app.security import require_permissions

router = APIRouter()

# Renk token değer formatı: #RRGGBB (büyük/küçük harf serbest).
_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")

# Sayısal değer kabul edilen anahtarlar (corpos.cta_text_weight gibi).
_NUMERIC_KEYS: frozenset[str] = frozenset({"cta_text_weight"})


def _repo(request: Request) -> ColorTokenRepository:
    return cast(ColorTokenRepository, request.app.state.color_token_repo)


def _validate_value(key: str, value: str | int) -> str | int:
    """Bir token değerinin formatını doğrula.

    - Renk anahtarları: '#RRGGBB' bekler (string).
    - Numeric anahtarlar (cta_text_weight): int kabul.
    """
    if key in _NUMERIC_KEYS:
        if not isinstance(value, int):
            try:
                return int(value)
            except (TypeError, ValueError) as err:
                raise HTTPException(
                    status_code=422,
                    detail=f"'{key}' için sayısal değer beklendi: {value!r}",
                ) from err
        return value
    # Color key
    if not isinstance(value, str) or not _HEX_RE.match(value):
        raise HTTPException(
            status_code=422,
            detail=f"'{key}' geçersiz renk değeri (#RRGGBB beklendi): {value!r}",
        )
    return value.upper()


@router.get(
    "/api/v1/design-tokens",
    response_model=ColorTokenListResponse,
    tags=["design-tokens"],
)
def list_tokens(
    request: Request,
    scope: ColorTokenScope | None = Query(
        default=None,
        description="Opsiyonel scope filtresi (core/aq/finos/corpos).",
    ),
) -> ColorTokenListResponse:
    """Tasarım token'larını listele.

    `scope` verilmezse hepsini döner (deterministic sıralama).
    Frontend `getTokens` bu ucu çağırır; başarısızlıkta `DEFAULT_TOKENS`'a düşer.
    """
    if scope is not None and scope not in VALID_SCOPES:
        raise HTTPException(status_code=400, detail=f"invalid scope: {scope}")

    repo = _repo(request)
    rows = repo.list_tokens(scope=scope)
    tokens = [
        ColorTokenResponse(
            scope=cast(ColorTokenScope, row["scope"]),
            key=str(row["key"]),
            value=str(row["value"]),
            label=str(row["label"]),
            category=str(row["category"]),
            display_order=int(row["display_order"]),
            updated_at=int(row["updated_at"]),
        )
        for row in rows
    ]
    return ColorTokenListResponse(
        tokens=tokens,
        scope_filter=scope,
        seeded_at=repo.latest_updated_at(),
    )


@router.patch(
    "/api/v1/design-tokens",
    response_model=ColorTokenPatchResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
        422: {"description": "Governance ihlali veya geçersiz değer"},
    },
)
def patch_tokens(
    payload: ColorTokenPatchRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenPatchResponse:
    """Faz 4+5: panel yazma ucu — pre-save snapshot ile.

    Tek scope'ta delta update. Governance API'de zorlanır:
      - Modül scope'unda core-sahipli key → 422 (assertGovernance fırlar)
      - Bilinmeyen key → 422 (ne core ne module whitelist'inde)
      - Geçersiz hex değer → 422 (_validate_value)

    Faz 5: yazımdan ÖNCE mevcut scope durumu 'pre_save' snapshot'u olarak
    yazılır → "⤺ Bir Önceki" tek tıkla bu noktaya döner.
    """
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {payload.scope}")

    # Önce hepsini doğrula (early fail; partial write yok).
    for key, value in payload.changes.items():
        # Governance: scope/key whitelist
        try:
            assert_governance(payload.scope, key)
        except GovernanceViolation as err:
            raise HTTPException(status_code=422, detail=str(err)) from err
        # Value format
        _validate_value(key, value)

    repo = _repo(request)

    # Faz 5: pre-save snapshot. Boş scope'ta da yazılır (geri dönüş hâlâ mümkün).
    pre_payload = repo.snapshot_payload(payload.scope)
    repo.create_snapshot(
        scope=payload.scope,
        source="pre_save",
        label=f"Kaydetme öncesi ({len(payload.changes)} alan)",
        payload=pre_payload,
        created_by=getattr(user, "email", None) or getattr(user, "id", None),
    )

    updated: list[str] = []
    for key, raw_value in payload.changes.items():
        normalized = _validate_value(key, raw_value)
        ok = repo.update_value(payload.scope, key, str(normalized))
        if ok:
            updated.append(key)

    return ColorTokenPatchResponse(
        scope=payload.scope,
        updated=updated,
        updated_count=len(updated),
    )


@router.post(
    "/api/v1/design-tokens/reset",
    response_model=ColorTokenResetResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
    },
)
def reset_scope(
    payload: ColorTokenResetRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenResetResponse:
    """Faz 4+5: bir scope'u Faz 0 seed'ine döndür — pre-reset snapshot ile.

    İki adımlı onay UI'da; backend tek atomik op:
      0. Mevcut scope durumu 'pre_reset' snapshot'u olarak yazılır (Faz 5)
      1. Belirtilen scope'taki tüm token'ları sil
      2. wcag-report.json'dan o scope için seed'i upsert et
    """
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {payload.scope}")

    # Foundation kilidini oku, scope filter uygula
    foundation_path = (
        Path(__file__).resolve().parent.parent.parent
        / "docs" / "design-tokens" / "wcag-report.json"
    )
    seed_items = [it for it in build_seed_items(foundation_path) if it["scope"] == payload.scope]

    repo = _repo(request)

    # Faz 5: fabrika reset öncesi de snapshot al ki kullanıcı geri dönebilsin.
    pre_payload = repo.snapshot_payload(payload.scope)
    if pre_payload:  # boş scope'ta snapshot anlamsız
        repo.create_snapshot(
            scope=payload.scope,
            source="pre_reset",
            label="Fabrika ayarlarına dönüş öncesi",
            payload=pre_payload,
            created_by=getattr(user, "email", None) or getattr(user, "id", None),
        )

    deleted = repo.delete_scope(payload.scope)
    inserted = repo.upsert_many(seed_items)

    return ColorTokenResetResponse(
        scope=payload.scope,
        deleted=deleted,
        inserted=inserted,
    )


# ---------------------------------------------------------------------------
# Faz 5 — Snapshot endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/api/v1/design-tokens/snapshots",
    response_model=ColorTokenSnapshotListResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
    },
)
def list_snapshots(
    request: Request,
    scope: ColorTokenScope = Query(..., description="Snapshot listelenecek scope."),
    limit: int = Query(default=20, ge=1, le=100),
    _user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenSnapshotListResponse:
    """Faz 5: bir scope için snapshot listesi (yeni→eski).

    Payload taşımaz; UI'da liste hafif kalsın. Tek snapshot'a `restore` ile gidilir.
    """
    if scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {scope}")

    repo = _repo(request)
    rows = repo.list_snapshots(scope=scope, limit=limit)
    return ColorTokenSnapshotListResponse(
        scope=scope,
        snapshots=[
            ColorTokenSnapshotSummary(
                id=int(r["id"]),
                scope=cast(ColorTokenScope, r["scope"]),
                source=cast(ColorTokenSnapshotSource, r["source"]),
                label=str(r["label"]),
                created_by=(str(r["created_by"]) if r.get("created_by") is not None else None),
                taken_at=int(r["taken_at"]),
            )
            for r in rows
        ],
    )


@router.post(
    "/api/v1/design-tokens/snapshot",
    response_model=ColorTokenSnapshotCreateResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
    },
)
def create_manual_snapshot(
    payload: ColorTokenSnapshotCreateRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenSnapshotCreateResponse:
    """Faz 5: manuel etiketli snapshot ("Versiyonum 1.0" gibi).

    PATCH/reset zaten otomatik snapshot alır; bu uç kullanıcının kendi tanımlı
    referans noktasını oluşturmasını sağlar.
    """
    if payload.scope not in VALID_SCOPES:
        raise HTTPException(status_code=422, detail=f"invalid scope: {payload.scope}")

    repo = _repo(request)
    snap_payload = repo.snapshot_payload(payload.scope)
    if not snap_payload:
        raise HTTPException(
            status_code=422,
            detail=f"Scope '{payload.scope}' boş; snapshot alınacak veri yok.",
        )

    snapshot_id = repo.create_snapshot(
        scope=payload.scope,
        source="manual",
        label=payload.label.strip()[:80],
        payload=snap_payload,
        created_by=getattr(user, "email", None) or getattr(user, "id", None),
    )

    # taken_at'i tekrar okumak yerine tekil get ile dön (consistency).
    row = repo.get_snapshot(snapshot_id)
    return ColorTokenSnapshotCreateResponse(
        snapshot_id=snapshot_id,
        scope=payload.scope,
        label=payload.label.strip()[:80],
        taken_at=int(row["taken_at"]) if row else 0,
    )


@router.post(
    "/api/v1/design-tokens/restore",
    response_model=ColorTokenRestoreResponse,
    tags=["design-tokens"],
    responses={
        401: {"description": "Auth gerekli"},
        403: {"description": "Insufficient permissions (manage_design_tokens)"},
        404: {"description": "Snapshot bulunamadı"},
    },
)
def restore_snapshot(
    payload: ColorTokenRestoreRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_design_tokens")),
) -> ColorTokenRestoreResponse:
    """Faz 5: bir snapshot'a geri dön (kayıpsız undo).

    Algoritma:
      1. Hedef snapshot oku — yoksa 404.
      2. Mevcut scope durumunu 'pre_restore' snapshot'u olarak kaydet.
      3. Hedef payload'ı governance ile doğrula (whitelist defansı).
      4. Scope'u sil + payload'ı upsert et.

    Restore'un kendisi de yeni bir snapshot bıraktığı için tekrar geri sarılabilir.
    """
    repo = _repo(request)
    target = repo.get_snapshot(payload.snapshot_id)
    if target is None:
        raise HTTPException(
            status_code=404, detail=f"Snapshot bulunamadı: {payload.snapshot_id}"
        )

    target_scope = str(target["scope"])
    if target_scope not in VALID_SCOPES:
        raise HTTPException(
            status_code=500, detail=f"Snapshot bozuk scope: {target_scope!r}"
        )

    target_payload = target.get("payload") or []
    if not isinstance(target_payload, list):
        raise HTTPException(status_code=500, detail="Snapshot payload bozuk.")

    # Defansif governance — depo bozulsa bile yazıma izinli olmayan key girmesin.
    for item in target_payload:
        try:
            assert_governance(str(item.get("scope")), str(item.get("key")))
        except GovernanceViolation as err:
            raise HTTPException(
                status_code=422, detail=f"Snapshot governance ihlal ediyor: {err}"
            ) from err

    # Pre-restore snapshot — undo zinciri.
    pre_payload = repo.snapshot_payload(target_scope)
    pre_id = repo.create_snapshot(
        scope=target_scope,
        source="pre_restore",
        label=f"Snapshot #{payload.snapshot_id} restore öncesi",
        payload=pre_payload,
        created_by=getattr(user, "email", None) or getattr(user, "id", None),
    )

    repo.delete_scope(target_scope)
    restored = repo.upsert_many(target_payload)

    return ColorTokenRestoreResponse(
        scope=target_scope,
        snapshot_id=payload.snapshot_id,
        pre_restore_snapshot_id=pre_id,
        restored_count=restored,
    )

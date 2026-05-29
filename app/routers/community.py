"""BZ3: Community router — public changelog + roadmap voting.

Public endpoint'ler (auth gerekli değil — landing'den çağrılır):
  * GET  /api/v1/changelog
  * GET  /api/v1/roadmap
  * GET  /api/v1/community/stats

Authenticated:
  * POST /api/v1/roadmap          — yeni fikir öner
  * POST /api/v1/roadmap/{id}/vote — oy ver/geri al (toggle)
  * GET  /api/v1/roadmap/{id}     — detay (has_voted flag dahil)

Admin (manage_admin permission):
  * POST  /api/v1/changelog
  * PATCH /api/v1/roadmap/{id}    — status güncelle
"""
from __future__ import annotations

from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.engines.community_engine import CommunityEngine
from app.models import (
    ChangelogEntry,
    ChangelogListResponse,
    ChangelogPublishRequest,
    CommunityStatsResponse,
    RoadmapItem,
    RoadmapListResponse,
    RoadmapStatusUpdateRequest,
    RoadmapSubmitRequest,
    RoadmapVoteResponse,
    UserProfile,
)
from app.routers._deps import _value_error_to_http
from app.security import require_permissions


router = APIRouter()


def _engine(request: Request) -> CommunityEngine:
    return cast(CommunityEngine, request.app.state.community_engine)


def _optional_user(request: Request) -> str | None:
    """Auth optional — header yoksa None döner.

    Public read endpoint'lerinde "has_voted" flag için viewer kim
    optional. MVP: identity yoksa anonymous.
    """
    # Burada production'da app.security'nin optional-auth helper'ı
    # kullanılır. MVP: header tabanlı basit lookup.
    auth = request.headers.get("X-User-Id")
    return auth or None


# ── Changelog (public) ─────────────────────────────────────────────────


@router.get(
    "/api/v1/changelog",
    response_model=ChangelogListResponse,
    tags=["community"],
)
def list_changelog(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    category: str | None = Query(default=None),
) -> ChangelogListResponse:
    """Yayınlanmış changelog entry'leri (yeni → eski)."""
    try:
        entries = _engine(request).list_changelog(
            limit=limit, category=category,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return ChangelogListResponse(
        entries=[ChangelogEntry(**e) for e in entries],
        total=len(entries),
    )


@router.post(
    "/api/v1/changelog",
    response_model=ChangelogEntry,
    tags=["community"],
)
def publish_changelog(
    payload: ChangelogPublishRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("manage_admin")),
) -> ChangelogEntry:
    """Admin: yeni release notu ekle."""
    try:
        entry = _engine(request).publish_changelog_entry(
            version=payload.version,
            title=payload.title,
            description=payload.description,
            category=payload.category,
            released_at=payload.released_at,
            created_by=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    if not entry:
        raise HTTPException(status_code=500, detail="Changelog entry yazılamadı")
    return ChangelogEntry(**entry)


# ── Roadmap (public read, authenticated write) ─────────────────────────


@router.get(
    "/api/v1/roadmap",
    response_model=RoadmapListResponse,
    tags=["community"],
)
def list_roadmap(
    request: Request,
    status: str | None = Query(default=None),
    category: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> RoadmapListResponse:
    """Roadmap items — upvotes DESC.

    viewer auth header'da varsa has_voted flag set edilir.
    """
    viewer = _optional_user(request)
    try:
        items = _engine(request).list_roadmap(
            status=status, category=category, limit=limit,
            viewer_user_id=viewer,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return RoadmapListResponse(
        items=[RoadmapItem(**it) for it in items],
        total=len(items),
    )


@router.get(
    "/api/v1/roadmap/{item_id}",
    response_model=RoadmapItem,
    tags=["community"],
)
def get_roadmap_item(
    item_id: int,
    request: Request,
) -> RoadmapItem:
    viewer = _optional_user(request)
    item = _engine(request).get_roadmap_item(
        item_id, viewer_user_id=viewer,
    )
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item bulunamadı")
    return RoadmapItem(**item)


@router.post(
    "/api/v1/roadmap",
    response_model=RoadmapItem,
    tags=["community"],
)
def submit_roadmap_idea(
    payload: RoadmapSubmitRequest,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> RoadmapItem:
    """Kullanıcı yeni fikir önerir. Status='idea' ile başlar."""
    try:
        item = _engine(request).submit_roadmap_idea(
            title=payload.title,
            description=payload.description,
            category=payload.category,
            submitter=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return RoadmapItem(**item)


@router.post(
    "/api/v1/roadmap/{item_id}/vote",
    response_model=RoadmapVoteResponse,
    tags=["community"],
)
def toggle_roadmap_vote(
    item_id: int,
    request: Request,
    user: UserProfile = Depends(require_permissions("read_finance")),
) -> RoadmapVoteResponse:
    """Oy ver / geri al (toggle)."""
    try:
        result = _engine(request).toggle_vote(
            item_id=item_id, user_id=user.username,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return RoadmapVoteResponse(
        item_id=result.item_id,
        voted=result.voted,
        upvotes_after=result.upvotes_after,
    )


@router.patch(
    "/api/v1/roadmap/{item_id}",
    response_model=RoadmapItem,
    tags=["community"],
)
def update_roadmap_status(
    item_id: int,
    payload: RoadmapStatusUpdateRequest,
    request: Request,
    _user: UserProfile = Depends(require_permissions("manage_admin")),
) -> RoadmapItem:
    """Admin: durum + target quarter + shipped link güncellemesi."""
    try:
        item = _engine(request).update_roadmap_status(
            item_id=item_id,
            status=payload.status,
            target_quarter=payload.target_quarter,
            shipped_changelog_id=payload.shipped_changelog_id,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    if not item:
        raise HTTPException(status_code=404, detail="Roadmap item bulunamadı")
    return RoadmapItem(**item)


# ── Stats (public) ─────────────────────────────────────────────────────


@router.get(
    "/api/v1/community/stats",
    response_model=CommunityStatsResponse,
    tags=["community"],
)
def get_community_stats(request: Request) -> CommunityStatsResponse:
    """Landing page için: yayınlanan özellik sayısı, oy sayısı, vs."""
    stats = _engine(request).public_stats()
    return CommunityStatsResponse(**stats)

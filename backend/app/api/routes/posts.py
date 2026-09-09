"""Social posts API — compose, manage, render, schedule, publish (Phase 5)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.models.enums import SocialPostStatus
from app.repositories.social_post_repository import SocialPostRepository
from app.repositories.visual_asset_repository import VisualAssetRepository
from app.schemas.common import Page, PageMeta
from app.schemas.social_post import (
    ComposeTaskResponse,
    EligibilityCheck,
    SocialPostCompose,
    SocialPostPatch,
    SocialPostRead,
    SocialPostSchedule,
    VisualAssetRead,
)

router = APIRouter(prefix="/posts", tags=["posts"])


@router.post("/compose", response_model=ComposeTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def compose_post_endpoint(body: SocialPostCompose, session: Session = Depends(get_db)) -> ComposeTaskResponse:
    from app.workers.tasks import compose_post
    task = compose_post.delay(str(body.event_id), body.format.value, body.theme)
    return ComposeTaskResponse(task_id=task.id, post_id=None, message="compose queued")


@router.get("", response_model=Page[SocialPostRead])
def list_posts(
    session: Session = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    post_status: SocialPostStatus | None = Query(None, alias="status"),
    event_id: uuid.UUID | None = Query(None),
    theme: str | None = Query(None),
) -> Page[SocialPostRead]:
    repo = SocialPostRepository(session)
    items, total = repo.list(limit=limit, offset=offset, status=post_status, event_id=event_id, theme=theme)
    return Page[SocialPostRead](
        items=[_to_read(p) for p in items],
        meta=PageMeta(total=total, limit=limit, offset=offset),
    )


# Visual asset endpoints (defined before /{post_id} so "assets" is not parsed as UUID)

@router.get("/assets", response_model=list[VisualAssetRead])
def list_assets(
    session: Session = Depends(get_db),
    event_id: uuid.UUID | None = Query(None),
) -> list[VisualAssetRead]:
    repo = VisualAssetRepository(session)
    if event_id:
        assets = repo.list_for_event(event_id)
    else:
        assets = []
    return [VisualAssetRead.model_validate(a) for a in assets]


@router.post("/assets/generate", response_model=ComposeTaskResponse, status_code=202)
def trigger_generate_asset(event_id: uuid.UUID, session: Session = Depends(get_db)) -> ComposeTaskResponse:
    from app.workers.tasks import generate_visual_asset
    task = generate_visual_asset.delay(str(event_id))
    return ComposeTaskResponse(task_id=task.id, post_id=None, message="image generation queued")


@router.post("/assets/{asset_id}/select", response_model=VisualAssetRead)
def select_asset(asset_id: uuid.UUID, session: Session = Depends(get_db)) -> VisualAssetRead:
    repo = VisualAssetRepository(session)
    asset = repo.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    repo.mark_selected(asset_id)
    session.commit()
    session.refresh(asset)
    return VisualAssetRead.model_validate(asset)


@router.get("/{post_id}", response_model=SocialPostRead)
def get_post(post_id: uuid.UUID, session: Session = Depends(get_db)) -> SocialPostRead:
    repo = SocialPostRepository(session)
    post = repo.get(post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
    return _to_read(post)


@router.get("/{post_id}/eligibility", response_model=EligibilityCheck)
def check_eligibility(post_id: uuid.UUID, session: Session = Depends(get_db)) -> EligibilityCheck:
    from app.integrations.publishers.instagram import InstagramPublisher
    from app.services.social.publish_service import PublishService
    from app.services.social.render_service import RenderService
    repo = SocialPostRepository(session)
    post = repo.get_with_event(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    svc = PublishService(session, InstagramPublisher(), RenderService())
    eligible, reasons = svc.check_eligibility(post)
    return EligibilityCheck(
        eligible=eligible,
        blocked_reasons=reasons,
        verification_score=post.event.verification_score,
        review_required=post.event.review_required,
        auto_publish_eligible=post.event.auto_publish_eligible,
    )


@router.post("/{post_id}/render", response_model=ComposeTaskResponse, status_code=202)
def trigger_render(post_id: uuid.UUID, session: Session = Depends(get_db)) -> ComposeTaskResponse:
    from app.workers.tasks import render_post
    repo = SocialPostRepository(session)
    if repo.get(post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found")
    task = render_post.delay(str(post_id))
    return ComposeTaskResponse(task_id=task.id, post_id=post_id, message="render queued")


@router.post("/{post_id}/schedule", response_model=SocialPostRead)
def schedule_post(post_id: uuid.UUID, body: SocialPostSchedule, session: Session = Depends(get_db)) -> SocialPostRead:
    repo = SocialPostRepository(session)
    post = repo.get(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    post.scheduled_at = body.scheduled_at
    post.status = SocialPostStatus.scheduled
    session.commit()
    session.refresh(post)
    return _to_read(post)


@router.post("/{post_id}/publish", response_model=ComposeTaskResponse, status_code=202)
def trigger_publish(post_id: uuid.UUID, session: Session = Depends(get_db)) -> ComposeTaskResponse:
    from app.workers.tasks import publish_post
    repo = SocialPostRepository(session)
    if repo.get(post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found")
    task = publish_post.delay(str(post_id))
    return ComposeTaskResponse(task_id=task.id, post_id=post_id, message="publish queued")


@router.patch("/{post_id}", response_model=SocialPostRead)
def patch_post(post_id: uuid.UUID, body: SocialPostPatch, session: Session = Depends(get_db)) -> SocialPostRead:
    repo = SocialPostRepository(session)
    post = repo.get(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != SocialPostStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft posts can be edited")
    if body.headline is not None:
        post.headline = body.headline
    if body.caption is not None:
        if len(body.caption) > 2200:
            raise HTTPException(status_code=400, detail="Caption exceeds 2200 chars")
        post.caption = body.caption
    if body.hashtags is not None:
        post.hashtags = body.hashtags
    session.commit()
    session.refresh(post)
    return _to_read(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_post(post_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    repo = SocialPostRepository(session)
    post = repo.get(post_id)
    if post is None:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.status != SocialPostStatus.draft:
        raise HTTPException(status_code=400, detail="Only draft posts can be deleted")
    session.delete(post)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_read(post) -> SocialPostRead:
    return SocialPostRead.model_validate(post)

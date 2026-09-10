"""Social posts API — compose, manage, render, schedule, publish (Phase 5)."""
from __future__ import annotations

import uuid

import socket
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.logging import get_logger
from app.models.enums import SocialPostStatus
from app.repositories.social_post_repository import SocialPostRepository
from app.repositories.visual_asset_repository import VisualAssetRepository
from app.schemas.common import Page, PageMeta
from app.schemas.social_post import (
    ComposeTaskResponse,
    EligibilityCheck,
    PhotoBrowseResponse,
    PhotoCandidate,
    SelectCandidateRequest,
    SocialPostCompose,
    SocialPostPatch,
    SocialPostRead,
    SocialPostSchedule,
    VisualAssetRead,
)

logger = get_logger(__name__)
router = APIRouter(prefix="/posts", tags=["posts"])


def _is_redis_available() -> bool:
    try:
        s = socket.socket()
        s.settimeout(0.15)
        s.connect(("localhost", 6379))
        s.close()
        return True
    except Exception:
        return False


def _dispatch_task(task, *args, background_tasks: BackgroundTasks | None = None, **kwargs) -> str:
    task_id = str(uuid.uuid4())
    if _is_redis_available():
        try:
            res = task.delay(*args, **kwargs)
            return res.id
        except Exception:
            pass
    if background_tasks:
        background_tasks.add_task(task.apply, args=args, kwargs=kwargs, task_id=task_id)
    else:
        try:
            task.apply(args=args, kwargs=kwargs, task_id=task_id)
        except Exception:
            logger.exception("task_local_run_failed", task=getattr(task, "name", str(task)))
    return task_id


@router.post("/compose", response_model=ComposeTaskResponse, status_code=status.HTTP_202_ACCEPTED)
def compose_post_endpoint(
    body: SocialPostCompose,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ComposeTaskResponse:
    from app.workers.tasks import compose_post
    task_id = _dispatch_task(
        compose_post,
        str(body.event_id),
        body.format.value,
        body.theme,
        background_tasks=background_tasks,
    )
    return ComposeTaskResponse(task_id=task_id, post_id=None, message="compose queued")


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
def trigger_generate_asset(
    event_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ComposeTaskResponse:
    from app.workers.tasks import generate_visual_asset
    task_id = _dispatch_task(
        generate_visual_asset,
        str(event_id),
        background_tasks=background_tasks,
    )
    return ComposeTaskResponse(task_id=task_id, post_id=None, message="image generation queued")


@router.get("/assets/browse-photos", response_model=PhotoBrowseResponse)
def browse_photos_endpoint(
    event_id: uuid.UUID,
    query: str | None = None,
    page: int = Query(1, ge=1),
    session: Session = Depends(get_db),
) -> PhotoBrowseResponse:
    """Search internet for 6 real photo alternatives based on the news story topic without saving to DB."""
    from app.integrations.ai.registry import get_text_provider, get_image_provider
    from app.repositories.event_repository import EventRepository
    from app.services.social.image_pipeline import ImagePipeline

    event_repo = EventRepository(session)
    event = event_repo.get_with_articles(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    pipeline = ImagePipeline(
        session=session,
        text_provider=get_text_provider(),
        image_provider=get_image_provider(),
    )
    return pipeline.browse_photos(event, query=query, page=page)


@router.post("/assets/select-candidate", response_model=VisualAssetRead)
def select_candidate_endpoint(
    body: SelectCandidateRequest,
    session: Session = Depends(get_db),
) -> VisualAssetRead:
    """Download only the chosen photo candidate, save as VisualAsset in Photo Studio, and mark selected."""
    from app.integrations.ai.registry import get_text_provider, get_image_provider
    from app.repositories.event_repository import EventRepository
    from app.services.social.image_pipeline import ImagePipeline

    event_repo = EventRepository(session)
    event = event_repo.get_with_articles(body.event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    pipeline = ImagePipeline(
        session=session,
        text_provider=get_text_provider(),
        image_provider=get_image_provider(),
    )
    asset = pipeline.import_candidate(event, body)
    return VisualAssetRead.model_validate(asset)


@router.post("/assets/search-photos", response_model=list[VisualAssetRead])
def search_real_photos(
    event_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    query: str | None = None,
    session: Session = Depends(get_db),
) -> list[VisualAssetRead]:
    """Search Pexels for editorial photos matching this event story."""
    from app.integrations.ai.registry import get_text_provider, get_image_provider
    from app.repositories.event_repository import EventRepository
    from app.services.social.image_pipeline import ImagePipeline

    event_repo = EventRepository(session)
    event = event_repo.get_with_articles(event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")

    pipeline = ImagePipeline(
        session=session,
        text_provider=get_text_provider(),
        image_provider=get_image_provider(),
    )
    assets = pipeline.search_pexels(event, query=query)
    session.commit()
    return [VisualAssetRead.model_validate(a) for a in assets]


@router.post("/assets/fetch-article-photo", response_model=ComposeTaskResponse, status_code=202)
def fetch_article_photo(
    event_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ComposeTaskResponse:
    """Try to use the real article photo from RSS feed as the visual asset."""
    from app.workers.tasks import generate_visual_asset_real_photo
    task_id = _dispatch_task(
        generate_visual_asset_real_photo,
        str(event_id),
        background_tasks=background_tasks,
    )
    return ComposeTaskResponse(task_id=task_id, post_id=None, message="real photo fetch queued")


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


@router.delete("/assets/{asset_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_asset(asset_id: uuid.UUID, session: Session = Depends(get_db)) -> Response:
    """Delete a visual asset from DB and remove its file from disk."""
    repo = VisualAssetRepository(session)
    asset = repo.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Asset not found")
    if asset.storage_path:
        p = Path(asset.storage_path)
        if p.exists():
            try:
                p.unlink()
            except OSError:
                pass
    repo.delete(asset_id)
    session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/assets/{asset_id}/image")
def get_asset_image(asset_id: uuid.UUID, session: Session = Depends(get_db)) -> FileResponse:
    repo = VisualAssetRepository(session)
    asset = repo.get(asset_id)
    if asset is None or not asset.storage_path:
        raise HTTPException(status_code=404, detail="Asset image not found")
    path = Path(asset.storage_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Asset image file not found")
    return FileResponse(path, media_type="image/png")


@router.get("/{post_id}/image")
def get_post_image(post_id: uuid.UUID, session: Session = Depends(get_db)) -> FileResponse:
    repo = SocialPostRepository(session)
    post = repo.get(post_id)
    if post is None or not post.media_path:
        raise HTTPException(status_code=404, detail="Post image not found")
    path = Path(post.media_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Post image file not found")
    return FileResponse(path, media_type="image/png")


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
def trigger_render(
    post_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ComposeTaskResponse:
    from app.workers.tasks import render_post
    repo = SocialPostRepository(session)
    if repo.get(post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found")
    task_id = _dispatch_task(
        render_post,
        str(post_id),
        background_tasks=background_tasks,
    )
    return ComposeTaskResponse(task_id=task_id, post_id=post_id, message="render queued")


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
def trigger_publish(
    post_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_db),
) -> ComposeTaskResponse:
    """Enqueue publish. Hard gates enforced in PublishService/worker."""
    from app.workers.tasks import publish_post
    repo = SocialPostRepository(session)
    if repo.get(post_id) is None:
        raise HTTPException(status_code=404, detail="Post not found")
    task_id = _dispatch_task(
        publish_post,
        str(post_id),
        background_tasks=background_tasks,
    )
    return ComposeTaskResponse(task_id=task_id, post_id=post_id, message="publish queued")


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
    data = SocialPostRead.model_validate(post)
    snapshot = post.eligibility_snapshot or {}
    slides = snapshot.get("carousel_slides", [])
    if slides:
        from app.schemas.social_post import CarouselSlide
        data.carousel_slides = [CarouselSlide.model_validate(s) for s in slides]
    return data

"""Operator-owned publishing automation policy endpoints."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.config import settings as app_settings
from app.integrations.publishers.telegram import TelegramPublisher
from app.models.article import Article
from app.models.news_event import EventArticle, NewsEvent
from app.models.publishing_settings import PublishingSettings
from app.models.telegram_post import TelegramPost, TelegramPublishingSettings
from app.schemas.publishing_settings import PublishingSettingsRead, PublishingSettingsUpdate
from app.schemas.telegram import (
    BucketContentFilter,
    TelegramPublishingSettingsRead,
    TelegramPublishingSettingsUpdate,
    TelegramTestPostRequest,
    TelegramTestPostResponse,
)
from app.services.social.translation_service import _amharic_enough

router = APIRouter(prefix="/settings", tags=["settings"])


def _get_or_create(session: Session) -> PublishingSettings:
    settings = session.get(PublishingSettings, 1)
    if settings is None:
        settings = PublishingSettings(id=1)
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


@router.get("/publishing", response_model=PublishingSettingsRead)
def get_publishing_settings(session: Session = Depends(get_db)) -> PublishingSettingsRead:
    return PublishingSettingsRead.model_validate(_get_or_create(session))


@router.patch("/publishing", response_model=PublishingSettingsRead)
def update_publishing_settings(
    body: PublishingSettingsUpdate, session: Session = Depends(get_db)
) -> PublishingSettingsRead:
    settings = _get_or_create(session)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    session.commit()
    session.refresh(settings)
    return PublishingSettingsRead.model_validate(settings)


def _get_or_create_telegram(session: Session) -> TelegramPublishingSettings:
    policy = session.get(TelegramPublishingSettings, 1)
    if policy is None:
        policy = TelegramPublishingSettings(id=1, channel_username=app_settings.telegram_channel_username)
        session.add(policy)
        session.commit()
        session.refresh(policy)
    return policy


def _telegram_read(policy: TelegramPublishingSettings) -> TelegramPublishingSettingsRead:
    data = TelegramPublishingSettingsRead.model_validate(policy).model_dump()
    data["bot_configured"] = bool(app_settings.telegram_bot_token)
    return TelegramPublishingSettingsRead.model_validate(data)


@router.get("/telegram-publishing", response_model=TelegramPublishingSettingsRead)
def get_telegram_publishing_settings(session: Session = Depends(get_db)) -> TelegramPublishingSettingsRead:
    return _telegram_read(_get_or_create_telegram(session))


@router.patch("/telegram-publishing", response_model=TelegramPublishingSettingsRead)
def update_telegram_publishing_settings(
    body: TelegramPublishingSettingsUpdate, session: Session = Depends(get_db)
) -> TelegramPublishingSettingsRead:
    policy = _get_or_create_telegram(session)
    changes = body.model_dump(exclude_unset=True)

    if "channel_username" in changes and changes["channel_username"]:
        ch = str(changes["channel_username"]).strip()
        if not ch.startswith(("@", "-")):
            ch = f"@{ch}"
        changes["channel_username"] = ch

    if "posts_per_day" in changes and "ethiopia_posts_per_day" not in changes and "international_posts_per_day" not in changes:
        new_total = changes["posts_per_day"]
        ethiopia = int(round(new_total * 0.6))
        international = new_total - ethiopia
        changes["ethiopia_posts_per_day"] = ethiopia
        changes["international_posts_per_day"] = international
    elif "posts_per_day" not in changes and ("ethiopia_posts_per_day" in changes or "international_posts_per_day" in changes):
        ethiopia = changes.get("ethiopia_posts_per_day", policy.ethiopia_posts_per_day)
        international = changes.get("international_posts_per_day", policy.international_posts_per_day)
        changes["posts_per_day"] = ethiopia + international

    projected = {
        "posts_per_day": changes.get("posts_per_day", policy.posts_per_day),
        "ethiopia_posts_per_day": changes.get("ethiopia_posts_per_day", policy.ethiopia_posts_per_day),
        "international_posts_per_day": changes.get("international_posts_per_day", policy.international_posts_per_day),
    }
    if projected["ethiopia_posts_per_day"] + projected["international_posts_per_day"] != projected["posts_per_day"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Ethiopia and international quotas must equal posts_per_day")
    for field, value in changes.items():
        setattr(policy, field, value)
    session.commit()
    session.refresh(policy)
    return _telegram_read(policy)


@router.put("/telegram-publishing/content-filters", response_model=TelegramPublishingSettingsRead)
def update_content_filters(
    body: dict,
    session: Session = Depends(get_db),
) -> TelegramPublishingSettingsRead:
    """Replace the full content_filters JSONB blob for Telegram publishing.

    Accepts a dict keyed by bucket (``ethiopia``, ``international``) with fields:
    - ``allowed_categories``: list[str] — if non-empty, only events in these categories pass
    - ``blocked_categories``: list[str] — events in these categories are always excluded
    - ``allowed_keywords``: list[str] — if non-empty, event title/summary must contain at least one
    - ``blocked_keywords``: list[str] — events with any of these in title/summary are excluded
    """
    from fastapi import HTTPException as _HTTPException

    known_buckets = {"ethiopia", "international"}
    if not isinstance(body, dict):
        raise _HTTPException(status_code=422, detail="content_filters must be a JSON object keyed by bucket name")
    unknown = set(body.keys()) - known_buckets
    if unknown:
        raise _HTTPException(status_code=422, detail=f"Unknown bucket(s): {sorted(unknown)}. Allowed: {sorted(known_buckets)}")

    # Validate each bucket entry
    validated: dict = {}
    for bucket, cfg in body.items():
        if not isinstance(cfg, dict):
            raise _HTTPException(status_code=422, detail=f"Bucket '{bucket}' must be a JSON object")
        try:
            bf = BucketContentFilter.model_validate(cfg)
            validated[bucket] = bf.model_dump()
        except Exception as exc:  # noqa: BLE001
            raise _HTTPException(status_code=422, detail=f"Invalid filter config for bucket '{bucket}': {exc}") from exc

    # Ensure both buckets are present, merging with existing if partial
    policy = _get_or_create_telegram(session)
    existing = dict(policy.content_filters or {})
    existing.update(validated)
    policy.content_filters = existing
    session.commit()
    session.refresh(policy)
    return _telegram_read(policy)


@router.post("/telegram-publishing/test-post", response_model=TelegramTestPostResponse)
def trigger_telegram_test_post(
    body: TelegramTestPostRequest | None = None,
    session: Session = Depends(get_db),
) -> TelegramTestPostResponse:
    """Immediately publish a live test broadcast to the configured Telegram channel."""
    publisher = TelegramPublisher()
    if not publisher.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Telegram bot token is not configured (TELEGRAM_BOT_TOKEN is missing).",
        )

    policy = _get_or_create_telegram(session)
    channel = (body.channel_username if body and body.channel_username else policy.channel_username) or "@Ethiopantimes"
    channel = channel.strip()
    if not channel.startswith(("@", "-")):
        channel = f"@{channel}"

    target_event: NewsEvent | None = None
    if body and body.event_id:
        target_event = session.get(NewsEvent, body.event_id)
        if not target_event:
            raise HTTPException(status_code=404, detail=f"NewsEvent {body.event_id} not found")
    else:
        from app.workers.tasks import _is_sponsored_event, _passes_bucket_filters

        stream_key = (body.stream if body and body.stream else "ethiopia").lower()
        active_cfg: dict = {}
        if hasattr(policy, "content_filters") and isinstance(policy.content_filters, dict):
            active_cfg = dict(policy.content_filters.get(stream_key, {}))

        # If a specific category was requested in test post body, override allowed_categories
        if body and body.category:
            active_cfg["allowed_categories"] = [body.category]

        posted_event_ids = select(TelegramPost.event_id).distinct()
        img_candidates = list(session.scalars(
            select(NewsEvent)
            .join(EventArticle, EventArticle.event_id == NewsEvent.id)
            .join(Article, Article.id == EventArticle.article_id)
            .where(
                Article.image_url.isnot(None),
                ~Article.image_url.ilike("%telesco.pe%"),
                ~NewsEvent.id.in_(posted_event_ids),
                NewsEvent.review_required.is_(False),
            )
            .order_by(NewsEvent.last_seen_at.desc().nullslast(), NewsEvent.created_at.desc())
            .limit(200)
        ).all())

        for ev in img_candidates:
            if _is_sponsored_event(ev):
                continue
            if active_cfg and not _passes_bucket_filters(ev, active_cfg):
                continue
            target_event = ev
            break

        if not target_event:
            unposted_candidates = list(session.scalars(
                select(NewsEvent)
                .where(~NewsEvent.id.in_(posted_event_ids), NewsEvent.review_required.is_(False))
                .order_by(NewsEvent.last_seen_at.desc().nullslast(), NewsEvent.created_at.desc())
                .limit(200)
            ).all())
            for ev in unposted_candidates:
                if _is_sponsored_event(ev):
                    continue
                if active_cfg and not _passes_bucket_filters(ev, active_cfg):
                    continue
                target_event = ev
                break

        if not target_event and active_cfg:
            all_cat_candidates = list(session.scalars(
                select(NewsEvent)
                .order_by(NewsEvent.last_seen_at.desc().nullslast(), NewsEvent.created_at.desc())
                .limit(200)
            ).all())
            for ev in all_cat_candidates:
                if _is_sponsored_event(ev):
                    continue
                if _passes_bucket_filters(ev, active_cfg):
                    target_event = ev
                    break

        if not target_event:
            target_event = session.scalars(
                select(NewsEvent)
                .order_by(NewsEvent.last_seen_at.desc().nullslast(), NewsEvent.created_at.desc())
                .limit(1)
            ).first()

    if not target_event:
        raise HTTPException(status_code=404, detail="No news events found in database to broadcast.")

    photo_url: str | None = None
    photo_credit: str | None = None
    art = session.scalars(
        select(Article)
        .join(EventArticle, EventArticle.article_id == Article.id)
        .where(
            EventArticle.event_id == target_event.id,
            Article.image_url.isnot(None),
            ~Article.image_url.ilike("%telesco.pe%"),
        )
        .limit(1)
    ).first()
    if art:
        photo_url = art.image_url
        photo_credit = art.author or "ETHIOPIAN TIMES"

    headline = target_event.title.strip()
    description = (target_event.summary or target_event.title).strip()
    source_attribution = (art.source_domain if (art and getattr(art, "source_domain", None)) else None) or "ETHIOPIAN TIMES"
    caption = f"Follow {channel} for verified news updates."

    is_amharic = _amharic_enough(headline)
    bucket = "ethiopia" if is_amharic else "international"
    language = "am" if is_amharic else "en"

    existing_post = session.scalars(
        select(TelegramPost).where(
            TelegramPost.event_id == target_event.id,
            TelegramPost.content_bucket == bucket,
        )
    ).first()

    if existing_post and existing_post.status != "published":
        post = existing_post
        post.headline = headline
        post.description = description
        post.photo_url = photo_url or post.photo_url
        post.photo_credit = photo_credit or post.photo_credit
        post.source_attribution = source_attribution
        post.caption = caption
        post.status = "publishing"
        post.dry_run = False
        post.scheduled_at = datetime.now(UTC)
    elif existing_post and existing_post.status == "published":
        test_bucket = f"test_{uuid.uuid4().hex[:6]}"
        post = TelegramPost(
            event_id=target_event.id,
            content_bucket=test_bucket,
            language=language,
            headline=headline,
            description=description,
            caption=caption,
            source_attribution=source_attribution,
            photo_url=photo_url,
            photo_credit=photo_credit,
            highlight_words=[],
            highlight_color=policy.highlight_color or "#00F0FF",
            scheduled_at=datetime.now(UTC),
            dry_run=False,
            status="publishing",
            policy_snapshot={"timezone": policy.timezone, "channel": channel, "test_dispatch": True},
        )
        session.add(post)
    else:
        post = TelegramPost(
            event_id=target_event.id,
            content_bucket=bucket,
            language=language,
            headline=headline,
            description=description,
            caption=caption,
            source_attribution=source_attribution,
            photo_url=photo_url,
            photo_credit=photo_credit,
            highlight_words=[],
            highlight_color=policy.highlight_color or "#00F0FF",
            scheduled_at=datetime.now(UTC),
            dry_run=False,
            status="publishing",
            policy_snapshot={"timezone": policy.timezone, "channel": channel, "test_dispatch": True},
        )
        session.add(post)

    session.commit()
    session.refresh(post)

    pub_result = publisher.publish(post, channel, dry_run=False)

    if pub_result.error:
        post.status = "failed"
        post.error = pub_result.error[:2000]
        session.commit()
        return TelegramTestPostResponse(
            success=False,
            message=f"Telegram live dispatch failed: {pub_result.error}",
            post_id=post.id,
            headline=post.headline,
            channel=channel,
            photo_url=post.photo_url,
            status="failed",
        )

    post.status = "published"
    post.telegram_message_id = pub_result.message_id
    post.published_at = pub_result.published_at or datetime.now(UTC)
    post.error = None
    session.commit()

    return TelegramTestPostResponse(
        success=True,
        message=f"Live broadcast delivered to {channel}! (Message #{pub_result.message_id})",
        telegram_message_id=pub_result.message_id,
        post_id=post.id,
        headline=post.headline,
        channel=channel,
        photo_url=post.photo_url,
        status="published",
    )


@router.post("/telegram-publishing/plan-and-publish")
def plan_and_publish_endpoint(
    background_tasks: BackgroundTasks,
    sync: bool = False,
) -> dict:
    """Trigger planning and publishing of due Telegram posts. Runs asynchronously by default to prevent HTTP timeouts."""
    from app.workers.tasks import plan_telegram_posts, publish_due_telegram_posts

    if sync:
        plan_result = plan_telegram_posts()
        pub_result = publish_due_telegram_posts()
        return {"sync": True, "plan": plan_result, "publish": pub_result}

    def _execute():
        plan_telegram_posts()
        publish_due_telegram_posts()

    background_tasks.add_task(_execute)
    return {"sync": False, "status": "triggered", "message": "Planning and publishing executing in background"}




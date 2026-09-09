"""Primary-source discovery MVP (Phase 3).

When secondary coverage cites an official institution (NBE, MoF, PMO, MFA,
EIC, ESS, …), search the registered source registry for a matching
``is_primary_source`` outlet and attach it to the event. Also treats a
member article whose source is already flagged primary as sufficient.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.article import Article
from app.models.enums import EventTimelineType
from app.models.news_event import EventTimeline
from app.models.news_source import NewsSource

# Aliases used to match citations in copy / extracted institutions
# onto seeded official registry rows (slug or name).
INSTITUTION_ALIASES: dict[str, tuple[str, ...]] = {
    "nbe-ethiopia": (
        "nbe",
        "national bank of ethiopia",
        "central bank of ethiopia",
        "central bank",
    ),
    "mof-ethiopia": (
        "mof",
        "mofed",
        "ministry of finance",
        "ethiopian ministry of finance",
        "ministry of finance ethiopia",
    ),
    "pmo-ethiopia": (
        "pmo",
        "office of the prime minister",
        "prime minister's office",
        "prime minister office",
        "office of the pm",
    ),
    "mfa-ethiopia": (
        "mfa",
        "ministry of foreign affairs",
        "ethiopian ministry of foreign affairs",
    ),
    "eic-ethiopia": (
        "eic",
        "ethiopian investment commission",
        "investment commission",
    ),
    "ess-ethiopia": (
        "ess",
        "ethiopian statistics service",
        "central statistical agency",
        "csa ethiopia",
        "statistics service",
    ),
}


@dataclass
class PrimarySourceDiscovery:
    available: bool
    cited_institutions: list[str] = field(default_factory=list)
    matched_source_ids: list[str] = field(default_factory=list)
    matched_names: list[str] = field(default_factory=list)
    via_member_article: bool = False


class PrimarySourceService:
    def __init__(self, session: Session) -> None:
        self.session = session

    def discover(
        self,
        *,
        event_id,  # noqa: ANN001
        articles: list[Article],
        cited_institutions: list[str],
    ) -> PrimarySourceDiscovery:
        member_primary = [
            a.source for a in articles if a.source is not None and a.source.is_primary_source
        ]
        via_member = bool(member_primary)

        haystack = " ".join(
            p
            for p in (
                " ".join(cited_institutions),
                *[a.title or "" for a in articles],
                *[a.summary or "" for a in articles],
                *[_entity_blob(a) for a in articles],
            )
            if p
        ).lower()

        registry = list(
            self.session.scalars(
                select(NewsSource).where(NewsSource.is_primary_source.is_(True))
            ).all()
        )

        matched: dict[str, NewsSource] = {str(s.id): s for s in member_primary}
        cited_hits: list[str] = list(dict.fromkeys(cited_institutions))

        for source in registry:
            if str(source.id) in matched:
                continue
            if _matches(source, haystack):
                matched[str(source.id)] = source
                cited_hits.append(source.name)

        # Dedupe cited names while preserving order.
        seen: set[str] = set()
        cited_clean: list[str] = []
        for name in cited_hits:
            key = name.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            cited_clean.append(name.strip())

        discovery = PrimarySourceDiscovery(
            available=bool(matched),
            cited_institutions=cited_clean,
            matched_source_ids=list(matched.keys()),
            matched_names=[s.name for s in matched.values()],
            via_member_article=via_member,
        )

        # Attach newly discovered (not already a member) primary sources as a
        # timeline note — we do not fabricate an article from that outlet.
        already_member_source_ids = {str(a.source_id) for a in articles}
        new_ids = [
            sid for sid in discovery.matched_source_ids if sid not in already_member_source_ids
        ]
        if new_ids:
            names = [
                matched[sid].name for sid in new_ids if sid in matched
            ]
            self.session.add(
                EventTimeline(
                    event_id=event_id,
                    article_id=None,
                    entry_type=EventTimelineType.source_confirmation,
                    occurred_at=datetime.now(UTC),
                    title="Primary source identified in registry",
                    detail={
                        "primary_source_ids": new_ids,
                        "names": names,
                        "mvp": True,
                    },
                )
            )
            self.session.flush()
        return discovery


def _entity_blob(article: Article) -> str:
    if article.analysis is None:
        return ""
    names = article.analysis.entity_names or []
    ents = article.analysis.entities or {}
    gov = ents.get("government_institutions") if isinstance(ents, dict) else []
    return " ".join(str(x) for x in list(names) + list(gov or []))


def _matches(source: NewsSource, haystack: str) -> bool:
    needles = [source.name.lower()]
    needles.extend(INSTITUTION_ALIASES.get(source.slug, ()))
    slug_head = source.slug.split("-")[0].lower()
    if slug_head and slug_head not in {"ethiopia"}:
        needles.append(slug_head)
    for needle in needles:
        if not needle:
            continue
        # Word-ish boundaries so "ess" does not match inside "business".
        pattern = rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])"
        if re.search(pattern, haystack):
            return True
    return False

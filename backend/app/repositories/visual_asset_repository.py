from __future__ import annotations

import uuid
from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.models.enums import VisualAssetStatus
from app.models.social_post import VisualAsset

class VisualAssetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, asset: VisualAsset) -> VisualAsset:
        self.session.add(asset)
        self.session.flush()
        return asset

    def get(self, asset_id: uuid.UUID) -> VisualAsset | None:
        return self.session.get(VisualAsset, asset_id)

    def get_selected_for_event(self, event_id: uuid.UUID) -> VisualAsset | None:
        return self.session.scalar(
            select(VisualAsset)
            .where(VisualAsset.event_id == event_id, VisualAsset.is_selected == True)
        )

    def mark_selected(self, asset_id: uuid.UUID) -> None:
        asset = self.get(asset_id)
        if not asset:
            return
        
        # Clear others
        stmt = (
            update(VisualAsset)
            .where(VisualAsset.event_id == asset.event_id)
            .values(is_selected=False)
        )
        self.session.execute(stmt)
        
        # Set this one
        asset.is_selected = True
        self.session.add(asset)

    def list_for_event(self, event_id: uuid.UUID) -> Sequence[VisualAsset]:
        return self.session.scalars(
            select(VisualAsset)
            .where(VisualAsset.event_id == event_id)
            .order_by(VisualAsset.created_at.desc())
        ).all()

    def update_quality(
        self, asset_id: uuid.UUID, quality_score: int, quality_report: dict, status: VisualAssetStatus
    ) -> None:
        asset = self.get(asset_id)
        if asset:
            asset.quality_score = quality_score
            asset.quality_report = quality_report
            asset.status = status
            self.session.add(asset)

    def delete(self, asset_id: uuid.UUID) -> bool:
        asset = self.get(asset_id)
        if not asset:
            return False
        self.session.delete(asset)
        self.session.flush()
        return True

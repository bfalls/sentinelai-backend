"""Analysis endpoints for mission status."""

from __future__ import annotations

from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import db_models
from app.db import get_db
from app.models.analysis import AnalysisStatusResponse
from app.services import AnalysisResult, get_analysis_engine

router = APIRouter(prefix="/api/v1", tags=["analysis"])

logger = logging.getLogger("sentinelai.analysis")


@router.get(
    "/analysis/status",
    response_model=AnalysisStatusResponse,
    summary="Get mission status based on recent events",
)
async def get_analysis_status(
    mission_id: Optional[str] = Query(
        default=None, description="Mission identifier to filter events"
    ),
    window_minutes: int = Query(
        default=60, ge=1, le=1440, description="Time window for event analysis"
    ),
    db: Session = Depends(get_db),
) -> AnalysisStatusResponse:
    """Return a rule-based mission status derived from recent events."""

    engine = get_analysis_engine()
    result: AnalysisResult = engine.analyze(
        db, mission_id=mission_id, window_minutes=int(window_minutes)
    )

    _persist_snapshot(db, result)

    logger.info(
        "Analysis status computed: mission=%s status=%s events=%s window=%s",
        mission_id,
        result.status,
        result.event_count,
        result.window_minutes,
    )

    return AnalysisStatusResponse(
        mission_id=result.mission_id,
        window_minutes=result.window_minutes,
        event_count=result.event_count,
        status=result.status,
        last_event_at=result.last_event_at,
        summary=result.summary,
    )


def _persist_snapshot(db: Session, result: AnalysisResult) -> None:
    """Store the analysis snapshot for historical tracking."""

    snapshot = db_models.AnalysisSnapshot(
        mission_id=result.mission_id,
        status=result.status,
        summary=result.summary,
        created_at=datetime.utcnow(),
        event_count=result.event_count,
        window_minutes=result.window_minutes,
    )
    db.add(snapshot)
    db.commit()

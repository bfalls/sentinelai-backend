"""Analysis endpoints for mission status."""

from __future__ import annotations

from datetime import datetime, timedelta
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app import db_models
from app.db import get_db
from app.models.analysis import AnalysisStatusResponse

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

    window_minutes = int(window_minutes)
    cutoff = datetime.utcnow() - timedelta(minutes=window_minutes)

    query = db.query(db_models.EventRecord).filter(db_models.EventRecord.timestamp >= cutoff)
    if mission_id:
        query = query.filter(db_models.EventRecord.mission_id == mission_id)

    event_count = query.count()
    last_event = query.order_by(db_models.EventRecord.timestamp.desc()).first()

    if event_count >= 10:
        status = "critical"
        summary = "High volume of events in the selected window."
    elif event_count >= 5:
        status = "attention"
        summary = "Elevated activity detected; review events."
    else:
        status = "stable"
        summary = "Low activity; mission appears stable."

    # Persist a snapshot for historical tracking
    snapshot = db_models.AnalysisSnapshot(
        mission_id=mission_id,
        status=status,
        summary=summary,
        created_at=datetime.utcnow(),
        event_count=event_count,
        window_minutes=window_minutes,
    )
    db.add(snapshot)
    db.commit()

    logger.info(
        "Analysis status computed: mission=%s status=%s events=%s window=%s",
        mission_id,
        status,
        event_count,
        window_minutes,
    )

    return AnalysisStatusResponse(
        mission_id=mission_id,
        window_minutes=window_minutes,
        event_count=event_count,
        status=status,
        last_event_at=last_event.timestamp if last_event else None,
        summary=summary,
    )

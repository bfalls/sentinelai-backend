from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app import db_models
from app.db import get_db, maybe_cleanup_old_records
from app.models.analysis import (
    AnalysisStatusResponse,
    MissionAnalysisRequest,
    MissionAnalysisResponse,
)
from app.services import (
    AnalysisResult,
    MissionAnalysisResult,
    MissionIntent as MissionIntentType,
    analyze_mission,
    analyze_mission_auto_intent,
    build_context_payload,
    get_analysis_engine,
)

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


@router.post(
    "/analysis/mission",
    response_model=MissionAnalysisResponse,
    summary="Analyze mission context using AI with intent routing",
)
async def analyze_mission_context(
    request: MissionAnalysisRequest, db: Session = Depends(get_db)
) -> MissionAnalysisResponse:
    """Route mission analysis requests to the AI engine based on intent."""

    payload = await build_context_payload(request, db=db)
    intent: MissionIntentType | None = request.intent

    try:
        if intent is not None:
            result: MissionAnalysisResult = await analyze_mission(
                payload, intent=intent
            )
        else:
            result = await analyze_mission_auto_intent(request, payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    return MissionAnalysisResponse(
        intent=result.intent,
        summary=result.summary,
        risks=result.risks,
        recommendations=result.recommendations,
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
    maybe_cleanup_old_records(db)

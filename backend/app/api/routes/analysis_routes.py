"""REST API routes for the analysis platform."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.schemas import (
    AnalysisRequest,
    AnalysisResponse,
    AnalysisDetail,
    HistoryResponse,
    ModelsResponse,
    ProfileResponse,
    ProfileUpdate,
    SettingsResponse,
    SettingsUpdate,
    UsageResponse,
)
from app.services.analysis_service import AnalysisService
from app.auth import get_current_user

router = APIRouter(tags=["analysis"])


def get_analysis_service(request: Request) -> AnalysisService:
    """Dependency injection for AnalysisService from app state.

    Falls back to creating a fresh instance if app state is not
    initialized (e.g., in test environments).
    """
    try:
        service = request.app.state.analysis_service
    except AttributeError:
        service = None
    if service is None:
        service = AnalysisService()
    return service


@router.post("/analysis", response_model=AnalysisResponse)
@router.post("/analyze", response_model=AnalysisResponse)
async def start_analysis(
    request: AnalysisRequest,
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Start a new analysis job."""
    user_id = user.get("id", user.get("sub", "unknown"))
    user_email = user.get("email", "")

    # Merge models and model_selection
    merged_models = dict(request.models or request.model_selection or {})
    if request.quick_think_llm:
        merged_models["quick_think_llm"] = request.quick_think_llm
    if request.deep_think_llm:
        merged_models["deep_think_llm"] = request.deep_think_llm

    # Resolve debate/risk rounds from research_depth if provided
    debate_rounds = request.max_debate_rounds or 1
    risk_rounds = request.max_risk_discuss_rounds or 1
    if request.research_depth == "medium":
        debate_rounds = 2
        risk_rounds = 2
    elif request.research_depth == "deep":
        debate_rounds = 3
        risk_rounds = 3

    result = await service.start_analysis(
        user_id=user_id,
        email=user_email,
        ticker=request.ticker,
        models=merged_models,
        selected_analysts=request.selected_analysts,
        max_debate_rounds=debate_rounds,
        max_risk_discuss_rounds=risk_rounds,
        analysis_date=request.analysis_date,
    )
    return result


@router.get("/analysis/{job_id}", response_model=AnalysisDetail)
async def get_analysis(
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Get the complete analysis report."""
    result = await service.get_analysis(job_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return result


@router.get("/analysis/{job_id}/stream")
async def stream_analysis(
    job_id: str,
    service: AnalysisService = Depends(get_analysis_service),
):
    """Server-Sent Events (SSE) streaming endpoint."""
    from fastapi.responses import StreamingResponse
    import json
    import asyncio

    async def event_generator():
        yield f"data: {json.dumps({'agent': 'system', 'type': 'start'})}\n\n"
        seen_events = set()

        for _ in range(150):
            events = await service.get_events(job_id)
            for idx, ev in enumerate(events):
                event_key = f"{ev.get('timestamp')}_{idx}_{ev.get('agent')}"
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    payload = {
                        "agent": ev.get("agent", "system"),
                        "type": "complete" if ev.get("status") == "completed" else "progress",
                        "content": ev.get("message", ""),
                        "progress": float(ev.get("progress", 1.0)) * 100,
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

            analysis = await service.get_analysis(job_id)
            if analysis and analysis.get("status") in ["completed", "failed"]:
                yield f"data: {json.dumps({'agent': 'system', 'type': 'complete', 'data': analysis})}\n\n"
                break

            yield f"data: {json.dumps({'agent': 'system', 'type': 'heartbeat'})}\n\n"
            await asyncio.sleep(2)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.get("/history", response_model=HistoryResponse)
@router.get("/analyses", response_model=HistoryResponse)
async def get_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    limit: Optional[int] = Query(None),
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Get paginated analysis history."""
    effective_page_size = limit or page_size
    user_id = user.get("id", user.get("sub", "unknown"))
    return await service.get_history(user_id, page, effective_page_size)


@router.get("/models")
async def get_models(
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Return available models."""
    return await service.get_models()



@router.get("/profile", response_model=ProfileResponse)
async def get_profile(
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Get user profile."""
    user_id = user.get("id", user.get("sub", "unknown"))
    profile = await service.get_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.put("/profile", response_model=ProfileResponse)
async def update_profile(
    body: ProfileUpdate,
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Update user profile."""
    user_id = user.get("id", user.get("sub", "unknown"))
    profile = await service.update_profile(user_id, body.model_dump(exclude_unset=True))
    if profile is None:
        raise HTTPException(status_code=404, detail="Profile not found")
    return profile


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Get user settings."""
    user_id = user.get("id", user.get("sub", "unknown"))
    settings = await service.get_settings(user_id)
    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Update user settings."""
    user_id = user.get("id", user.get("sub", "unknown"))
    settings = await service.update_settings(
        user_id, body.model_dump(exclude_unset=True)
    )
    if settings is None:
        raise HTTPException(status_code=404, detail="Settings not found")
    return settings


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    service: AnalysisService = Depends(get_analysis_service),
    user: dict = Depends(get_current_user),
):
    """Get today's usage."""
    user_id = user.get("id", user.get("sub", "unknown"))
    return await service.get_usage(user_id)
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from services.analysis_store import (
    approve_current_items,
    clear_current_analysis,
    current_analysis_response,
    run_current_analysis,
    reject_current_items,
)


router = APIRouter(prefix="/api/research", tags=["Research Analysis"])


class ResearchAnalyzeRequest(BaseModel):
    query: Optional[str] = None
    monthlyRevenueThreshold: float = Field(default=2000, ge=0)
    minMarginPercent: float = Field(default=20, ge=0, le=95)
    priority: str = "researchScore"


class ResearchApproveRequest(BaseModel):
    recordIds: list[str] = Field(default_factory=list)


class ResearchRejectRequest(BaseModel):
    recordIds: list[str] = Field(default_factory=list)


@router.post("/analyze")
def research_analyze(payload: ResearchAnalyzeRequest):
    analysis = run_current_analysis(
        revenue_threshold=payload.monthlyRevenueThreshold,
        min_margin_percent=payload.minMarginPercent,
        priority=payload.priority,
    )

    if not payload.query:
        return analysis

    query = payload.query.lower().strip()
    filtered_results = [
        item
        for item in analysis.get("results", [])
        if query in str(item.get("sku", "")).lower()
        or query in str(item.get("asin", "")).lower()
        or query in str(item.get("name", "")).lower()
        or query in str(item.get("brand", "")).lower()
        or query in str(item.get("category", "")).lower()
    ]
    filtered = dict(analysis)
    filtered["results"] = filtered_results
    filtered["metadata"] = dict(analysis.get("metadata", {}))
    filtered["metadata"]["query"] = payload.query
    return filtered


@router.get("/current")
def research_current():
    return current_analysis_response()


@router.post("/clear")
def research_clear():
    return clear_current_analysis()


@router.post("/approve")
def research_approve(payload: ResearchApproveRequest):
    return approve_current_items(payload.recordIds)


@router.post("/reject")
def research_reject(payload: ResearchRejectRequest):
    return reject_current_items(payload.recordIds)

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.research_service import analyze_research_catalog


_CURRENT_ANALYSIS: Optional[Dict[str, Any]] = None
LIVE_ACTIONS = {"PUSH_TO_AMAZON", "REPRICE_AND_PUSH"}


def run_current_analysis(
    revenue_threshold: float = 2000,
    min_margin_percent: float = 20,
    priority: str = "researchScore",
) -> Dict[str, Any]:
    global _CURRENT_ANALYSIS

    analysis = analyze_research_catalog(
        query=None,
        revenue_threshold=revenue_threshold,
        min_margin_percent=min_margin_percent,
        priority=priority,
    )
    analysis["isReady"] = True
    analysis["generatedAt"] = datetime.now(timezone.utc).isoformat()
    _CURRENT_ANALYSIS = analysis
    return analysis


def get_current_analysis() -> Optional[Dict[str, Any]]:
    return _CURRENT_ANALYSIS


def clear_current_analysis() -> Dict[str, Any]:
    global _CURRENT_ANALYSIS

    _CURRENT_ANALYSIS = None
    return current_analysis_response()


def approve_current_items(record_ids: List[str]) -> Dict[str, Any]:
    if _CURRENT_ANALYSIS is None:
        return current_analysis_response()

    selected_ids = {str(record_id) for record_id in record_ids}
    approved_ids = []

    for item in _CURRENT_ANALYSIS.get("results", []):
        if str(item.get("recordId")) not in selected_ids:
            continue

        item["approvalStatus"] = "APPROVED_BY_USER"
        item["decision"] = {
            "action": "PUSH_TO_AMAZON",
            "label": "Approved",
            "reason": "User approved this medium-risk SKU from the Review queue.",
        }

        push = item.setdefault("pushRecommendation", {})
        push.update(
            {
                "action": "PUSH_TO_AMAZON",
                "status": "READY_TO_PUSH",
                "priceAction": "Push approved listing",
                "message": "Approved from Review. Use the recommendation price and create or update the Amazon listing.",
                "sku": item.get("sku"),
                "asin": item.get("asin"),
                "recommendedPrice": item.get("recommendedAmazonPrice", 0),
                "riskLevel": item.get("riskAnalysis", {}).get("level"),
                "nextSteps": [
                    "Create or update the Amazon listing for this SKU.",
                    "Use the recommended price shown in the decision studio.",
                    "Monitor margin and competitor movement after launch.",
                ],
            }
        )
        approved_ids.append(str(item.get("recordId")))

    _CURRENT_ANALYSIS["summary"] = _summary_for(_CURRENT_ANALYSIS.get("results", []))
    _CURRENT_ANALYSIS["approvedRecordIds"] = approved_ids
    return _CURRENT_ANALYSIS


def reject_current_items(record_ids: List[str]) -> Dict[str, Any]:
    if _CURRENT_ANALYSIS is None:
        return current_analysis_response()

    selected_ids = {str(record_id) for record_id in record_ids}
    rejected_ids = []

    for item in _CURRENT_ANALYSIS.get("results", []):
        if str(item.get("recordId")) not in selected_ids:
            continue

        item["approvalStatus"] = "REJECTED_BY_USER"
        item["decision"] = {
            "action": "REJECTED_BY_USER",
            "label": "Rejected",
            "reason": "User rejected this SKU from the Review queue.",
        }
        push = item.setdefault("pushRecommendation", {})
        push.update(
            {
                "action": "NO_OP",
                "status": "REJECTED",
                "priceAction": "Do not push",
                "message": "Rejected from Review. No Amazon payload should be sent.",
                "sku": item.get("sku"),
                "asin": item.get("asin"),
                "recommendedPrice": item.get("recommendedAmazonPrice", 0),
                "riskLevel": item.get("riskAnalysis", {}).get("level"),
                "nextSteps": [
                    "Hold the SKU back from Amazon listing changes.",
                    "Revisit margin, demand, or competitor fit in a later run.",
                ],
            }
        )
        rejected_ids.append(str(item.get("recordId")))

    _CURRENT_ANALYSIS["summary"] = _summary_for(_CURRENT_ANALYSIS.get("results", []))
    _CURRENT_ANALYSIS["rejectedRecordIds"] = rejected_ids
    return _CURRENT_ANALYSIS


def current_analysis_response() -> Dict[str, Any]:
    if _CURRENT_ANALYSIS is None:
        return {
            "isReady": False,
            "message": "Run the Pipeline before opening Review or Dashboard.",
        }

    return _CURRENT_ANALYSIS


def _summary_for(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    push_count = sum(
        1
        for item in results
        if _is_live_listing(item)
    )
    total_revenue = round(sum(_number(item.get("monthlyRevenue", 0)) for item in results), 2)
    weighted_margin = (
        round(
            sum(
                _number(item.get("monthlyRevenue", 0))
                * _number(item.get("economics", {}).get("contributionMarginPercent", 0))
                for item in results
            )
            / total_revenue,
            2,
        )
        if total_revenue
        else 0
    )

    return {
        "pushCount": push_count,
        "reviewCount": len(results) - push_count,
        "variantCollapsedCount": sum(
            max(0, int(item.get("variantCount", 1)) - 1)
            for item in results
        ),
        "averageScore": round(
            sum(_number(item.get("researchScore", 0)) for item in results) / len(results)
        )
        if results
        else 0,
        "averageMarginPercent": weighted_margin,
        "weightedMarginPercent": weighted_margin,
        "totalEstimatedMonthlyRevenue": total_revenue,
    }


def _is_live_listing(item: Dict[str, Any]) -> bool:
    return (
        item.get("approvalStatus") == "APPROVED_BY_USER"
        or item.get("decision", {}).get("action") in LIVE_ACTIONS
    )


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0

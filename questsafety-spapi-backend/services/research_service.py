import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional


DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PRODUCTS_FILE = DATA_DIR / "quest-safety-products-100.json"
COMPETITORS_FILE = DATA_DIR / "amazon-competitor-candidates-500.json"
MARKUP_MIN_PERCENT = 17.0
MARKUP_MAX_PERCENT = 35.0
AMAZON_REFERRAL_FEE_RATE = 0.15
FBA_FEE_RATE = 0.08
FBA_FEE_MIN = 4.35
FBA_FEE_MAX = 18.0
REPRICE_ACTIONS = {"PUSH_TO_AMAZON", "REPRICE_AND_PUSH"}


def analyze_research_catalog(
    query: Optional[str] = None,
    revenue_threshold: float = 2000,
    min_margin_percent: float = 20,
    priority: str = "researchScore",
) -> Dict[str, Any]:
    products = _load_records(PRODUCTS_FILE)
    competitors = _load_records(COMPETITORS_FILE)
    competitor_groups = _group_competitors(competitors)

    analyses = [
        _analyze_product(
            product=product,
            competitor_candidates=competitor_groups.get(product.get("recordId"), []),
            revenue_threshold=revenue_threshold,
            min_margin_percent=min_margin_percent,
        )
        for product in products
    ]
    deduped_analyses = _dedupe_product_variants(
        analyses,
        revenue_threshold=revenue_threshold,
    )

    filtered = _filter_results(deduped_analyses, query)
    sorted_results = _sort_results(filtered, priority)

    return {
        "metadata": {
            "productCount": len(deduped_analyses),
            "sourceProductCount": len(products),
            "competitorCount": len(competitors),
            "competitorsPerProduct": 5,
            "query": query or "",
            "criteria": {
                "monthlyRevenueGreaterThan": revenue_threshold,
                "minimumContributionMarginPercent": min_margin_percent,
                "fbaCompetitiveRequired": True,
                "costMarkupPercentRange": [
                    MARKUP_MIN_PERCENT,
                    MARKUP_MAX_PERCENT,
                ],
                "recommendedPriceBasis": (
                    "Recommended price is margin-safe after referral, estimated FBA, "
                    "and prep costs, then checked against the lowest FBA competitor."
                ),
            },
            "priority": priority,
            "estimateNote": (
                "QuestSafety JSON includes explicit Cost, costMarkupPercent, "
                "and base price fields. In this sandbox file, Cost was populated "
                "from the original price because no separate cost feed "
                "was provided; price is the deterministic 17-35% cost-based "
                "sandbox price and recommendedAmazonPrice is the margin-safe "
                "Amazon push price."
            ),
            "dedupeNote": (
                "QuestSafety data is normalized to unique product families. "
                "A duplicate size/package guard remains for future imports."
            ),
        },
        "summary": _build_summary(sorted_results),
        "results": sorted_results,
    }


@lru_cache(maxsize=4)
def _load_records(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return data.get("records", [])


def _group_competitors(records: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for record in records:
        key = record.get("linkedQuestRecordId")
        grouped.setdefault(key, []).append(record)

    for key in grouped:
        grouped[key] = sorted(
            grouped[key],
            key=lambda item: item.get("competitorRank", 999),
        )

    return grouped


def _analyze_product(
    product: Dict[str, Any],
    competitor_candidates: List[Dict[str, Any]],
    revenue_threshold: float,
    min_margin_percent: float,
) -> Dict[str, Any]:
    vendor_cost = _product_cost(product)
    markup_percent = _product_markup_percent(product)
    base_price = _product_sale_price(product, vendor_cost, markup_percent)
    sku = str(product.get("sku") or "")
    asin = str(product.get("amazonAsin") or "")
    category = _first(product.get("categories"), "Uncategorized")
    monthly_units = _estimate_monthly_units(product)
    target_margin_percent = _target_margin_percent(product, min_margin_percent)
    min_viable_price = _price_for_margin(vendor_cost, category, min_margin_percent)
    target_margin_price = _price_for_margin(vendor_cost, category, target_margin_percent)
    competitors = _build_competitor_analysis(
        product=product,
        base_price=base_price,
        target_margin_price=target_margin_price,
        min_viable_price=min_viable_price,
        competitor_candidates=competitor_candidates,
        monthly_units=monthly_units,
    )

    lowest_fba = _lowest_fba_price(competitors)
    recommended_price = _recommended_price(
        current_price=base_price,
        lowest_fba_price=lowest_fba,
        min_viable_price=min_viable_price,
        target_margin_price=target_margin_price,
    )
    economics = _estimate_economics(
        product=product,
        vendor_cost=vendor_cost,
        base_price=base_price,
        sale_price=recommended_price,
        markup_percent=markup_percent,
        min_margin_percent=min_margin_percent,
        target_margin_percent=target_margin_percent,
    )
    monthly_revenue = round(recommended_price * monthly_units, 2)
    can_compete_fba = lowest_fba > 0 and recommended_price <= lowest_fba * 1.02
    revenue_pass = monthly_revenue >= revenue_threshold
    margin_pass = economics["contributionMarginPercent"] >= min_margin_percent
    match_confidence = str(product.get("asinLookupConfidence") or "unknown")
    risk_analysis = _risk_analysis(
        product=product,
        economics=economics,
        monthly_revenue=monthly_revenue,
        revenue_threshold=revenue_threshold,
        min_margin_percent=min_margin_percent,
        can_compete_fba=can_compete_fba,
        match_confidence=match_confidence,
    )
    criteria = {
        "revenue": {
            "passed": revenue_pass,
            "actual": monthly_revenue,
            "threshold": revenue_threshold,
            "explanation": (
                f"Estimated monthly revenue is ${monthly_revenue:,.0f}, "
                f"measured against the ${revenue_threshold:,.0f} threshold."
            ),
        },
        "fbaCompetitive": {
            "passed": can_compete_fba,
            "actual": lowest_fba,
            "threshold": economics["minViablePrice"],
            "explanation": (
                "Quest can meet or beat the lowest FBA seller while protecting margin."
                if can_compete_fba
                else "The lowest FBA seller is below the margin-safe recommended price."
            ),
        },
        "margin": {
            "passed": margin_pass,
            "actual": economics["contributionMarginPercent"],
            "threshold": min_margin_percent,
            "explanation": (
                f"Recommended price is ${recommended_price:,.2f}. It is calculated "
                f"to protect at least {min_margin_percent:.1f}% contribution "
                f"margin after estimated referral, FBA, and prep costs. "
                f"Projected margin is {economics['contributionMarginPercent']:.1f}%."
            ),
        },
    }

    decision = _decision(criteria, risk_analysis, base_price, recommended_price)
    score = _research_score(criteria, economics, monthly_revenue, revenue_threshold, risk_analysis)

    return {
        "recordId": product.get("recordId"),
        "sku": sku,
        "asin": asin,
        "name": product.get("name"),
        "brand": product.get("brand"),
        "category": category,
        "imageUrl": product.get("imageUrl"),
        "questProductUrl": product.get("sourceUrl"),
        "amazonProductUrl": product.get("amazonProductUrl"),
        "Cost": vendor_cost,
        "markupPercent": markup_percent,
        "price": base_price,
        "monthlyUnits": monthly_units,
        "monthlyRevenue": monthly_revenue,
        "economics": economics,
        "competitors": competitors,
        "criteria": criteria,
        "riskAnalysis": risk_analysis,
        "decision": decision,
        "researchScore": score,
        "recommendedAmazonPrice": recommended_price,
        "pricingBasis": _pricing_basis(
            base_price=base_price,
            recommended_price=recommended_price,
            lowest_fba_price=lowest_fba,
            min_margin_percent=min_margin_percent,
            target_margin_percent=target_margin_percent,
        ),
        "pushRecommendation": _push_recommendation(
            product=product,
            decision=decision,
            recommended_price=recommended_price,
            risk_analysis=risk_analysis,
        ),
        "explanation": _build_explanation(
            product=product,
            criteria=criteria,
            decision=decision,
            risk_analysis=risk_analysis,
            competitors=competitors,
        ),
    }


def _estimate_monthly_units(product: Dict[str, Any]) -> int:
    category = _first(product.get("categories"), "")
    base_units = _stable_int(str(product.get("recordId")), 12, 105)
    category_boost = 1.0

    if "Coverall" in category:
        category_boost = 1.18
    elif "Glove" in category:
        category_boost = 1.28
    elif "Hard Hat" in category:
        category_boost = 1.12
    elif "Respirator" in category or "Mask" in category:
        category_boost = 1.22

    return max(4, round(base_units * category_boost))


def _estimate_economics(
    product: Dict[str, Any],
    vendor_cost: float,
    base_price: float,
    sale_price: float,
    markup_percent: float,
    min_margin_percent: float,
    target_margin_percent: float,
) -> Dict[str, float]:
    category = _first(product.get("categories"), "")
    referral_fee = round(sale_price * AMAZON_REFERRAL_FEE_RATE, 2)
    fba_fee = _estimate_fba_fee(sale_price)
    prep_cost = round(_category_prep_cost(category), 2)
    gross_markup_dollars = round(sale_price - vendor_cost, 2)
    profit = round(sale_price - vendor_cost - referral_fee - fba_fee - prep_cost, 2)
    contribution_margin = round((profit / sale_price) * 100, 2) if sale_price else 0
    min_viable_price = _price_for_margin(vendor_cost, category, min_margin_percent)

    return {
        "Cost": round(vendor_cost, 2),
        "basePrice": round(base_price, 2),
        "salePrice": round(sale_price, 2),
        "recommendedPrice": round(sale_price, 2),
        "costMarkupPercent": markup_percent,
        "grossMarkupDollars": gross_markup_dollars,
        "estimatedProductCost": round(vendor_cost, 2),
        "amazonReferralFee": referral_fee,
        "estimatedFbaFee": fba_fee,
        "shippingPrepCost": prep_cost,
        "profitPerUnit": profit,
        "contributionMarginPercent": contribution_margin,
        "minViablePrice": min_viable_price,
        "requiredMarginPercent": min_margin_percent,
        "targetMarginPercent": target_margin_percent,
    }


def _build_competitor_analysis(
    product: Dict[str, Any],
    base_price: float,
    target_margin_price: float,
    min_viable_price: float,
    competitor_candidates: List[Dict[str, Any]],
    monthly_units: int,
) -> List[Dict[str, Any]]:
    competitors: List[Dict[str, Any]] = []

    for candidate in competitor_candidates:
        rank = int(candidate.get("competitorRank") or len(competitors) + 1)
        price = _competitor_price(
            product=product,
            base_price=base_price,
            target_margin_price=target_margin_price,
            min_viable_price=min_viable_price,
            candidate=candidate,
            rank=rank,
        )
        fulfillment = "FBA" if rank in {1, 2, 4} else "FBM"
        estimated_units = max(2, round(monthly_units * (1.1 - (rank * 0.09))))

        competitors.append(
            {
                "rank": rank,
                "sellerName": candidate.get("expectedCompetitorBrand") or "Amazon competitor",
                "brand": candidate.get("expectedCompetitorBrand") or "Unknown",
                "asin": candidate.get("amazonAsin"),
                "title": candidate.get("amazonListingTitle")
                or candidate.get("sourceCatalogProductName"),
                "category": candidate.get("expectedCategory"),
                "fulfillmentType": fulfillment,
                "estimatedPrice": price,
                "estimatedMonthlyRevenue": round(price * estimated_units, 2),
                "matchConfidence": candidate.get("asinLookupConfidence") or "unknown",
                "amazonProductUrl": candidate.get("amazonProductUrl"),
                "amazonSearchUrl": candidate.get("amazonSearchUrl"),
                "reason": candidate.get("selectionReason"),
            }
        )

    return _dedupe_competitors(competitors)


def _risk_analysis(
    product: Dict[str, Any],
    economics: Dict[str, float],
    monthly_revenue: float,
    revenue_threshold: float,
    min_margin_percent: float,
    can_compete_fba: bool,
    match_confidence: str,
) -> Dict[str, Any]:
    margin_buffer = round(economics["contributionMarginPercent"] - min_margin_percent, 2)
    factors = [
        _factor(
            "Revenue quality",
            "LOW" if monthly_revenue >= revenue_threshold else "HIGH",
            (
                "Estimated demand clears the monthly revenue threshold."
                if monthly_revenue >= revenue_threshold
                else "Estimated revenue is below the push threshold."
            ),
        ),
        _factor(
            "Margin buffer",
            "LOW" if margin_buffer >= 4 else "MEDIUM" if margin_buffer >= 0 else "HIGH",
            (
                f"Margin has {margin_buffer:.1f}% buffer above requirement."
                if margin_buffer >= 0
                else f"Margin is {abs(margin_buffer):.1f}% below requirement."
            ),
        ),
        _factor(
            "FBA competitiveness",
            "LOW" if can_compete_fba else "HIGH",
            (
                "Quest can be lowest or competitive FBA seller."
                if can_compete_fba
                else "Quest cannot safely match the lowest FBA price."
            ),
        ),
        _factor(
            "ASIN match confidence",
            _confidence_level(match_confidence),
            f"Catalog-to-Amazon match confidence is {match_confidence}.",
        ),
        _factor(
            "Category compliance",
            _category_risk_level(product),
            _category_risk_message(product),
        ),
    ]
    score = _risk_score(factors)

    return {
        "score": score,
        "level": _risk_level(score),
        "factors": factors,
        "marginBufferPercent": margin_buffer,
        "summary": _risk_summary(factors),
    }


def _push_recommendation(
    product: Dict[str, Any],
    decision: Dict[str, str],
    recommended_price: float,
    risk_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    should_push = decision["action"] in REPRICE_ACTIONS
    is_reprice = decision["action"] == "REPRICE_AND_PUSH"

    return {
        "shouldPush": should_push,
        "action": (
            "REPRICE_AND_UPDATE_LISTING"
            if is_reprice
            else "CREATE_OR_UPDATE_LISTING"
            if should_push
            else "HUMAN_REVIEW"
        ),
        "priceAction": (
            "Reprice and push listing"
            if is_reprice
            else "Set Amazon listing price"
            if should_push
            else "Do not update Amazon yet"
        ),
        "sku": product.get("sku"),
        "asin": product.get("amazonAsin"),
        "recommendedPrice": recommended_price,
        "currencyCode": product.get("currency") or "USD",
        "message": (
            "Reprice candidate: recommended price clears margin, FBA, and risk checks."
            if is_reprice
            else "Push candidate: criteria clear and risk is controlled."
            if should_push
            else "Hold for review: one or more criteria or risk checks failed."
        ),
        "nextSteps": _push_next_steps(should_push),
        "riskLevel": risk_analysis["level"],
    }


def _decision(
    criteria: Dict[str, Dict[str, Any]],
    risk_analysis: Dict[str, Any],
    base_price: float,
    recommended_price: float,
) -> Dict[str, str]:
    passed = all(item["passed"] for item in criteria.values())
    low_or_medium_risk = risk_analysis["level"] in {"LOW", "MEDIUM"}

    if passed and low_or_medium_risk:
        if abs(recommended_price - base_price) >= 0.02:
            return {
                "action": "REPRICE_AND_PUSH",
                "label": "Reprice & Push",
                "reason": (
                    "Revenue, FBA competitiveness, margin, and risk checks are acceptable "
                    "after using the recommended Amazon price."
                ),
            }

        return {
            "action": "PUSH_TO_AMAZON",
            "label": "Push to Amazon",
            "reason": "Revenue, FBA competitiveness, margin, and risk checks are acceptable.",
        }

    return {
        "action": "HUMAN_REVIEW",
        "label": "Human Review",
        "reason": "At least one push gate needs review before Amazon listing changes.",
    }


def _research_score(
    criteria: Dict[str, Dict[str, Any]],
    economics: Dict[str, float],
    monthly_revenue: float,
    revenue_threshold: float,
    risk_analysis: Dict[str, Any],
) -> int:
    revenue_score = min(100, round((monthly_revenue / max(revenue_threshold, 1)) * 100))
    margin_score = min(100, max(0, round(economics["contributionMarginPercent"] * 3)))
    fba_score = 100 if criteria["fbaCompetitive"]["passed"] else 35
    risk_component = max(0, 100 - int(risk_analysis["score"]))

    return round(
        revenue_score * 0.3
        + margin_score * 0.28
        + fba_score * 0.24
        + risk_component * 0.18
    )


def _build_explanation(
    product: Dict[str, Any],
    criteria: Dict[str, Dict[str, Any]],
    decision: Dict[str, str],
    risk_analysis: Dict[str, Any],
    competitors: List[Dict[str, Any]],
) -> List[str]:
    lowest_fba = _lowest_fba_price(competitors)
    competitor_names = ", ".join(
        competitor["sellerName"] for competitor in competitors[:3]
    )

    return [
        criteria["revenue"]["explanation"],
        criteria["margin"]["explanation"],
        criteria["fbaCompetitive"]["explanation"],
        f"Lowest estimated FBA competitor price is ${lowest_fba:,.2f}.",
        f"Primary competitor brands: {competitor_names}.",
        f"Risk level is {risk_analysis['level']} because {risk_analysis['summary']}",
        decision["reason"],
    ]


def _build_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    push_count = sum(1 for item in results if item["decision"]["action"] in REPRICE_ACTIONS)
    review_count = len(results) - push_count
    total_revenue = round(
        sum(item["monthlyRevenue"] for item in results),
        2,
    )
    weighted_margin = (
        round(
            sum(
                item["monthlyRevenue"]
                * item["economics"]["contributionMarginPercent"]
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
        "reviewCount": review_count,
        "variantCollapsedCount": sum(
            max(0, int(item.get("variantCount", 1)) - 1)
            for item in results
        ),
        "averageScore": round(
            sum(item["researchScore"] for item in results) / len(results)
        )
        if results
        else 0,
        "averageMarginPercent": weighted_margin,
        "weightedMarginPercent": weighted_margin,
        "totalEstimatedMonthlyRevenue": total_revenue,
    }


def _filter_results(
    results: List[Dict[str, Any]],
    query: Optional[str],
) -> List[Dict[str, Any]]:
    if not query:
        return results

    needle = query.lower().strip()
    return [
        item
        for item in results
        if needle in str(item.get("sku", "")).lower()
        or needle in str(item.get("asin", "")).lower()
        or needle in str(item.get("name", "")).lower()
        or needle in str(item.get("brand", "")).lower()
        or needle in str(item.get("category", "")).lower()
    ]


def _sort_results(results: List[Dict[str, Any]], priority: str) -> List[Dict[str, Any]]:
    sorters = {
        "revenue": lambda item: item["monthlyRevenue"],
        "margin": lambda item: item["economics"]["contributionMarginPercent"],
        "risk": lambda item: -item["riskAnalysis"]["score"],
        "researchScore": lambda item: item["researchScore"],
    }

    return sorted(results, key=sorters.get(priority, sorters["researchScore"]), reverse=True)


def _recommended_price(
    current_price: float,
    lowest_fba_price: float,
    min_viable_price: float,
    target_margin_price: float,
) -> float:
    if not lowest_fba_price:
        return round(max(current_price, target_margin_price, min_viable_price), 2)

    competitor_beat = round(lowest_fba_price - 0.01, 2)
    if competitor_beat >= min_viable_price:
        target_price = max(current_price, target_margin_price, min_viable_price)
        return round(min(target_price, competitor_beat), 2)

    return round(max(current_price, min_viable_price), 2)


def _dedupe_product_variants(
    analyses: List[Dict[str, Any]],
    revenue_threshold: float,
) -> List[Dict[str, Any]]:
    groups: Dict[str, List[Dict[str, Any]]] = {}

    for analysis in analyses:
        groups.setdefault(_product_family_key(analysis), []).append(analysis)

    deduped: List[Dict[str, Any]] = []
    for items in groups.values():
        representative = sorted(
            items,
            key=lambda item: (
                item["decision"]["action"] in REPRICE_ACTIONS,
                item["researchScore"],
                item["monthlyRevenue"],
            ),
            reverse=True,
        )[0]

        total_revenue = round(sum(item["monthlyRevenue"] for item in items), 2)
        total_units = sum(int(item["monthlyUnits"]) for item in items)
        variants = [
            {
                "sku": item.get("sku"),
                "asin": item.get("asin"),
                "name": item.get("name"),
                "Cost": item.get("Cost"),
                "markupPercent": item.get("markupPercent"),
                "salePrice": item.get("price"),
            }
            for item in sorted(items, key=lambda item: str(item.get("sku", "")))
        ]

        representative["name"] = _clean_variant_name(str(representative.get("name") or ""))
        representative["monthlyRevenue"] = total_revenue
        representative["monthlyUnits"] = total_units
        representative["variantCount"] = len(items)
        representative["variants"] = variants

        criteria = representative["criteria"]
        criteria["revenue"]["actual"] = total_revenue
        criteria["revenue"]["passed"] = total_revenue >= revenue_threshold
        criteria["revenue"]["explanation"] = (
            f"Estimated monthly revenue is ${total_revenue:,.0f}, "
            f"measured against the ${revenue_threshold:,.0f} threshold."
        )

        representative["decision"] = _decision(
            representative["criteria"],
            representative["riskAnalysis"],
            representative.get("price", 0),
            representative.get("recommendedAmazonPrice", 0),
        )
        representative["researchScore"] = _research_score(
            representative["criteria"],
            representative["economics"],
            representative["monthlyRevenue"],
            revenue_threshold,
            representative["riskAnalysis"],
        )
        representative["pushRecommendation"] = _push_recommendation(
            product={
                "sku": representative.get("sku"),
                "amazonAsin": representative.get("asin"),
                "currency": "USD",
            },
            decision=representative["decision"],
            recommended_price=representative["recommendedAmazonPrice"],
            risk_analysis=representative["riskAnalysis"],
        )
        representative["explanation"] = _build_explanation(
            product=representative,
            criteria=representative["criteria"],
            decision=representative["decision"],
            risk_analysis=representative["riskAnalysis"],
            competitors=representative["competitors"],
        )

        if len(items) > 1:
            representative["explanation"].insert(
                0,
                f"{len(items)} size/package variants were collapsed into this one research item.",
            )

        deduped.append(representative)

    return deduped


def _dedupe_competitors(competitors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique: List[Dict[str, Any]] = []
    seen = set()

    for competitor in competitors:
        key = _competitor_family_key(competitor)
        if key in seen:
            continue

        seen.add(key)
        unique.append(competitor)

        if len(unique) == 5:
            break

    return _rerank_competitors(unique)


def _rerank_competitors(competitors: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    for index, competitor in enumerate(competitors, start=1):
        competitor["rank"] = index

    return competitors


def _product_family_key(item: Dict[str, Any]) -> str:
    return "|".join(
        [
            _normalize_family_text(str(item.get("brand") or "")),
            _normalize_family_text(str(item.get("category") or "")),
            _normalize_family_text(str(item.get("name") or "")),
        ]
    )


def _competitor_family_key(item: Dict[str, Any]) -> str:
    return "|".join(
        [
            _normalize_family_text(str(item.get("brand") or item.get("sellerName") or "")),
            _normalize_family_text(str(item.get("title") or "")),
        ]
    )


def _normalize_family_text(value: str) -> str:
    value = _clean_variant_name(value).lower()
    value = re.sub(r"\b(pack|case|carton|box)\s+of\s+\d+\b", " ", value)
    value = re.sub(r"\b\d+\s*(pack|case|carton|box|ct|count)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _clean_variant_name(value: str) -> str:
    size_terms = (
        r"xxs|xs|small|medium|large|xlarge|x-large|xxlarge|xx-large|"
        r"xxxlarge|xxx-large|xxxxlarge|xxxx-large|s|m|l|xl|xxl|xxxl|"
        r"xxxxl|[2-6]xl|[2-6]x-large"
    )
    value = re.sub(rf"\b({size_terms})\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\b(size|sz)\s*[:#-]?\s*[a-z0-9-]+\b", " ", value, flags=re.IGNORECASE)
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s+([,;:])", r"\1", value)
    return value.strip(" ,-")


def _competitor_price(
    product: Dict[str, Any],
    base_price: float,
    target_margin_price: float,
    min_viable_price: float,
    candidate: Dict[str, Any],
    rank: int,
) -> float:
    product_seed = f"{product.get('recordId')}:{product.get('sku')}:market"
    market_band = _stable_int(product_seed, 0, 99)
    band_spread = _stable_int(f"{product_seed}:spread", 0, 12) / 100

    if market_band < 58:
        anchor = target_margin_price * (1.04 + band_spread)
    elif market_band < 82:
        anchor = min_viable_price * (0.98 + band_spread)
    else:
        anchor = base_price * (0.92 + band_spread)

    seed = f"{candidate.get('recordId')}:{candidate.get('amazonAsin')}"
    spread = _stable_int(seed, -3, 7) / 100
    rank_lift = (rank - 1) * 0.045
    price = anchor * (1 + spread + rank_lift)
    return round(max(price, 4.99), 2)


def _pricing_basis(
    base_price: float,
    recommended_price: float,
    lowest_fba_price: float,
    min_margin_percent: float,
    target_margin_percent: float,
) -> Dict[str, Any]:
    return {
        "basePrice": round(base_price, 2),
        "recommendedPrice": round(recommended_price, 2),
        "lowestFbaCompetitorPrice": round(lowest_fba_price, 2),
        "requiredMarginPercent": round(min_margin_percent, 2),
        "targetMarginPercent": round(target_margin_percent, 2),
        "notes": [
            (
                "Recommended price protects the required contribution margin after "
                "estimated referral, FBA, and prep costs."
            ),
            (
                "The final price is checked against the lowest FBA competitor so "
                "Quest can stay lowest or competitive when possible."
            ),
        ],
    }


def _product_cost(product: Dict[str, Any]) -> float:
    return round(
        float(product.get("Cost") or product.get("price") or 0),
        2,
    )


def _product_markup_percent(product: Dict[str, Any]) -> float:
    markup = product.get("costMarkupPercent")
    if markup is not None:
        return round(float(markup), 2)

    return _cost_markup_percent(product)


def _product_sale_price(
    product: Dict[str, Any],
    vendor_cost: float,
    markup_percent: float,
) -> float:
    sale_price = product.get("price") if product.get("Cost") is not None else None
    if sale_price is not None:
        return round(float(sale_price), 2)

    return _sale_price_from_cost(vendor_cost, markup_percent)


def _cost_markup_percent(product: Dict[str, Any]) -> float:
    seed = f"{product.get('recordId')}:{product.get('sku')}:markup"
    basis_points = _stable_int(
        seed,
        round(MARKUP_MIN_PERCENT * 100),
        round(MARKUP_MAX_PERCENT * 100),
    )
    cents = _stable_int(f"{seed}:float", 0, 99) / 100
    return round(min(MARKUP_MAX_PERCENT, (basis_points / 100) + cents), 2)


def _target_margin_percent(product: Dict[str, Any], min_margin_percent: float) -> float:
    seed = f"{product.get('recordId')}:{product.get('sku')}:target-margin"
    buffer = _stable_int(seed, 150, 750) / 100
    return round(min(min_margin_percent + buffer, 48.0), 2)


def _price_for_margin(vendor_cost: float, category: str, margin_percent: float) -> float:
    margin_rate = min(max(margin_percent / 100, 0), 0.75)
    denominator = max(0.08, 1 - AMAZON_REFERRAL_FEE_RATE - margin_rate)
    prep_cost = round(_category_prep_cost(category), 2)
    price = max(vendor_cost * (1 + MARKUP_MIN_PERCENT / 100), vendor_cost + prep_cost + FBA_FEE_MIN)

    for _ in range(8):
        fba_fee = _estimate_fba_fee(price)
        price = (vendor_cost + fba_fee + prep_cost) / denominator

    return round(price, 2)


def _sale_price_from_cost(vendor_cost: float, markup_percent: float) -> float:
    return round(vendor_cost * (1 + (markup_percent / 100)), 2)


def _estimate_fba_fee(sale_price: float) -> float:
    return round(min(max(sale_price * FBA_FEE_RATE, FBA_FEE_MIN), FBA_FEE_MAX), 2)


def _lowest_fba_price(competitors: List[Dict[str, Any]]) -> float:
    fba_prices = [
        competitor["estimatedPrice"]
        for competitor in competitors
        if competitor.get("fulfillmentType") == "FBA"
    ]
    return round(min(fba_prices), 2) if fba_prices else 0


def _category_prep_cost(category: str) -> float:
    category_lower = category.lower()
    if "coverall" in category_lower:
        return 2.35
    if "hard hat" in category_lower:
        return 1.75
    if "respirator" in category_lower:
        return 1.55
    return 1.25


def _factor(name: str, level: str, message: str) -> Dict[str, str]:
    return {
        "name": name,
        "level": level,
        "message": message,
    }


def _confidence_level(confidence: str) -> str:
    normalized = confidence.lower()
    if normalized == "high":
        return "LOW"
    if normalized == "medium":
        return "MEDIUM"
    return "HIGH"


def _category_risk_level(product: Dict[str, Any]) -> str:
    text = f"{product.get('name', '')} {_first(product.get('categories'), '')}".lower()
    high_terms = ["respirator", "hazmat", "chemical", "cartridge"]
    medium_terms = ["coverall", "glove", "sleeve", "safety"]

    if any(term in text for term in high_terms):
        return "HIGH"
    if any(term in text for term in medium_terms):
        return "MEDIUM"
    return "LOW"


def _category_risk_message(product: Dict[str, Any]) -> str:
    level = _category_risk_level(product)
    if level == "HIGH":
        return "Product category may require compliance review before listing."
    if level == "MEDIUM":
        return "PPE category should be checked for listing restrictions and claims."
    return "No category-specific risk signal found in the catalog text."


def _risk_score(factors: List[Dict[str, str]]) -> int:
    weights = {"LOW": 15, "MEDIUM": 45, "HIGH": 80}
    return round(sum(weights.get(item["level"], 45) for item in factors) / len(factors))


def _risk_level(score: int) -> str:
    if score >= 60:
        return "HIGH"
    if score >= 35:
        return "MEDIUM"
    return "LOW"


def _risk_summary(factors: List[Dict[str, str]]) -> str:
    high = [item["name"] for item in factors if item["level"] == "HIGH"]
    medium = [item["name"] for item in factors if item["level"] == "MEDIUM"]

    if high:
        return f"high risk factors include {', '.join(high)}."
    if medium:
        return f"medium risk factors include {', '.join(medium)}."
    return "all tracked risk factors are low."


def _push_next_steps(should_push: bool) -> List[str]:
    if should_push:
        return [
            "Create or update the Amazon listing for this SKU.",
            "Use the recommended price shown in the decision studio.",
            "Keep FBA fulfillment competitive while protecting the required margin.",
        ]

    return [
        "Do not push this item yet.",
        "Review the failed decision gates and high-risk factors.",
        "Re-run research after pricing, cost, ASIN confidence, or compliance issues are corrected.",
    ]


def _stable_int(seed: str, minimum: int, maximum: int) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    value = int(digest[:8], 16)
    return minimum + (value % (maximum - minimum + 1))


def _first(values: Any, fallback: str) -> str:
    if isinstance(values, list) and values:
        return str(values[0])
    return fallback

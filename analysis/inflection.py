"""Inflection point detection — company-agnostic.

Methods:
1. Second derivative of growth rate (sign flip = inflection)
2. Structural break detection via PELT (ruptures library)
3. Cross-company inflection comparison
"""

import json
from datetime import datetime
from pathlib import Path

import numpy as np
import ruptures as rpt

from analysis.growth import load_data, calc_qoq, interpolate_monthly

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def second_derivative(data_points: list[dict]) -> list[dict]:
    """Compute second derivative of revenue growth.
    Positive = growth accelerating; Negative = growth decelerating.
    Sign flip = inflection point."""
    qoq = calc_qoq(data_points)
    results = []
    for i in range(1, len(qoq)):
        prev = qoq[i - 1]
        curr = qoq[i]
        d2 = curr["annualized_growth_pct"] - prev["annualized_growth_pct"]
        # Time-weighted: rate of change per month
        days = (
            datetime.strptime(curr["date"], "%Y-%m-%d")
            - datetime.strptime(prev["date"], "%Y-%m-%d")
        ).days
        d2_per_month = d2 / (days / 30.44) if days > 0 else 0

        # Detect sign flip
        prev_sign = 1 if prev["annualized_growth_pct"] > 0 else -1
        curr_sign = 1 if curr["annualized_growth_pct"] > 0 else -1
        is_inflection = (prev_sign != curr_sign) and abs(
            prev["annualized_growth_pct"] - curr["annualized_growth_pct"]
        ) > 10  # threshold to avoid noise

        inflection_type = None
        if is_inflection:
            if d2 < 0:
                inflection_type = "growth_peak"
            else:
                inflection_type = "growth_trough"

        results.append({
            "date": curr["date"],
            "growth_rate_pct": curr["annualized_growth_pct"],
            "prev_growth_rate_pct": prev["annualized_growth_pct"],
            "second_derivative": round(d2, 2),
            "second_derivative_per_month": round(d2_per_month, 2),
            "is_inflection": is_inflection,
            "inflection_type": inflection_type,
        })
    return results


def detect_regime_change(
    data_points: list[dict],
    penalty: float = 10,
    min_segment_size: int = 2,
) -> list[dict]:
    """Detect structural breaks in growth rate using PELT algorithm.
    Returns changepoint dates with surrounding regime info."""
    if len(data_points) < 4:
        return []

    # Use interpolated monthly data for smoother signal
    monthly = interpolate_monthly(data_points)
    # Remove duplicates
    seen = set()
    unique_monthly = []
    for m in monthly:
        if m["date"] not in seen:
            seen.add(m["date"])
            unique_monthly.append(m)
    monthly = unique_monthly

    if len(monthly) < 4:
        return []

    # Compute revenue growth rate series
    revenue = np.array([m["revenue_b"] for m in monthly])
    # Log revenue for percentage change detection
    log_rev = np.log(np.maximum(revenue, 1e-6))

    # PELT with L2 cost (detects shifts in mean)
    algo = rpt.Pelt(custom_cost=None).fit(log_rev.reshape(-1, 1))
    try:
        breakpoints = algo.predict(pen=penalty)
    except Exception:
        return []

    # Convert breakpoints to dates
    changepoints = []
    for bp in breakpoints[:-1]:  # last is always len(series)
        if bp < min_segment_size or bp >= len(monthly) - min_segment_size:
            continue
        date = monthly[bp]["date"]

        # Calculate average growth rate before and after
        before_rev = [monthly[j]["revenue_b"] for j in range(max(0, bp - 3), bp)]
        after_rev = [monthly[j]["revenue_b"] for j in range(bp, min(len(monthly), bp + 3))]

        before_growth = 0
        after_growth = 0
        if len(before_rev) >= 2 and before_rev[0] > 0:
            before_growth = (before_rev[-1] / before_rev[0] - 1) * 100
        if len(after_rev) >= 2 and after_rev[0] > 0:
            after_growth = (after_rev[-1] / after_rev[0] - 1) * 100

        changepoints.append({
            "date": date,
            "index": bp,
            "avg_growth_before_pct": round(before_growth, 1),
            "avg_growth_after_pct": round(after_growth, 1),
            "growth_delta_pct": round(after_growth - before_growth, 1),
            "regime_shift": "deceleration" if after_growth < before_growth else "acceleration",
        })

    return changepoints


def find_inflections(data_points: list[dict]) -> dict:
    """Combine both methods for robust inflection detection."""
    d2_results = second_derivative(data_points)
    regime_results = detect_regime_change(data_points)

    # Mark inflections confirmed by both methods
    d2_dates = {r["date"] for r in d2_results if r["is_inflection"]}
    regime_dates = {r["date"] for r in regime_results}

    confirmed = []
    for r in d2_results:
        if r["is_inflection"]:
            r["confirmed_by_regime"] = r["date"] in regime_dates
            confirmed.append(r)

    return {
        "second_derivative": d2_results,
        "regime_changes": regime_results,
        "inflections": confirmed,
        "total_inflections_found": len(confirmed),
    }


def compare_inflections(
    company_a_points: list[dict],
    company_b_points: list[dict],
    name_a: str = "company_a",
    name_b: str = "company_b",
) -> dict:
    """Compare inflection timing across two companies.
    Did one company's growth slow before the other's?"""
    infl_a = find_inflections(company_a_points)
    infl_b = find_inflections(company_b_points)

    # Collect all inflection dates
    a_inflections = infl_a["inflections"]
    b_inflections = infl_b["inflections"]

    # Find matching inflection types (both peaked around the same time)
    comparisons = []
    for a in a_inflections:
        for b in b_inflections:
            if a["inflection_type"] == b["inflection_type"]:
                days_diff = (
                    datetime.strptime(a["date"], "%Y-%m-%d")
                    - datetime.strptime(b["date"], "%Y-%m-%d")
                ).days
                comparisons.append({
                    "inflection_type": a["inflection_type"],
                    f"{name_a}_date": a["date"],
                    f"{name_b}_date": b["date"],
                    "days_apart": days_diff,
                    "who_first": name_a if days_diff < 0 else name_b,
                })

    return {
        name_a: {"inflection_count": len(a_inflections), "inflections": a_inflections},
        name_b: {"inflection_count": len(b_inflections), "inflections": b_inflections},
        "comparisons": comparisons,
    }

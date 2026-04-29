"""Growth rate calculations — company-agnostic."""

import json
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_data(company: str) -> list[dict]:
    path = DATA_DIR / f"{company}_revenue.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.sort(key=lambda x: x["date"])
    return data


def parse_date(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%d")


def days_between(d1: str, d2: str) -> float:
    return (parse_date(d2) - parse_date(d1)).days


def calc_qoq(data_points: list[dict]) -> list[dict]:
    """Quarter-over-quarter growth rate between consecutive data points,
    annualized and scaled to represent a full quarter."""
    results = []
    for i in range(1, len(data_points)):
        prev = data_points[i - 1]
        curr = data_points[i]
        prev_rev = prev["revenue_b"]
        curr_rev = curr["revenue_b"]
        if prev_rev <= 0:
            continue
        days = days_between(prev["date"], curr["date"])
        if days <= 0:
            continue
        # Raw growth ratio over the period
        raw_growth = (curr_rev - prev_rev) / prev_rev
        # Annualize to get implied annual rate
        annualized = (1 + raw_growth) ** (365.25 / days) - 1
        # Quarterly rate
        quarterly = (1 + raw_growth) ** (90 / days) - 1
        results.append({
            "date": curr["date"],
            "from_date": prev["date"],
            "prev_revenue_b": prev_rev,
            "curr_revenue_b": curr_rev,
            "raw_growth_pct": round(raw_growth * 100, 1),
            "annualized_growth_pct": round(annualized * 100, 1),
            "quarterly_growth_pct": round(quarterly * 100, 1),
            "days_gap": days,
        })
    return results


def calc_yoy(data_points: list[dict]) -> list[dict]:
    """Year-over-year growth rate: find data points ~12 months apart."""
    results = []
    for i, curr in enumerate(data_points):
        curr_date = parse_date(curr["date"])
        # Find closest point 11-13 months before
        best = None
        best_diff = 999
        for prev in data_points[:i]:
            prev_date = parse_date(prev["date"])
            diff_days = (curr_date - prev_date).days
            diff_from_365 = abs(diff_days - 365)
            if 300 < diff_days < 430 and diff_from_365 < best_diff:
                best = prev
                best_diff = diff_from_365
        if best and best["revenue_b"] > 0:
            growth = (curr["revenue_b"] - best["revenue_b"]) / best["revenue_b"] * 100
            results.append({
                "date": curr["date"],
                "compare_date": best["date"],
                "revenue_b": curr["revenue_b"],
                "prev_revenue_b": best["revenue_b"],
                "yoy_growth_pct": round(growth, 1),
                "days_gap": (curr_date - parse_date(best["date"])).days,
            })
    return results


def calc_absolute_increment(data_points: list[dict]) -> list[dict]:
    """Absolute revenue increment ($B) between consecutive data points,
    annualized to represent rate of addition."""
    results = []
    for i in range(1, len(data_points)):
        prev = data_points[i - 1]
        curr = data_points[i]
        increment = curr["revenue_b"] - prev["revenue_b"]
        days = days_between(prev["date"], curr["date"])
        annualized_increment = increment * 365.25 / days if days > 0 else 0
        results.append({
            "date": curr["date"],
            "from_date": prev["date"],
            "increment_b": round(increment, 3),
            "annualized_increment_b": round(annualized_increment, 2),
            "days_gap": days,
        })
    return results


def calc_implied_monthly(data_points: list[dict]) -> list[dict]:
    """Monthly revenue implied from run-rate snapshots."""
    results = []
    for dp in data_points:
        if dp["metric_type"] in ("run_rate", "arr"):
            monthly = dp["revenue_b"] / 12
            results.append({
                "date": dp["date"],
                "revenue_b": dp["revenue_b"],
                "implied_monthly_b": round(monthly, 3),
                "metric_type": dp["metric_type"],
            })
    return results


def interpolate_monthly(data_points: list[dict]) -> list[dict]:
    """Linear interpolation between data points to produce monthly estimates.
    Useful for smoother rate calculations."""
    if len(data_points) < 2:
        return data_points

    monthly = []
    for i in range(1, len(data_points)):
        prev = data_points[i - 1]
        curr = data_points[i]
        prev_date = parse_date(prev["date"])
        curr_date = parse_date(curr["date"])
        days = (curr_date - prev_date).days
        if days <= 0:
            continue

        # Generate first day of each month in between
        m = prev_date.replace(day=1)
        end = curr_date.replace(day=1)
        while m <= end:
            frac = (m - prev_date).days / days
            frac = max(0, min(1, frac))
            interp_rev = prev["revenue_b"] + frac * (curr["revenue_b"] - prev["revenue_b"])
            monthly.append({
                "date": m.strftime("%Y-%m-01"),
                "revenue_b": round(interp_rev, 4),
                "interpolated": True,
            })
            # Next month
            if m.month == 12:
                m = m.replace(year=m.year + 1, month=1)
            else:
                m = m.replace(month=m.month + 1)

    # Add original points (not interpolated)
    for dp in data_points:
        monthly.append({
            "date": dp["date"],
            "revenue_b": dp["revenue_b"],
            "interpolated": False,
        })

    monthly.sort(key=lambda x: x["date"])
    return monthly

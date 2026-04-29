"""Gross/net revenue adjustment and crossover analysis.

Anthropic reports gross (includes cloud reseller bookings).
OpenAI reports net (deducts Microsoft ~20% share).
This module adjusts both to a common basis for comparison.
"""

import json
from datetime import datetime
from pathlib import Path

from analysis.forecast import ensemble_forecast, linear_extrapolation
from analysis.growth import load_data

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_params() -> dict:
    with open(DATA_DIR / "comparability_params.json", encoding="utf-8") as f:
        return json.load(f)


def gross_to_net(
    revenue: float,
    cloud_take_rate: float = 0.25,
    cloud_channel_pct: float = 0.40,
) -> float:
    """Convert Anthropic gross revenue to net equivalent.
    net = gross - (gross * cloud_channel_pct * cloud_take_rate)"""
    deduction = revenue * cloud_channel_pct * cloud_take_rate
    return round(revenue - deduction, 2)


def net_to_gross(
    revenue: float,
    microsoft_share_rate: float = 0.20,
    azure_channel_pct: float = 0.30,
) -> float:
    """Convert OpenAI net revenue to gross equivalent.
    gross = net + (net * azure_channel_pct * microsoft_share_rate)"""
    addition = revenue * azure_channel_pct * microsoft_share_rate
    return round(revenue + addition, 2)


def adjust_for_comparability(
    data_points: list[dict],
    target_basis: str = "net",
    params: dict | None = None,
) -> list[dict]:
    """Adjust data points to a common reporting basis.
    target_basis: 'gross' or 'net'"""
    if params is None:
        params = load_params()

    adjusted = []
    for dp in data_points:
        new_dp = dict(dp)
        company = dp["company"]

        if dp["reporting_basis"] == target_basis:
            # Already on target basis
            new_dp["adjusted"] = False
        elif company == "anthropic" and target_basis == "net":
            p = params["anthropic"]["gross_to_net"]
            new_dp["revenue_b"] = gross_to_net(
                dp["revenue_b"],
                p["cloud_partner_take_rate"],
                p["cloud_channel_pct"],
            )
            new_dp["reporting_basis"] = "estimated_net"
            new_dp["adjusted"] = True
        elif company == "openai" and target_basis == "gross":
            p = params["openai"]["net_to_gross"]
            new_dp["revenue_b"] = net_to_gross(
                dp["revenue_b"],
                p["microsoft_share_rate"],
                p["azure_channel_pct"],
            )
            new_dp["reporting_basis"] = "estimated_gross"
            new_dp["adjusted"] = True
        else:
            new_dp["adjusted"] = False

        adjusted.append(new_dp)
    return adjusted


def sensitivity_analysis(
    data_points: list[dict],
    company: str,
    param_name: str,
    param_range: list[float],
) -> list[dict]:
    """Show revenue under different assumption sets for one parameter."""
    params = load_params()
    results = []

    for val in param_range:
        if company == "anthropic":
            if param_name == "cloud_take_rate":
                adjusted_rev = gross_to_net(
                    data_points[-1]["revenue_b"],
                    cloud_take_rate=val,
                    cloud_channel_pct=params["anthropic"]["gross_to_net"]["cloud_channel_pct"],
                )
            elif param_name == "cloud_channel_pct":
                adjusted_rev = gross_to_net(
                    data_points[-1]["revenue_b"],
                    cloud_take_rate=params["anthropic"]["gross_to_net"]["cloud_partner_take_rate"],
                    cloud_channel_pct=val,
                )
        elif company == "openai":
            if param_name == "microsoft_share_rate":
                adjusted_rev = net_to_gross(
                    data_points[-1]["revenue_b"],
                    microsoft_share_rate=val,
                    azure_channel_pct=params["openai"]["net_to_gross"]["azure_channel_pct"],
                )
            elif param_name == "azure_channel_pct":
                adjusted_rev = net_to_gross(
                    data_points[-1]["revenue_b"],
                    microsoft_share_rate=params["openai"]["net_to_gross"]["microsoft_share_rate"],
                    azure_channel_pct=val,
                )

        results.append({
            "param_value": val,
            "latest_revenue_b": data_points[-1]["revenue_b"],
            "adjusted_revenue_b": adjusted_rev,
            "adjustment_b": round(adjusted_rev - data_points[-1]["revenue_b"], 2),
        })

    return results


def crossover_analysis(
    anthropic_data: list[dict],
    openai_data: list[dict],
    basis: str = "net",
    periods_ahead: int = 12,
) -> dict:
    """Estimate when/if Anthropic's revenue surpasses OpenAI's.
    Runs forecasts for both and finds intersection."""
    # Adjust to common basis
    params = load_params()
    anthro_adj = adjust_for_comparability(anthropic_data, basis, params)
    openai_adj = adjust_for_comparability(openai_data, basis, params)

    # Forecast both using economics-grounded models
    anthro_forecast = ensemble_forecast(anthro_adj, periods_ahead, company="anthropic")
    openai_forecast = ensemble_forecast(openai_adj, periods_ahead, company="openai")

    if "error" in anthro_forecast or "error" in openai_forecast:
        return {"crossover_found": False, "reason": "Forecast failed for one or both companies"}

    # Find first point where Anthropic >= OpenAI
    crossover_date = None
    crossover_revenue = None
    for af, of in zip(anthro_forecast["forecast"], openai_forecast["forecast"]):
        if af["predicted_b"] >= of["predicted_b"]:
            crossover_date = af["date"]
            crossover_revenue = af["predicted_b"]
            break

    # Current gap
    current_anthro = anthropic_data[-1]["revenue_b"]
    current_openai = openai_data[-1]["revenue_b"]
    if basis == "net":
        current_anthro = gross_to_net(current_anthro)
        current_openai = current_openai  # already net

    return {
        "basis": basis,
        "current_anthro_b": round(current_anthro, 2),
        "current_openai_b": round(current_openai, 2),
        "current_gap_b": round(current_openai - current_anthro, 2),
        "crossover_found": crossover_date is not None,
        "crossover_date": crossover_date,
        "crossover_revenue_b": crossover_revenue,
        "anthro_forecast": anthro_forecast,
        "openai_forecast": openai_forecast,
    }

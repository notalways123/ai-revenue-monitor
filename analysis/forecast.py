"""Economics-grounded revenue prediction.

Models revenue as the product of TAM x Penetration, per revenue segment.
Each segment has its own TAM ceiling and adoption curve.

Segments for Anthropic:
  - API / Enterprise AI (largest, growing but competitive)
  - Coding tools / Claude Code (high share but approaching developer TAM ceiling)
  - Consumer subscriptions (Claude Pro/Max, smaller TAM)

Segments for OpenAI:
  - Consumer subscriptions (ChatGPT Plus/Pro/Team, large but saturated free user base)
  - Enterprise / API (growing rapidly from lower base)
  - Microsoft partnership revenue

Key economic logic:
  - Revenue = sum(segment_TAM * penetration_rate)
  - Penetration follows Bass diffusion (innovators + imitators)
  - Growth decelerates as penetration approaches saturation
  - Competition constrains each company's share of shared TAM
"""

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
from scipy.optimize import curve_fit

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def _months_ahead(dates: list[str], n_months: int) -> list[str]:
    last = datetime.strptime(dates[-1], "%Y-%m-%d")
    result = []
    for m in range(1, n_months + 1):
        future = last + timedelta(days=m * 30.44)
        result.append(future.strftime("%Y-%m-01"))
    return result


# ---- TAM and segment definitions ----

SEGMENT_PARAMS = {
    "anthropic": {
        "segments": {
            "api_enterprise": {
                "tam_b": 120,          # Enterprise AI API market 2026-2027 (~$120B)
                "tam_growth_rate": 0.35, # TAM itself growing ~35%/yr as AI adoption expands
                "current_share": 0.32, # 32% enterprise LLM API share
                "max_share": 0.40,     # realistic max given competition
                "bass_p": 0.03,        # innovation coefficient
                "bass_q": 0.30,        # imitation coefficient
            },
            "coding_tools": {
                "tam_b": 25,           # AI coding tools market 2026-2027 (~$25B)
                "tam_growth_rate": 0.25, # developer AI tools TAM growing ~25%/yr
                "current_share": 0.54, # 54% AI programming-tool segment
                "max_share": 0.60,     # near ceiling — developer TAM finite
                "bass_p": 0.02,
                "bass_q": 0.20,        # lower imitation — early majority already adopted
            },
            "consumer_subscription": {
                "tam_b": 15,           # AI consumer subscription market 2026-2027
                "tam_growth_rate": 0.20, # consumer AI TAM growing ~20%/yr
                "current_share": 0.08, # ~12M MAU vs ~100M+ addressable
                "max_share": 0.20,     # limited by ChatGPT dominance
                "bass_p": 0.01,
                "bass_q": 0.25,
            },
        },
        "revenue_split": {  # approximate current split
            "api_enterprise": 0.70,
            "coding_tools": 0.18,      # Claude Code $2.5B / $14B total (Feb 2026)
            "consumer_subscription": 0.12,
        },
    },
    "openai": {
        "segments": {
            "consumer_subscription": {
                "tam_b": 15,           # same consumer AI subscription TAM
                "tam_growth_rate": 0.20,
                "current_share": 0.60, # dominant — 18M+ paid subs
                "max_share": 0.65,     # near ceiling, most willing payers already subscribed
                "bass_p": 0.01,
                "bass_q": 0.15,        # low imitation — mature segment
            },
            "enterprise_api": {
                "tam_b": 120,          # same enterprise AI API TAM
                "tam_growth_rate": 0.35,
                "current_share": 0.25, # 25% enterprise LLM API share
                "max_share": 0.35,     # could grow but Anthropic competitive
                "bass_p": 0.03,
                "bass_q": 0.35,        # high imitation — enterprise adoption accelerating
            },
            "microsoft_partnership": {
                "tam_b": 30,           # Azure AI revenue share to OpenAI
                "tam_growth_rate": 0.25,
                "current_share": 0.50,
                "max_share": 0.55,
                "bass_p": 0.02,
                "bass_q": 0.20,
            },
        },
        "revenue_split": {
            "consumer_subscription": 0.45,
            "enterprise_api": 0.35,
            "microsoft_partnership": 0.10,
            "other": 0.10,
        },
    },
}


def _bass_diffusion(t: float, p: float, q: float, m: float = 1.0) -> float:
    """Bass diffusion model: fraction of TAM adopted at time t.
    t is in years from diffusion start.
    Returns penetration fraction [0, 1].
    F(t) = (1 - e^(-(p+q)t)) / (1 + (q/p) * e^(-(p+q)t))
    """
    if p + q == 0:
        return 0
    exp_term = np.exp(-(p + q) * t)
    denom = 1 + (q / p) * exp_term if p > 0 else 1
    if abs(denom) < 1e-10:
        return m
    return m * (1 - exp_term) / denom


def _bass_derivative(t: float, p: float, q: float) -> float:
    """Rate of adoption at time t (derivative of Bass curve)."""
    exp_term = np.exp(-(p + q) * t)
    num = (p + q) ** 2 * exp_term
    denom = (p + q * exp_term) ** 2 if p > 0 else 1
    if abs(denom) < 1e-10:
        return 0
    return num / denom


def _estimate_bass_t0(current_share: float, max_share: float, p: float, q: float) -> float:
    """Given current penetration as fraction of max, estimate how many years
    into the Bass diffusion curve we are."""
    if current_share <= 0 or max_share <= 0:
        return 0
    fraction = current_share / max_share
    fraction = min(fraction, 0.99)
    # Solve F(t) = fraction numerically
    for t in np.arange(0, 30, 0.01):
        if _bass_diffusion(t, p, q) >= fraction:
            return t
    return 15.0  # fallback


def tam_driven_forecast(
    data_points: list[dict],
    company: str,
    periods_ahead: int = 12,
) -> dict:
    """Economics-grounded forecast: revenue = sum(TAM_i * penetration_i).

    Each revenue segment has its own TAM and adoption curve.
    Growth decelerates as segments approach saturation.
    """
    params = SEGMENT_PARAMS[company]
    segments = params["segments"]
    split = params["revenue_split"]

    latest_rev = data_points[-1]["revenue_b"]
    dates = [d["date"] for d in data_points]

    # For each segment, compute current revenue and project forward
    segment_forecasts = {}
    total_forecasts = []

    for seg_name, seg_params in segments.items():
        tam = seg_params["tam_b"]
        current_share = seg_params["current_share"]
        max_share = seg_params["max_share"]
        p = seg_params["bass_p"]
        q = seg_params["bass_q"]

        # Current segment revenue
        seg_weight = split.get(seg_name, 0)
        current_seg_rev = latest_rev * seg_weight

        # Where are we on the Bass curve?
        t0 = _estimate_bass_t0(current_share, max_share, p, q)
        current_penetration = _bass_diffusion(t0, p, q)

        # Segment TAM available to this company
        addressable_tam = tam * max_share

        # Current revenue vs Bass-implied revenue (calibrate)
        bass_implied_rev = addressable_tam * current_penetration
        # Scale factor to match actual revenue
        scale = current_seg_rev / bass_implied_rev if bass_implied_rev > 0 else 1

        # Project forward with growing TAM
        seg_forecast = []
        for m in range(1, periods_ahead + 1):
            t_future = t0 + m / 12.0
            future_penetration = _bass_diffusion(t_future, p, q)
            # TAM grows over time — the pie itself is expanding
            tam_growth = seg_params.get("tam_growth_rate", 0.25)
            grown_tam = tam * (1 + tam_growth) ** (m / 12.0)
            grown_addressable = grown_tam * max_share
            future_rev = grown_addressable * future_penetration * scale
            seg_forecast.append(round(max(future_rev, 0), 2))

        segment_forecasts[seg_name] = {
            "tam_b": tam,
            "addressable_tam_b": round(addressable_tam, 1),
            "current_share": current_share,
            "max_share": max_share,
            "current_penetration": round(current_penetration, 4),
            "years_into_diffusion": round(t0, 2),
            "bass_p": p,
            "bass_q": q,
            "current_rev_b": round(current_seg_rev, 2),
            "ceiling_rev_b": round(addressable_tam * scale, 1),
            "saturation_pct": round(current_share / max_share * 100, 1),
            "forecast_b": seg_forecast,
        }

    # Sum across segments for each period
    forecast_dates = _months_ahead(dates, periods_ahead)
    for i in range(periods_ahead):
        total = sum(sf["forecast_b"][i] for sf in segment_forecasts.values())
        total_forecasts.append({
            "date": forecast_dates[i],
            "predicted_b": round(max(total, 0), 2),
        })

    # Confidence interval based on TAM uncertainty
    # Low scenario: TAM 30% lower, shares 10% lower
    # High scenario: TAM 30% higher, shares 10% higher (but capped at max_share)
    upper = []
    lower = []
    for i in range(periods_ahead):
        total_high = 0
        total_low = 0
        for seg_name, seg_params in segments.items():
            tam_high = seg_params["tam_b"] * 1.3
            tam_low = seg_params["tam_b"] * 0.7
            share_high = min(seg_params["max_share"] * 1.1, seg_params["max_share"])
            share_low = seg_params["current_share"] * 0.9
            t0_seg = _estimate_bass_t0(seg_params["current_share"], seg_params["max_share"], seg_params["bass_p"], seg_params["bass_q"])
            t_future = t0_seg + (i + 1) / 12.0
            pen = _bass_diffusion(t_future, seg_params["bass_p"], seg_params["bass_q"])
            seg_weight = split.get(seg_name, 0)
            scale = (latest_rev * seg_weight) / (seg_params["tam_b"] * seg_params["max_share"] * _bass_diffusion(t0_seg, seg_params["bass_p"], seg_params["bass_q"])) if _bass_diffusion(t0_seg, seg_params["bass_p"], seg_params["bass_q"]) > 0 else 1
            total_high += tam_high * share_high * pen * scale
            total_low += tam_low * share_low * pen * scale
        upper.append(round(max(total_high, 0), 2))
        lower.append(round(max(total_low, 0), 2))

    return {
        "method": "tam_driven",
        "company": company,
        "latest_revenue_b": latest_rev,
        "segment_analysis": segment_forecasts,
        "forecast": total_forecasts,
        "confidence_interval_80": {"upper": upper, "lower": lower},
        "assumptions": (
            "Revenue = sum(TAM_segment * penetration_segment). "
            "Each segment follows Bass diffusion with segment-specific TAM ceiling. "
            "Growth decelerates as segments approach saturation. "
            "Claude Code near developer TAM ceiling; enterprise API still has runway. "
            "Consumer subscription limited by ChatGPT dominance."
        ),
    }


# ---- Retained pure-math models for comparison ----

def _logistic(x, L, k, x0):
    return L / (1 + np.exp(-k * (x - x0)))


def scurve_fit(
    data_points: list[dict],
    periods_ahead: int = 6,
    curve_type: str = "logistic",
) -> dict:
    """Pure-math S-curve fit (retained for comparison, NOT the primary model)."""
    if len(data_points) < 4:
        return {"error": "Need at least 4 data points"}

    dates = [d["date"] for d in data_points]
    revs = [d["revenue_b"] for d in data_points]
    first_date = datetime.strptime(dates[0], "%Y-%m-%d")
    x = np.array([(datetime.strptime(d, "%Y-%m-%d") - first_date).days / 30.44 for d in dates])
    y = np.array(revs)

    func = _logistic
    L0 = max(y) * 3
    k0 = 0.1
    x00 = np.median(x)

    try:
        popt, pcov = curve_fit(
            func, x, y, p0=[L0, k0, x00],
            maxfev=10000,
            bounds=([0, 0.001, -100], [500, 2, 500]),
        )
        L, k, x0 = popt
        perr = np.sqrt(np.diag(pcov))
        forecast_dates = _months_ahead(dates, periods_ahead)
        forecasts = []
        upper = []
        lower = []
        for fd in forecast_dates:
            fx = (datetime.strptime(fd, "%Y-%m-%d") - first_date).days / 30.44
            pred = func(fx, *popt)
            pred_upper = func(fx, *(popt + 1.28 * perr))
            pred_lower = func(fx, *(popt - 1.28 * perr))
            forecasts.append({"date": fd, "predicted_b": round(max(pred, 0), 2)})
            upper.append(round(max(pred_upper, 0), 2))
            lower.append(round(max(pred_lower, 0), 2))

        return {
            "method": f"scurve_{curve_type}",
            "params": {"L": round(L, 2), "k": round(k, 4), "x0": round(x0, 2)},
            "ceiling_b": round(L, 2),
            "forecast": forecasts,
            "confidence_interval_80": {"upper": upper, "lower": lower},
            "assumptions": f"Pure math S-curve; ceiling ~${round(L, 1)}B (NOT economics-grounded)",
        }
    except (RuntimeError, ValueError):
        return {"error": "S-curve fit failed"}


def linear_extrapolation(
    data_points: list[dict],
    periods_ahead: int = 6,
    recent_n: int = 4,
) -> dict:
    """Linear extrapolation (retained for comparison, NOT the primary model)."""
    recent = data_points[-recent_n:]
    if len(recent) < 2:
        return {"error": "Need at least 2 data points"}

    dates = [r["date"] for r in recent]
    revs = [r["revenue_b"] for r in recent]
    first_date = datetime.strptime(dates[0], "%Y-%m-%d")
    x = np.array([(datetime.strptime(d, "%Y-%m-%d") - first_date).days / 30.44 for d in dates])
    y = np.array(revs)

    coeffs = np.polyfit(x, y, 1)
    slope, intercept = coeffs
    forecast_dates = _months_ahead(dates, periods_ahead)
    forecasts = []
    for fd in forecast_dates:
        months_from_start = (datetime.strptime(fd, "%Y-%m-%d") - first_date).days / 30.44
        pred = slope * months_from_start + intercept
        forecasts.append({"date": fd, "predicted_b": round(max(pred, 0), 2)})

    residuals = y - (slope * x + intercept)
    std_err = np.std(residuals) if len(residuals) > 2 else 0.5 * y[-1]

    return {
        "method": "linear_extrapolation",
        "slope_per_month": round(slope, 3),
        "forecast": forecasts,
        "confidence_interval_80": {
            "upper": [round(max(f["predicted_b"] + 1.28 * std_err, 0), 2) for f in forecasts],
            "lower": [round(max(f["predicted_b"] - 1.28 * std_err, 0), 2) for f in forecasts],
        },
        "assumptions": f"Pure math linear trend (NOT economics-grounded)",
    }


def ensemble_forecast(
    data_points: list[dict],
    periods_ahead: int = 12,
    company: str | None = None,
) -> dict:
    """Primary forecast: economics-grounded TAM model.

    When company is specified, uses TAM-driven Bass diffusion as the sole
    forward model. Pure math models (S-curve, linear) are NOT blended in
    because they lack economic grounding — all historical data is in the
    hypergrowth phase, so curve fitting produces absurdly high ceilings.

    The TAM model's confidence interval already captures uncertainty via
    TAM range and share range scenarios.
    """
    if company and company in SEGMENT_PARAMS:
        tam_result = tam_driven_forecast(data_points, company, periods_ahead)

        return {
            "method": "tam_driven",
            "company": company,
            "primary_model": "tam_driven",
            "segment_analysis": tam_result["segment_analysis"],
            "forecast": tam_result["forecast"],
            "confidence_interval_80": tam_result["confidence_interval_80"],
            "assumptions": tam_result["assumptions"],
        }

    # Fallback: no company specified, use pure math ensemble
    linear = linear_extrapolation(data_points, periods_ahead)
    scurve = scurve_fit(data_points, periods_ahead, "logistic")

    methods = [m for m in [linear, scurve] if "error" not in m]
    if not methods:
        return {"error": "All forecast methods failed"}

    forecast_dates = _months_ahead([d["date"] for d in data_points], periods_ahead)
    blend = []
    for i in range(periods_ahead):
        preds = []
        for m in methods:
            if i < len(m.get("forecast", [])):
                preds.append(m["forecast"][i]["predicted_b"])
        avg = sum(preds) / len(preds) if preds else 0
        blend.append({"date": forecast_dates[i], "predicted_b": round(max(avg, 0), 2)})

    return {
        "method": "math_ensemble",
        "forecast": blend,
        "assumptions": "Pure mathematical ensemble (no company economics available)",
    }

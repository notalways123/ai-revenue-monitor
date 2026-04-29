"""Generate pre-computed dashboard data from analysis engine."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.growth import load_data, calc_qoq, calc_yoy, calc_absolute_increment, calc_implied_monthly
from analysis.inflection import find_inflections, compare_inflections
from analysis.forecast import linear_extrapolation, scurve_fit, ensemble_forecast
from analysis.comparability import (
    adjust_for_comparability, crossover_analysis,
    sensitivity_analysis, gross_to_net, net_to_gross, load_params,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_DIR / "data"
DASHBOARD_DIR = PROJECT_DIR / "dashboard"


def main():
    anthro = load_data("anthropic")
    openai = load_data("openai")
    params = load_params()

    data = {
        "generated_at": __import__("datetime").datetime.now().isoformat(),
        "anthropic": {
            "revenue_points": anthro,
            "qoq": calc_qoq(anthro),
            "yoy": calc_yoy(anthro),
            "absolute_increment": calc_absolute_increment(anthro),
            "implied_monthly": calc_implied_monthly(anthro),
            "inflections": find_inflections(anthro),
            "forecast_ensemble": ensemble_forecast(anthro, 57, company="anthropic"),
            "latest": {
                "date": anthro[-1]["date"],
                "revenue_b": anthro[-1]["revenue_b"],
                "reporting_basis": anthro[-1]["reporting_basis"],
                "net_estimate_b": gross_to_net(anthro[-1]["revenue_b"]),
            },
        },
        "openai": {
            "revenue_points": openai,
            "qoq": calc_qoq(openai),
            "yoy": calc_yoy(openai),
            "absolute_increment": calc_absolute_increment(openai),
            "implied_monthly": calc_implied_monthly(openai),
            "inflections": find_inflections(openai),
            "forecast_ensemble": ensemble_forecast(openai, 57, company="openai"),
            "latest": {
                "date": openai[-1]["date"],
                "revenue_b": openai[-1]["revenue_b"],
                "reporting_basis": openai[-1]["reporting_basis"],
                "gross_estimate_b": net_to_gross(openai[-1]["revenue_b"]),
            },
        },
        "comparison": {
            "crossover_net": crossover_analysis(anthro, openai, "net", 57),
            "crossover_gross": crossover_analysis(anthro, openai, "gross", 57),
            "inflection_comparison": compare_inflections(anthro, openai, "anthropic", "openai"),
        },
        "sensitivity": {
            "anthropic_net_range": sensitivity_analysis(
                anthro, "anthropic", "cloud_take_rate",
                params["sensitivity_ranges"]["anthropic_cloud_take_rate"],
            ),
            "openai_gross_range": sensitivity_analysis(
                openai, "openai", "azure_channel_pct",
                params["sensitivity_ranges"]["openai_azure_channel_pct"],
            ),
        },
        "comparability_params": params,
    }

    out_path = DASHBOARD_DIR / "dashboard_data.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    print(f"Dashboard data written to {out_path}")
    print(f"  Anthropic: {len(anthro)} points, latest ${anthro[-1]['revenue_b']}B")
    print(f"  OpenAI: {len(openai)} points, latest ${openai[-1]['revenue_b']}B")
    print(f"  Crossover (net): {data['comparison']['crossover_net']['crossover_found']}")


if __name__ == "__main__":
    main()

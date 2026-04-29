"""Weekly update script — orchestrates data collection and dashboard refresh.

This script is designed to be called by Claude Code's scheduled task.
It outputs findings for user review and updates the dashboard data.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors.exa_search import (
    load_existing_data, save_data, extract_new_data_points,
    format_for_review, get_search_queries,
)

PROJECT_DIR = Path(__file__).resolve().parent.parent


def check_alerts(company: str, data: list[dict]) -> list[dict]:
    """Check for alert conditions after data update."""
    from analysis.growth import calc_qoq
    from analysis.inflection import second_derivative

    alerts = []
    qoq = calc_qoq(data)
    d2 = second_derivative(data)

    # Growth deceleration
    if len(qoq) >= 2:
        latest = qoq[-1]
        prev = qoq[-2]
        if latest["annualized_growth_pct"] < prev["annualized_growth_pct"]:
            alerts.append({
                "type": "growth_deceleration",
                "severity": "warning",
                "company": company,
                "message": f"{company}: Growth decelerating from {prev['annualized_growth_pct']}% to {latest['annualized_growth_pct']}%",
            })

    # Inflection detected
    for d in d2:
        if d["is_inflection"]:
            alerts.append({
                "type": "inflection",
                "severity": "critical",
                "company": company,
                "message": f"{company}: Inflection detected at {d['date']} — {d['inflection_type']}",
            })

    # New official disclosure (high confidence latest point)
    if data and data[-1]["confidence"] == "high" and data[-1]["source"].endswith("official"):
        alerts.append({
            "type": "new_disclosure",
            "severity": "info",
            "company": company,
            "message": f"{company}: New official disclosure — ${data[-1]['revenue_b']}B at {data[-1]['date']}",
        })

    return alerts


def main():
    print("=" * 50)
    print(f"AI Revenue Monitor — Weekly Update")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 50)

    all_alerts = []
    for company in ["anthropic", "openai"]:
        existing = load_existing_data(company)
        print(f"\n--- {company.upper()} ---")
        print(f"Existing data points: {len(existing)}")
        print(f"Latest: ${existing[-1]['revenue_b']}B ({existing[-1]['date']})")

        # Check alerts on existing data
        alerts = check_alerts(company, existing)
        all_alerts.extend(alerts)

        # Search queries for reference
        queries = get_search_queries(company)
        print(f"\nSearch queries to run:")
        for q in queries:
            print(f"  - {q}")

        print(f"\nNOTE: Use Claude Code's Exa MCP tool to search for new data.")
        print(f"After finding new data, add confirmed points to data/{company}_revenue.json")

    # Alerts summary
    if all_alerts:
        print(f"\n{'=' * 50}")
        print(f"ALERTS ({len(all_alerts)})")
        print(f"{'=' * 50}")
        for a in all_alerts:
            icon = {"warning": "[W]", "critical": "[!]", "info": "[i]"}.get(a["severity"], "[-]")
            print(f"  {icon} [{a['severity'].upper()}] {a['message']}")

    print(f"\nTo regenerate dashboard data after updates:")
    print(f"  python scripts/generate_dashboard.py")


if __name__ == "__main__":
    main()

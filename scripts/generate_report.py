"""Generate weekly Markdown report."""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from analysis.growth import load_data, calc_qoq, calc_yoy
from analysis.inflection import find_inflections
from analysis.forecast import ensemble_forecast
from analysis.comparability import crossover_analysis, gross_to_net, net_to_gross

PROJECT_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = PROJECT_DIR / "reports" / "weekly"


def main():
    anthro = load_data("anthropic")
    openai = load_data("openai")
    now = datetime.now().strftime("%Y-%m-%d")

    a_latest = anthro[-1]
    o_latest = openai[-1]
    a_qoq = calc_qoq(anthro)
    o_qoq = calc_qoq(openai)
    a_yoy = calc_yoy(anthro)
    o_yoy = calc_yoy(openai)
    a_infl = find_inflections(anthro)
    o_infl = find_inflections(openai)
    a_fc = ensemble_forecast(anthro, 57, company="anthropic")
    o_fc = ensemble_forecast(openai, 48, company="openai")
    co = crossover_analysis(anthro, openai, "net", 57)

    report = f"""# AI Revenue Monitor — Weekly Report

**Date**: {now}

## Summary

| Metric | Anthropic | OpenAI |
|--------|-----------|--------|
| Latest ARR | ${a_latest['revenue_b']}B ({a_latest['reporting_basis']}) | ${o_latest['revenue_b']}B ({o_latest['reporting_basis']}) |
| Latest Date | {a_latest['date']} | {o_latest['date']} |
| Est. Net | ${gross_to_net(a_latest['revenue_b'])}B | ${o_latest['revenue_b']}B (already net) |
| Est. Gross | ${a_latest['revenue_b']}B (already gross) | ${net_to_gross(o_latest['revenue_b'])}B |

## Growth Rates

### Anthropic
| Period | From | Revenue Change | Annualized Growth |
|--------|------|---------------|-------------------|
"""

    for q in a_qoq[-5:]:
        report += f"| {q['date']} | {q['from_date']} | ${q['prev_revenue_b']}B → ${q['curr_revenue_b']}B | {q['annualized_growth_pct']}% |\n"

    report += f"""
### OpenAI
| Period | From | Revenue Change | Annualized Growth |
|--------|------|---------------|-------------------|
"""

    for q in o_qoq[-5:]:
        report += f"| {q['date']} | {q['from_date']} | ${q['prev_revenue_b']}B → ${q['curr_revenue_b']}B | {q['annualized_growth_pct']}% |\n"

    # Inflections
    report += f"""
## Inflection Points

### Anthropic ({len(a_infl['inflections'])} detected)
"""

    for i in a_infl["inflections"]:
        report += f"- **{i['date']}**: {i['inflection_type']} (2nd derivative: {i['second_derivative']}%)\n"

    if not a_infl["inflections"]:
        report += "- No inflections detected\n"

    report += f"""
### OpenAI ({len(o_infl['inflections'])} detected)
"""

    for i in o_infl["inflections"]:
        report += f"- **{i['date']}**: {i['inflection_type']} (2nd derivative: {i['second_derivative']}%)\n"

    if not o_infl["inflections"]:
        report += "- No inflections detected\n"

    # Crossover
    report += f"""
## Crossover Analysis (Net Basis)

- Current gap: ${abs(co['current_gap_b'])}B ({'Anthropic leads' if co['current_gap_b'] < 0 else 'OpenAI leads'})
- Crossover found: {'Yes — ' + co['crossover_date'] if co['crossover_found'] else 'Not within forecast period'}
"""

    # Forecast
    report += """
## 4-Year Forecast to 2030 (Economics-Grounded)

Method: TAM-driven Bass diffusion per revenue segment. No pure-math blending.

### Anthropic
| Date | Predicted | Method |
|------|-----------|--------|
"""

    if "forecast" in a_fc:
        for f in a_fc["forecast"]:
            report += f"| {f['date']} | ${f['predicted_b']}B | {a_fc.get('method', 'ensemble')} |\n"

    # Segment analysis
    if "segment_analysis" in a_fc:
        report += "\n**Anthropic Segment Breakdown:**\n\n"
        report += "| Segment | TAM | Addressable | Current Share | Max Share | Saturation |\n"
        report += "|---------|-----|-------------|---------------|-----------|------------|\n"
        for seg_name, seg in a_fc["segment_analysis"].items():
            report += f"| {seg_name} | ${seg['tam_b']}B | ${seg['addressable_tam_b']}B | {seg['current_share']*100:.0f}% | {seg['max_share']*100:.0f}% | {seg['saturation_pct']}% |\n"
        report += "\n*Saturation = current_share / max_share. Near 100% means limited growth runway.*\n"

    report += """
### OpenAI
| Date | Predicted | Method |
|------|-----------|--------|
"""

    if "forecast" in o_fc:
        for f in o_fc["forecast"]:
            report += f"| {f['date']} | ${f['predicted_b']}B | {o_fc.get('method', 'ensemble')} |\n"

    if "segment_analysis" in o_fc:
        report += "\n**OpenAI Segment Breakdown:**\n\n"
        report += "| Segment | TAM | Addressable | Current Share | Max Share | Saturation |\n"
        report += "|---------|-----|-------------|---------------|-----------|------------|\n"
        for seg_name, seg in o_fc["segment_analysis"].items():
            report += f"| {seg_name} | ${seg['tam_b']}B | ${seg['addressable_tam_b']}B | {seg['current_share']*100:.0f}% | {seg['max_share']*100:.0f}% | {seg['saturation_pct']}% |\n"

    # Risk flags
    report += """
## Risk Flags

- Anthropic reports on **gross basis** (includes cloud reseller). Adjusted net estimate assumes 25% take-rate on 40% cloud channel — these parameters are unverified.
- OpenAI reports on **net basis** (excludes Microsoft share). Actual gross revenue is higher.
- Run-rate figures != recognized revenue. OpenAI's 2025 recognized revenue was $13.1B vs $20B+ annualized.
- **Growth deceleration is expected**: Claude Code has 54% of AI coding tools (near TAM ceiling for developers). Enterprise API still has runway but competition intensifies.
- TAM estimates are uncertain. Enterprise AI TAM could be $80B or $200B depending on definition.
- Consumer subscription market is limited by ChatGPT's dominance; Anthropic's max share capped at ~20%.
- Forecasts use Bass diffusion with economics-grounded TAM ceilings, NOT pure trend extrapolation.
"""

    # Save
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"report-{now}.md"
    with open(path, "w", encoding="utf-8") as f:
        f.write(report)

    print(f"Report saved to {path}")
    return report


if __name__ == "__main__":
    main()

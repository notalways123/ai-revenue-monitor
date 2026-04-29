"""Exa search collector for Anthropic and OpenAI revenue news."""

import json
from datetime import datetime, timedelta
from pathlib import Path

# This module is designed to be called from Claude Code's weekly scheduled task.
# It uses the Exa MCP tool which is available in the Claude Code environment.
# When run standalone (outside Claude Code), it falls back to a manual template.

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


def load_existing_data(company: str) -> list[dict]:
    path = DATA_DIR / f"{company}_revenue.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_data(company: str, data: list[dict]):
    path = DATA_DIR / f"{company}_revenue.json"
    data.sort(key=lambda x: x["date"])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def extract_new_data_points(
    search_results: list[dict],
    existing_data: list[dict],
    company: str,
) -> list[dict]:
    """Identify genuinely new data points from search results.
    Returns entries that don't match any existing data point."""
    existing_revenues = {(dp["date"], dp["revenue_b"]) for dp in existing_data}
    new_points = []

    for result in search_results:
        date = result.get("date")
        revenue = result.get("revenue_b")
        if not date or not revenue:
            continue
        if (date, revenue) not in existing_revenues:
            new_points.append(result)

    return new_points


def format_for_review(new_points: list[dict], company: str) -> str:
    """Format new data points for user review."""
    if not new_points:
        return f"No new {company} revenue data points found this week."

    lines = [f"Found {len(new_points)} new {company} data point(s) for review:\n"]
    for i, p in enumerate(new_points, 1):
        lines.append(f"  {i}. Date: {p.get('date', '?')}")
        lines.append(f"     Revenue: ${p.get('revenue_b', '?')}B ({p.get('metric_type', '?')})")
        lines.append(f"     Source: {p.get('source', '?')}")
        lines.append(f"     Confidence: {p.get('confidence', '?')}")
        lines.append(f"     Notes: {p.get('notes', '')}")
        lines.append("")

    lines.append("Reply with the numbers to confirm (e.g., '1 3') or 'skip' to skip all.")
    return "\n".join(lines)


# --- Search query templates ---

SEARCH_QUERIES = {
    "anthropic": [
        "Anthropic revenue annualized 2026",
        "Anthropic ARR run rate",
        "Anthropic Claude Code revenue",
    ],
    "openai": [
        "OpenAI revenue annualized 2026",
        "OpenAI ARR run rate ChatGPT",
        "OpenAI annualized revenue monthly",
    ],
}


def get_search_queries(company: str) -> list[str]:
    return SEARCH_QUERIES.get(company, [])


def generate_review_prompt() -> str:
    """Generate the prompt for Claude Code's weekly scheduled task."""
    return """Run the weekly AI Revenue Monitor update:

1. For each company (anthropic, openai):
   a. Use Exa web search to find recent revenue news (last 7 days)
   b. Search queries: """ + str(SEARCH_QUERIES) + """
   c. Compare results with existing data in ~/ai-revenue-monitor/data/
   d. If new data points found, present them for user review
   e. After confirmation, add to the respective revenue JSON file

2. After data update, regenerate dashboard data:
   cd ~/ai-revenue-monitor && python scripts/generate_dashboard.py

3. Generate weekly report:
   cd ~/ai-revenue-monitor && python scripts/generate_report.py

4. Check for alerts (growth deceleration, inflection, new disclosure)

5. Send push notification with summary"""

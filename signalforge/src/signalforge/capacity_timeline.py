"""Comparable project milestones; synchronization/trial completion never imply COD."""
from datetime import date
from decimal import Decimal


def compare_project(expected, actual):
    required = ("project", "unit", "capacity_mw", "milestone", "date", "source_id")
    for event in (expected, actual):
        if any(event.get(k) is None for k in required):
            raise ValueError("Project, unit, capacity, milestone, date and source required")
        date.fromisoformat(event["date"])
        if not Decimal(str(event["capacity_mw"])).is_finite() or Decimal(str(event["capacity_mw"])) <= 0:
            raise ValueError("Capacity must be a positive finite MW value")
    compatible = all(str(expected[k]).casefold() == str(actual[k]).casefold()
                     for k in ("project", "unit", "milestone"))
    compatible = compatible and Decimal(str(expected["capacity_mw"])) == Decimal(str(actual["capacity_mw"]))
    if not compatible:
        return {"status": "not_comparable", "reason": "Project/unit/capacity or milestone differs; no slippage inferred", "slippage_days": None}
    days = (date.fromisoformat(actual["date"]) - date.fromisoformat(expected["date"])).days
    return {"status": "computed", "slippage_days": days,
            "capacity_mw": str(Decimal(str(actual["capacity_mw"]))),
            "formula": "actual matched milestone date - expected matched milestone date",
            "source_ids": [expected["source_id"], actual["source_id"]],
            "limitation": "Schedule revisions must be checked separately; this difference is not a revenue or penalty estimate."}


def exact_share(numerator, denominator):
    n, d = Decimal(str(numerator)), Decimal(str(denominator))
    if not n.is_finite() or not d.is_finite() or n < 0 or d <= 0 or n > d:
        raise ValueError("Require comparable 0 <= numerator <= positive denominator")
    return {"numerator": str(n), "denominator": str(d), "percent_exact": str(n / d * 100),
            "percent_display": f"{n / d * 100:.2f}", "formula": "numerator / denominator * 100"}

"""A separate, explicitly synthetic exposure demonstration.

Garwood intervals assume a Poisson event count with known exposure. Repeat-event
dependence, incomplete capture or changing populations can violate that model.
"""

from datetime import date
from math import isfinite

from scipy.stats import chi2


def poisson_rate(events, exposure, scale=1000.0, confidence=0.95):
    if isinstance(events, bool) or not isinstance(events, int) or events < 0:
        raise ValueError("events must be a nonnegative integer")
    if not 0 < confidence < 1 or not isfinite(scale) or scale <= 0:
        raise ValueError("invalid interval or rate scale")
    if exposure is None:
        return {"rate": None, "lower": None, "upper": None, "status": "missing exposure"}
    if (
        isinstance(exposure, bool)
        or not isinstance(exposure, (int, float))
        or not isfinite(exposure)
        or exposure < 0
    ):
        raise ValueError("exposure must be finite and nonnegative")
    if exposure == 0:
        if events:
            raise ValueError("events with zero exposure require reconciliation")
        return {"rate": None, "lower": None, "upper": None, "status": "zero exposure"}
    alpha = 1 - confidence
    lower_count = 0 if events == 0 else chi2.ppf(alpha / 2, 2 * events) / 2
    upper_count = chi2.ppf(1 - alpha / 2, 2 * (events + 1)) / 2
    return {
        "rate": events / exposure * scale,
        "lower": round(float(lower_count / exposure * scale), 9),
        "upper": round(float(upper_count / exposure * scale), 9),
        "status": "synthetic exposure demonstration",
    }


def rate_review(rows, baseline_months=6):
    """Compare later months to a predeclared baseline; never fit on later events."""
    ordered = sorted(rows, key=lambda row: row["month"])
    if len({r["month"] for r in ordered}) != len(ordered):
        raise ValueError("duplicate month: aggregate at one declared fleet/system grain first")
    months = [date.fromisoformat(row["month"] + "-01") for row in ordered]
    ordinals = [month.year * 12 + month.month for month in months]
    if any(right - left != 1 for left, right in zip(ordinals, ordinals[1:])):
        raise ValueError("missing month: provide an explicit row, never silently fill with zero")
    if not 1 <= baseline_months < len(ordered):
        raise ValueError("baseline must precede at least one review month")
    baseline = ordered[:baseline_months]
    if any(r["flight_hours"] is None or r["flight_hours"] <= 0 for r in baseline):
        raise ValueError("baseline requires complete positive exposure")
    for row in ordered:
        poisson_rate(row["removals"], row["flight_hours"])
    baseline_rate = (
        sum(r["removals"] for r in baseline) / sum(r["flight_hours"] for r in baseline) * 1000
    )
    output = []
    for i, row in enumerate(ordered):
        interval = poisson_rate(row["removals"], row["flight_hours"])
        # A screening flag only. Baseline uncertainty and repeated looks are not adjusted.
        flag = (
            "baseline"
            if i < baseline_months
            else "insufficient exposure"
            if interval["rate"] is None
            else "investigate"
            if interval["lower"] > baseline_rate
            else "monitor"
        )
        mtbur = (
            row["flight_hours"] / row["removals"]
            if row["flight_hours"] is not None and row["flight_hours"] > 0 and row["removals"] > 0
            else None
        )
        output.append(
            {
                **row,
                **interval,
                "screen": flag,
                "mtbur_hours": mtbur,
                "baseline_per_1000h": baseline_rate,
            }
        )
    return output

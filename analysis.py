"""Summaries across several simulation runs (shared by the GUI and sweep.py)."""

import statistics

from base import MODULE_TYPES, TECHS
from simulation import CAUSES


def self_sufficiency(result, days=365):
    """Share of food, water and oxygen needs met by local production over the last `days` alive.

    Returns {"food": 0-1, "water": 0-1, "o2": 0-1} (capped at 1).
    """
    se = result.series
    end = result.extinct_day if result.extinct_day is not None else len(result.sizes) - 1
    start = max(0, end - days)
    out = {}
    for name, made, need in (("food", "food_made", "food_need"), ("water", "water_in", "water_out"),
                             ("o2", "o2_made", "o2_need")):
        m = sum(se[made][start:end + 1])
        n = sum(se[need][start:end + 1])
        out[name] = min(1.0, m / n) if n > 0 else 1.0
    return out


def mars_born_share(result):
    return len(result.martians) / len(result.colony) if result.colony else 0.0


def summarize(results):
    """Headline numbers for a list of SimResult."""
    n = len(results)
    finals = [r.sizes[-1] for r in results]
    extinct = [r.extinct_day for r in results if r.extinct_day is not None]
    sufficiency = [self_sufficiency(r) for r in results]
    return {
        "runs": n,
        "survived": n - len(extinct),
        "extinction_probability": len(extinct) / n,
        "median_extinction_day": statistics.median(extinct) if extinct else None,
        "final_min": min(finals),
        "final_median": statistics.median(finals),
        "final_max": max(finals),
        "peak_median": statistics.median(max(r.sizes) for r in results),
        "mars_born_median": statistics.median(mars_born_share(r) for r in results),
        "modules_median": statistics.median(sum(r.final_modules.values()) for r in results),
        "techs_median": statistics.median(len(r.final_techs) for r in results),
        "techs_total": len(TECHS),
        "sufficiency": {k: statistics.median(s[k] for s in sufficiency) for k in ("food", "water", "o2")},
        "mean_deaths_by_cause": {c: sum(r.death_causes[c] for r in results) / n for c in CAUSES},
        "mean_disasters": sum(1 for r in results for _, k, _ in r.events
                              if k in ("storm", "epidemic", "failure", "breach", "cargo")) / n,
    }


def describe(summary):
    """One-line text version of summarize() for a status label."""
    text = "{survived}/{runs} colonies survived, final population {final_min:,}-{final_max:,}".format(**summary)
    causes = summary["mean_deaths_by_cause"]
    top = max(causes, key=causes.get)
    if causes[top] > 0:
        text += ", main killer: " + top
    return text


def module_counts(result, step=30):
    """Built modules of each type over time, sampled every `step` days: (days, {type: [counts]})."""
    days = list(range(0, len(result.sizes), step))
    built = sorted((e[1], e[3]) for e in result.timeline if e[0] == "module" and e[4] == "built")
    counts = {k: [] for k in MODULE_TYPES}
    running = {k: 0 for k in MODULE_TYPES}
    i = 0
    for d in days:
        while i < len(built) and built[i][0] <= d:
            running[built[i][1]] += 1
            i += 1
        for k in MODULE_TYPES:
            counts[k].append(running[k])
    return days, counts

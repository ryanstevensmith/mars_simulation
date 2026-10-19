"""Summaries across several simulation runs (shared by the GUI and sweep.py)."""

import statistics

from simulation import CAUSES


def summarize(results):
    """Headline numbers for a list of SimResult."""
    n = len(results)
    finals = [r.sizes[-1] for r in results]
    extinct = [r.extinct_day for r in results if r.extinct_day is not None]
    return {
        "runs": n,
        "extinct_runs": len(extinct),
        "extinction_probability": len(extinct) / n,
        "median_extinction_day": statistics.median(extinct) if extinct else None,
        "final_min": min(finals),
        "final_median": statistics.median(finals),
        "final_max": max(finals),
        "peak_median": statistics.median(max(r.sizes) for r in results),
        "mean_deaths_by_cause": {c: sum(r.death_causes[c] for r in results) / n for c in CAUSES},
        "mean_disasters": sum(len(r.events) for r in results) / n,
    }


def describe(summary):
    """One-line text version of summarize() for a status label."""
    text = "{runs} runs: final pop {final_min}-{final_max} (median {final_median:g}), extinct in {extinct_runs}/{runs}".format(**summary)
    causes = summary["mean_deaths_by_cause"]
    top = max(causes, key=causes.get)
    if causes[top] > 0:
        text += ", main killer: " + top
    return text

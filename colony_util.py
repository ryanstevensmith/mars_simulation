"""Probability tables and helpers shared by the simulation.

Both CSV files hold ANNUAL probabilities, one row per age: ``age,probability``.
Row 1 is used for ages 0 and 1; row N is used for age N; ages beyond the last
row use the last row (death_prob.csv ends with 1, so everyone dies at 100).

The simulation steps one day at a time, so annual probabilities are converted
to the equivalent per-day probability before they are compared with a random
number.
"""

import csv
from pathlib import Path

_DIR = Path(__file__).resolve().parent


def _load_table(name):
    with open(_DIR / name, newline='') as f:
        return [float(row[1]) for row in csv.reader(f) if row]


# Loaded once at import (these used to be re-read from disk on every lookup)
DEATH_ANNUAL = _load_table('death_prob.csv')
BIRTH_ANNUAL = _load_table('preg_prob.csv')


def table_index(age):
    """Index into a per-age table for the given age in whole years."""
    return max(0, min(age - 1, len(DEATH_ANNUAL) - 1))


def per_day(p, days):
    """Probability per day that gives probability p of happening over `days` days."""
    if p >= 1:
        return 1.0
    if p <= 0:
        return 0.0
    return 1 - (1 - p) ** (1 / days)


def death_hazards(scale=1.0):
    """Per-day death probability for each table index.

    `scale` multiplies the annual rates (use it to model a harsher or kinder
    environment). A probability of 1 (the cutoff age) is never scaled down.
    """
    return [per_day(p if p >= 1 else min(p * scale, 1.0), 365) for p in DEATH_ANNUAL]


def conception_hazards(window_days):
    """Per-day conception probability for each table index.

    The annual rate is spread across `window_days`, so a woman has the annual
    chance of conceiving once per conception window.
    """
    return [per_day(p, window_days) for p in BIRTH_ANNUAL]


def ratioCalculator(capacity, ratio):
    """Split a ship's capacity into (male, female) crew for a male:female ratio."""
    male_crew = int((ratio / (ratio + 1)) * capacity)
    female_crew = capacity - male_crew

    return male_crew, female_crew

# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 17:28:00 2019
@author: matej
"""

# The choices made before launch. Most of the colony's behaviour comes from the strategy and
# landing site (strategies.py) and the module stats (base.py); these are the remaining knobs.

from dataclasses import dataclass
from typing import Optional

import strategies


@dataclass
class SimParams:
    STRATEGY: object = "balanced"   # key in strategies.STRATEGIES (or a Strategy)
    SITE: object = "arcadia"        # key in strategies.SITES (or a Site)
    SIM_LENGTH: int = 365 * 30      # days simulated
    RUNS: int = 5                   # simulations to run and compare
    SEED: Optional[int] = None      # set for reproducible runs (run n uses SEED + n)

    # --- advanced ---
    COLONISTS_PER_SHIP: Optional[int] = None   # None = the strategy's number
    ARRIVAL_PERIOD: int = 780       # days between ships (Earth-Mars launch windows are ~26 months)
    DISASTER_SCALE: float = 1.0     # multiplies storm, epidemic, failure, breach and cargo-loss rates (0 = none)
    SUPPLY_SCALE: float = 1.0       # multiplies the food, water, oxygen and materials ships bring
    MORTALITY_SCALE: float = 1.0    # multiplier on the annual death rates in death_prob.csv

    # --- people ---
    CREW_RATIO: float = 1.0         # male : female ratio of each crew
    COOLDOWN: int = 365             # days after a birth before the mother can conceive again
    PREG_THRESH: int = 280          # days from conception to birth
    PREG_AGE_MIN: int = 20          # childbearing age range
    PREG_AGE_MAX: int = 40
    WORK_AGE_MIN: int = 16          # working age range (everyone else is a dependant)
    WORK_AGE_MAX: int = 65

    RECORD_TIMELINE: bool = True    # keep the event log the colony viewer replays (sweeps turn it off)

    @property
    def strategy(self):
        return strategies.get_strategy(self.STRATEGY)

    @property
    def site(self):
        return strategies.get_site(self.SITE)

    @property
    def colonists_per_ship(self):
        return self.strategy.colonists_per_ship if self.COLONISTS_PER_SHIP is None else self.COLONISTS_PER_SHIP

    def validate(self):
        """Raise ValueError with a readable message if the parameters make no sense."""
        try:
            self.strategy, self.site
        except KeyError as e:
            raise ValueError("Unknown strategy or site: " + str(e))
        if self.SIM_LENGTH < 1:
            raise ValueError("Sim length must be at least 1 day")
        if self.RUNS < 1:
            raise ValueError("Runs must be at least 1")
        if self.colonists_per_ship < 0:
            raise ValueError("Colonists per ship can't be negative")
        if self.ARRIVAL_PERIOD < 1:
            raise ValueError("Ship interval must be at least 1 day")
        if min(self.DISASTER_SCALE, self.SUPPLY_SCALE, self.MORTALITY_SCALE) < 0:
            raise ValueError("Disaster, supply and mortality scales can't be negative")
        if self.CREW_RATIO < 0 or self.COOLDOWN < 0:
            raise ValueError("Crew ratio and cooldown can't be negative")
        if self.PREG_THRESH < 1:
            raise ValueError("Gestation must be at least 1 day")
        if self.PREG_AGE_MIN > self.PREG_AGE_MAX or self.WORK_AGE_MIN > self.WORK_AGE_MAX:
            raise ValueError("Age ranges must have min <= max")

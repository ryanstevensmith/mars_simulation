# -*- coding: utf-8 -*-
"""
Created on Fri Mar 29 17:28:00 2019
@author: matej
"""

# Module storing all the constants used in the simulation
# This is the central place to tune the numbers to achieve the desired simulation behaviour

from dataclasses import dataclass
from typing import Optional


@dataclass
class SimParams:
    SIM_LENGTH: int = 365 * 30      # days the simulation runs for
    SHIP_CAPACITY: int = 80         # astronauts per ship
    ARRIVAL_PERIOD: int = 780       # days between ships (the first arrives on day 0)
    CREW_RATIO: float = 1.0         # male : female ratio of each crew
    COOLDOWN: int = 365             # days after a birth before the mother can conceive again
    MAX_PREG: int = 100             # maximum concurrent pregnancies allowed by the colony
    NEWGEN_PERIOD: int = 365        # days between conception windows (<= 0: always open)
    NEWGEN_WINDOW: int = 365        # days at the start of each period when conceptions can start
    PREG_THRESH: int = 280          # days from conception to birth
    DEATH_THRESH: int = 0           # age (years) from which natural death is checked
    PREG_AGE_MIN: int = 20          # minimum childbearing age
    PREG_AGE_MAX: int = 40          # maximum childbearing age
    MORTALITY_SCALE: float = 1.0    # multiplier on the annual death rates in death_prob.csv
    RUNS: int = 5                   # simulations to run and compare
    SEED: Optional[int] = None      # set for reproducible runs (run n uses SEED + n)

    # --- Food (units per day) ---
    # Each landed ship brings a farm that produces FOOD_PER_SHIP a day for the rest of the
    # sim, plus SHIP_FOOD_STOCK units of stored supplies. Everyone eats FOOD_PER_PERSON.
    FOOD_PER_PERSON: float = 1.0
    FOOD_PER_SHIP: float = 70.0
    SHIP_FOOD_STOCK: float = 2400.0
    FOOD_STORAGE_MAX: float = 20000.0
    STARVATION_DEATH_RATE: float = 0.005    # extra daily death chance at 100% food shortfall
    # --- Habitat / life support ---
    # Each landed ship adds HAB_PER_SHIP people of habitat and oxygen capacity.
    HAB_PER_SHIP: int = 120
    OVERCROWD_DEATH_RATE: float = 0.005     # extra daily death chance when 100% over capacity
    # --- Disasters (average events per year; 0 turns them off) ---
    DUST_STORMS_PER_YEAR: float = 0.5       # solar farms drop to DUST_STORM_POWER for 30-90 days
    DUST_STORM_POWER: float = 0.4
    BREACHES_PER_YEAR: float = 0.2          # kills 1..BREACH_MAX_DEATHS, habitat -25% for 30 days
    BREACH_MAX_DEATHS: int = 5
    EPIDEMICS_PER_YEAR: float = 0.1         # extra daily death chance for everyone for 20-60 days
    EPIDEMIC_DEATH_RATE: float = 0.002

    def validate(self):
        """Raise ValueError with a readable message if the parameters make no sense."""
        if self.SIM_LENGTH < 1:
            raise ValueError("Sim length must be at least 1 day")
        if self.SHIP_CAPACITY < 0:
            raise ValueError("Ship capacity can't be negative")
        if self.ARRIVAL_PERIOD < 1:
            raise ValueError("Arrival period must be at least 1 day")
        if self.CREW_RATIO < 0:
            raise ValueError("Crew ratio can't be negative")
        if self.COOLDOWN < 0 or self.MAX_PREG < 0 or self.DEATH_THRESH < 0:
            raise ValueError("Cooldown, max pregnancies and death threshold can't be negative")
        if self.PREG_THRESH < 1:
            raise ValueError("Preg threshold (gestation) must be at least 1 day")
        if self.NEWGEN_WINDOW < 1:
            raise ValueError("New gen window must be at least 1 day")
        if self.NEWGEN_PERIOD > 0 and self.NEWGEN_WINDOW > self.NEWGEN_PERIOD:
            raise ValueError("New gen window can't be longer than the new gen period")
        if self.PREG_AGE_MIN > self.PREG_AGE_MAX:
            raise ValueError("Repro min age can't be above repro max age")
        if self.MORTALITY_SCALE < 0:
            raise ValueError("Mortality scale can't be negative")
        if self.RUNS < 1:
            raise ValueError("Runs must be at least 1")
        if min(self.FOOD_PER_PERSON, self.FOOD_PER_SHIP, self.SHIP_FOOD_STOCK, self.FOOD_STORAGE_MAX,
               self.HAB_PER_SHIP, self.BREACH_MAX_DEATHS) < 0:
            raise ValueError("Food, habitat and breach amounts can't be negative")
        if min(self.DUST_STORMS_PER_YEAR, self.BREACHES_PER_YEAR, self.EPIDEMICS_PER_YEAR) < 0:
            raise ValueError("Disaster rates can't be negative")
        for name in ("STARVATION_DEATH_RATE", "OVERCROWD_DEATH_RATE", "EPIDEMIC_DEATH_RATE", "DUST_STORM_POWER"):
            if not 0 <= getattr(self, name) <= 1:
                raise ValueError(name + " must be between 0 and 1")

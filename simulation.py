# -*- coding: utf-8 -*-
"""
Created on Sun Mar 24 16:20:52 2019
@author: Ryan Smith
"""

import random
from dataclasses import dataclass, field
from typing import Optional

import colony_util as util
import colonists as col

CAUSES = ("natural", "starvation", "oxygen", "epidemic", "breach")
BREACH_REPAIR_DAYS = 30
BREACH_HAB_LOSS = 0.25


@dataclass
class SimResult:
    colony: list                                    # colonists alive at the end
    end_day: int                                    # day number to compute final ages from
    sizes: list = field(default_factory=list)       # population at the end of each day
    births: list = field(default_factory=list)      # births on each day
    deaths: list = field(default_factory=list)      # deaths on each day
    food_stock: list = field(default_factory=list)  # stored food at the end of each day
    food_satisfaction: list = field(default_factory=list)   # share of the day's food need met (0-1)
    habitat: list = field(default_factory=list)     # people the habitat can support each day
    death_causes: dict = field(default_factory=lambda: {c: 0 for c in CAUSES})
    events: list = field(default_factory=list)      # (day, kind, detail) for each disaster
    extinct_day: Optional[int] = None               # day the last colonist died, if it happened

    @property
    def martians(self):
        return [c for c in self.colony if c.getName() == "Martian"]


# TODO: move to colony_utils.py
def arrivalFromEarth(arrivalDate, params, rng):
    male_crew, female_crew = util.ratioCalculator(params.SHIP_CAPACITY, params.CREW_RATIO)

    crew = [col.Astronaut("m", arrivalDate, rng) for _ in range(male_crew)]
    crew += [col.Astronaut("f", arrivalDate, rng) for _ in range(female_crew)]

    return crew


def simulation(params, progress=None, seed=None):
    """Run one simulation and return a SimResult.

    progress, if given, is called as progress(days_done, total_days) about once a
    simulated month, so the model stays independent of any GUI.

    Each day: ships may land, disasters may start, food is eaten and grown, then every
    colonist faces death (natural causes plus any starvation / overcrowding / epidemic /
    breach risk) and women may conceive or give birth. If the colony dies out, it stays
    dead: no more ships come.
    """
    params.validate()
    rng = random.Random(seed)

    death_hz = util.death_hazards(params.MORTALITY_SCALE)
    windowed = params.NEWGEN_PERIOD > 0
    conception_hz = util.conception_hazards(params.NEWGEN_WINDOW if windowed else 365)

    colony = []
    result = SimResult(colony, params.SIM_LENGTH)
    pregnant_count = 0
    ships_landed = 0
    food_stock = 0.0
    storm_until = epidemic_until = breach_until = -1
    total_days = params.SIM_LENGTH
    extinct = False

    for day in range(total_days):
        if extinct:
            for series in (result.sizes, result.births, result.deaths, result.food_stock,
                           result.food_satisfaction, result.habitat):
                series.append(0)
            continue

        # --- arrivals ---
        if day % params.ARRIVAL_PERIOD == 0:
            colony += arrivalFromEarth(day, params, rng)
            ships_landed += 1
            food_stock = min(params.FOOD_STORAGE_MAX, food_stock + params.SHIP_FOOD_STOCK)

        # --- disasters ---
        victims = set()
        if rng.random() < params.DUST_STORMS_PER_YEAR / 365:
            length = rng.randint(30, 90)
            storm_until = max(storm_until, day + length)
            result.events.append((day, "dust storm", str(length) + " days"))
        if rng.random() < params.EPIDEMICS_PER_YEAR / 365:
            length = rng.randint(20, 60)
            epidemic_until = max(epidemic_until, day + length)
            result.events.append((day, "epidemic", str(length) + " days"))
        if rng.random() < params.BREACHES_PER_YEAR / 365:
            n = min(rng.randint(1, max(1, params.BREACH_MAX_DEATHS)), len(colony))
            if params.BREACH_MAX_DEATHS == 0:
                n = 0
            victims = set(id(x) for x in rng.sample(colony, n))
            breach_until = day + BREACH_REPAIR_DAYS
            result.events.append((day, "habitat breach", str(n) + " killed"))
        storm = day < storm_until
        epidemic = day < epidemic_until
        breach = day < breach_until

        # --- resources ---
        pop = len(colony)
        need = pop * params.FOOD_PER_PERSON
        available = food_stock + ships_landed * params.FOOD_PER_SHIP * (params.DUST_STORM_POWER if storm else 1.0)
        eaten = min(need, available)
        satisfaction = eaten / need if need > 0 else 1.0
        food_stock = min(params.FOOD_STORAGE_MAX, available - eaten)

        capacity = ships_landed * params.HAB_PER_SHIP * ((1 - BREACH_HAB_LOSS) if breach else 1.0)
        overcrowding = max(0.0, (pop - capacity) / pop) if pop > 0 else 0.0

        # extra daily death chances, by cause (all colonists share them)
        extra = {
            "starvation": params.STARVATION_DEATH_RATE * (1 - satisfaction),
            "oxygen": params.OVERCROWD_DEATH_RATE * overcrowding,
            "epidemic": params.EPIDEMIC_DEATH_RATE if epidemic else 0.0,
        }
        extra_total = 1 - (1 - extra["starvation"]) * (1 - extra["oxygen"]) * (1 - extra["epidemic"])

        # rationing and cramped conditions both suppress conceptions
        fertility = satisfaction * (min(1.0, capacity / pop) if pop > 0 else 1.0)

        conceiving_open = (not windowed) or (day % params.NEWGEN_PERIOD < params.NEWGEN_WINDOW)

        survivors = []
        newborns = []
        died = 0

        for x in colony:
            age = x.getAge(day)
            i = util.table_index(age)

            cause = None
            if id(x) in victims:
                cause = "breach"
            else:
                base = death_hz[i] if age >= params.DEATH_THRESH else 0.0
                p = base + extra_total - base * extra_total
                if p > 0 and rng.random() < p:
                    if extra_total == 0:
                        cause = "natural"
                    else:
                        cause = rng.choices(
                            ("natural", "starvation", "oxygen", "epidemic"),
                            weights=(base, extra["starvation"], extra["oxygen"], extra["epidemic"]))[0]

            if cause:
                died += 1
                result.death_causes[cause] += 1
                if x.isPregnant():
                    pregnant_count -= 1
                continue

            if x.getSex() == "f":
                if x.isPregnant():
                    x.incPregnant()
                    if x.pregnant_days >= params.PREG_THRESH:
                        x.birth(day, params.COOLDOWN)
                        pregnant_count -= 1
                        newborns.append(col.Martian(day, rng))
                elif (conceiving_open
                      and day >= x.cooldown_until
                      and params.PREG_AGE_MIN <= age <= params.PREG_AGE_MAX
                      and pregnant_count < params.MAX_PREG
                      and rng.random() < conception_hz[i] * fertility):
                    x.startPregnant()
                    pregnant_count += 1

            survivors.append(x)

        colony = survivors + newborns
        result.colony = colony
        result.sizes.append(len(colony))
        result.births.append(len(newborns))
        result.deaths.append(died)
        result.food_stock.append(food_stock)
        result.food_satisfaction.append(satisfaction)
        result.habitat.append(capacity)

        if not colony:
            extinct = True
            result.extinct_day = day

        if progress and (day % 30 == 0 or day == total_days - 1):
            progress(day + 1, total_days)

    return result

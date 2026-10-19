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
from base import Base, PLAN_EVERY

CAUSES = ("natural", "starvation", "dehydration", "suffocation", "epidemic", "accident")
SERIES = ("food", "water", "o2", "materials", "research", "power_supply", "power_demand",
          "food_made", "food_need", "o2_made", "o2_need", "water_in", "water_out",
          "food_sat", "water_sat", "o2_sat", "coverage", "beds", "crowding", "modules", "workers", "idle")
POP_MILESTONES = (100, 250, 500, 1000, 2000, 5000)


@dataclass
class SimResult:
    params: object
    colony: list                                    # colonists alive at the end
    end_day: int                                    # day number to compute final ages from
    sizes: list = field(default_factory=list)       # population at the end of each day
    births: list = field(default_factory=list)      # births on each day
    deaths: list = field(default_factory=list)      # deaths on each day
    death_causes: dict = field(default_factory=lambda: {c: 0 for c in CAUSES})
    events: list = field(default_factory=list)      # mission log: (day, kind, text)
    extinct_day: Optional[int] = None               # day the last colonist died, if it happened
    series: dict = field(default_factory=lambda: {k: [] for k in SERIES})   # daily base figures
    snapshots: list = field(default_factory=list)   # (day, per-module (condition, efficiency, progress))
    module_types: list = field(default_factory=list)  # module type by module id
    techs: list = field(default_factory=list)       # (day, tech key) in unlock order
    # Replay log for the colony viewer, in the order things happened:
    #   ("ship", day, ship_no) ("arrive", day, uid, sex, age) ("birth", day, uid, sex, mother_uid)
    #   ("conceive", day, uid) ("death", day, uid, cause) ("home"|"job", day, uid, module or -1)
    #   ("module", day, mid, type, "start"|"built") ("damage", day, mid, "failure"|"breach")
    #   ("storm"|"epidemic", day, end_day) ("tech", day, key)
    timeline: list = field(default_factory=list)

    @property
    def martians(self):
        return [c for c in self.colony if c.getName() == "Martian"]


def arrivalFromEarth(arrivalDate, params, rng):
    male_crew, female_crew = util.ratioCalculator(params.colonists_per_ship, params.CREW_RATIO)

    crew = [col.Astronaut("m", arrivalDate, rng) for _ in range(male_crew)]
    crew += [col.Astronaut("f", arrivalDate, rng) for _ in range(female_crew)]

    return crew


def run_one(args):
    """(params, seed) -> SimResult. Top-level so it can run in a process pool."""
    params, seed = args
    return simulation(params, seed=seed)


def simulation(params, progress=None, seed=None):
    """Run one simulation and return a SimResult.

    progress, if given, is called as progress(days_done, total_days) about once a
    simulated month, so the model stays independent of any GUI.
    """
    params.validate()
    rng = random.Random(seed)
    result = SimResult(params, [], params.SIM_LENGTH)
    log = result.timeline.append if params.RECORD_TIMELINE else (lambda e: None)

    def event(day, kind, text):
        result.events.append((day, kind, text))

    base = Base(params, rng, log, event)
    death_hz = util.death_hazards(params.MORTALITY_SCALE)
    conception_hz = util.conception_hazards(365)
    work_min = params.WORK_AGE_MIN

    colony = []
    pregnant_count = 0
    ship_no = 0
    next_uid = 0
    realloc = True
    extinct = False
    milestones = list(POP_MILESTONES)
    first_birth = first_adult = False
    sufficient_streak = 0
    total_days = params.SIM_LENGTH

    for day in range(total_days):
        if extinct:
            for series in (result.sizes, result.births, result.deaths, *result.series.values()):
                series.append(series[-1] if series is not result.sizes and series is not result.births
                              and series is not result.deaths and series else 0)
            continue

        # --- ships ---
        if day % params.ARRIVAL_PERIOD == 0:
            log(("ship", day, ship_no))
            base.receive_ship(day, ship_no)
            for x in arrivalFromEarth(day, params, rng):
                x.uid = next_uid
                next_uid += 1
                log(("arrive", day, x.uid, x.sex, x.getAge(day)))
                colony.append(x)
            ship_no += 1
            realloc = True

        # --- disasters ---
        victims = set()
        hit = base.disasters(day)
        if hit:
            hab, n = hit
            residents = [x for x in colony if x.home == hab.mid]
            victims = set(id(x) for x in rng.sample(residents, min(n, len(residents))))
            event(day, "breach", "Hull breach in {}: {} killed".format(hab.label, len(victims)))

        if realloc or day % PLAN_EVERY == 0:
            base.allocate(day, colony)
            realloc = False

        children = sum(1 for x in colony if x.getAge(day) < work_min)
        needs = base.produce(day, len(colony) - children, children)
        extra = needs["extra"]
        extra_total = 1.0
        for p in extra.values():
            extra_total *= 1 - p
        extra_total = 1 - extra_total
        natural_scale = needs["natural_scale"]
        fertility = needs["fertility"]

        survivors = []
        newborns = []
        died = 0

        for x in colony:
            age = x.getAge(day)
            i = util.table_index(age)

            cause = None
            if id(x) in victims:
                cause = "accident"
            else:
                base_p = 1.0 if death_hz[i] >= 1 else death_hz[i] * natural_scale
                p = base_p + extra_total - base_p * extra_total
                if p > 0 and rng.random() < p:
                    if extra_total == 0:
                        cause = "natural"
                    else:
                        cause = rng.choices(("natural",) + tuple(extra),
                                            weights=(base_p,) + tuple(extra.values()))[0]

            if cause:
                died += 1
                result.death_causes[cause] += 1
                log(("death", day, x.uid, cause))
                base.on_death(x)
                if x.isPregnant():
                    pregnant_count -= 1
                continue

            if x.getSex() == "f":
                if x.isPregnant():
                    x.incPregnant()
                    if x.pregnant_days >= params.PREG_THRESH:
                        x.birth(day, params.COOLDOWN)
                        pregnant_count -= 1
                        baby = col.Martian(day, rng)
                        baby.uid, baby.home = next_uid, x.home
                        next_uid += 1
                        newborns.append(baby)
                        log(("birth", day, baby.uid, baby.sex, x.uid))
                elif (day >= x.cooldown_until
                      and params.PREG_AGE_MIN <= age <= params.PREG_AGE_MAX
                      and rng.random() < conception_hz[i] * fertility):
                    x.startPregnant()
                    pregnant_count += 1
                    log(("conceive", day, x.uid))

            survivors.append(x)

        colony = survivors + newborns
        result.colony = colony

        # --- building ---
        if base.construct(day):
            realloc = True
        if day % PLAN_EVERY == 0:
            days_to_ship = params.ARRIVAL_PERIOD - day % params.ARRIVAL_PERIOD
            base.plan(day, len(colony), params.colonists_per_ship if days_to_ship < 300 else 0)

        # --- milestones ---
        if newborns and not first_birth:
            first_birth = True
            event(day, "milestone", "First child born on Mars")
        while milestones and len(colony) >= milestones[0]:
            event(day, "milestone", "Population passed {}".format(milestones.pop(0)))
        if not first_adult and day % 30 == 0 and any(x.getName() == "Martian" and x.getAge(day) >= 18 for x in colony):
            first_adult = True
            event(day, "milestone", "First Mars-born colonist comes of age")
        st = base.stats
        if (st["food_made"] >= st["food_need"] and st["o2_made"] >= st["o2_need"]
                and st["water_in"] >= st["water_out"]):
            sufficient_streak += 1
            if sufficient_streak == 365:
                event(day, "milestone", "A full year self-sufficient in food, water and oxygen")
        else:
            sufficient_streak = 0 if sufficient_streak < 365 else sufficient_streak

        # --- records ---
        result.sizes.append(len(colony))
        result.births.append(len(newborns))
        result.deaths.append(died)
        rec = result.series
        for k in ("food", "water", "o2", "materials"):
            rec[k].append(base.stock[k])
        rec["research"].append(base.research)
        for k in ("power_supply", "power_demand", "food_made", "food_need", "o2_made", "o2_need",
                  "water_in", "water_out", "food_sat", "water_sat", "o2_sat", "coverage", "beds", "crowding"):
            rec[k].append(st[k])
        rec["modules"].append(sum(1 for m in base.modules if m.built))
        rec["idle"].append(base.idle_workers)
        rec["workers"].append(sum(m.staff for m in base.modules))
        if day % PLAN_EVERY == 0 or len(base.modules) != len(result.module_types):
            result.module_types = [m.type for m in base.modules]
            result.snapshots.append((day, base.snapshot()))

        if not colony:
            extinct = True
            result.extinct_day = day
            event(day, "extinct", "The colony has died out")

        if progress and (day % 30 == 0 or day == total_days - 1):
            progress(day + 1, total_days)

    result.techs = [(e[1], e[2]) for e in result.timeline if e[0] == "tech"] if params.RECORD_TIMELINE else \
        [(None, t) for t in base.techs]
    result.module_types = [m.type for m in base.modules]
    result.final_modules = {k: sum(1 for m in base.modules if m.type == k and m.built) for k in base.counts}
    result.final_techs = sorted(base.techs)
    return result

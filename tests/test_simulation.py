import dataclasses
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import base as b
import colonists as col
import colony_util as util
import colonysim_params as ps
import simulation as sim
import strategies


def strategy(**changes):
    """The balanced strategy with some fields changed."""
    return dataclasses.replace(strategies.STRATEGIES["balanced"], key="test", **changes)


def run(seed=1, **overrides):
    overrides.setdefault("DISASTER_SCALE", 0)
    return sim.simulation(ps.SimParams(**overrides), seed=seed)


def make_base(strat=None, **overrides):
    params = ps.SimParams(STRATEGY=strat or strategy(), DISASTER_SCALE=0, **overrides)
    events = []
    base = b.Base(params, random.Random(1), lambda e: None, lambda d, k, t: events.append((d, k, t)))
    return base, events


def adults(n, day=0, sex="f"):
    rng = random.Random(2)
    people = [col.Astronaut(sex, day, rng) for _ in range(n)]
    for i, x in enumerate(people):
        x.uid = i
    return people


class TestUtil(unittest.TestCase):

    def test_age_index_is_clamped(self):
        self.assertEqual(util.table_index(0), 0)        # newborns must not wrap to the last row
        self.assertEqual(util.table_index(100), 99)
        self.assertEqual(util.table_index(150), 99)

    def test_everyone_dies_at_cutoff_age(self):
        self.assertEqual(util.death_hazards(0.0)[util.table_index(100)], 1.0)

    def test_per_day_conversion_compounds_back_to_annual(self):
        self.assertAlmostEqual(1 - (1 - util.per_day(0.1, 365)) ** 365, 0.1)


class TestStrategies(unittest.TestCase):

    def test_every_strategy_site_and_difficulty_runs(self):
        for s in strategies.STRATEGIES:
            for site in strategies.SITES:
                r = sim.simulation(ps.SimParams(STRATEGY=s, SITE=site, SIM_LENGTH=200), seed=1)
                self.assertGreater(r.sizes[-1], 0, (s, site))
        for d in strategies.DIFFICULTIES.values():
            sim.simulation(ps.SimParams(DISASTER_SCALE=d.disasters, SUPPLY_SCALE=d.supplies, SIM_LENGTH=200), seed=1)

    def test_starter_base_is_landed_on_day_zero(self):
        for s in strategies.STRATEGIES.values():
            r = sim.simulation(ps.SimParams(STRATEGY=s.key, SIM_LENGTH=1, DISASTER_SCALE=0), seed=1)
            self.assertEqual(r.series["modules"][0], sum(s.starter_modules.values()), s.key)

    def test_colonists_per_ship_override(self):
        r = run(SIM_LENGTH=1, COLONISTS_PER_SHIP=7)
        self.assertEqual(r.sizes[0], 7)


class TestSimulation(unittest.TestCase):

    def test_same_seed_is_reproducible(self):
        self.assertEqual(run(seed=7, SIM_LENGTH=400, DISASTER_SCALE=1).sizes,
                         run(seed=7, SIM_LENGTH=400, DISASTER_SCALE=1).sizes)

    def test_population_accounting_balances(self):
        r = run(SIM_LENGTH=1600, DISASTER_SCALE=2)
        arrived = 60 * (1 + 1599 // 780)
        self.assertEqual(len(r.colony), arrived + sum(r.births) - sum(r.deaths))
        self.assertEqual(sum(r.death_causes.values()), sum(r.deaths))

    def test_births_wait_for_gestation(self):
        r = run(SIM_LENGTH=600)
        first = next(d for d, n in enumerate(r.births) if n)
        self.assertGreaterEqual(first, ps.SimParams().PREG_THRESH)

    def test_no_life_support_means_suffocation_and_extinction_is_final(self):
        s = strategy(starter_modules={"hab": 3, "solar": 2}, ship_modules={}, ship_materials=0)
        r = run(STRATEGY=s, SIM_LENGTH=1000)
        self.assertGreater(r.death_causes["suffocation"], 0)
        self.assertIsNotNone(r.extinct_day)
        self.assertEqual(r.sizes[r.extinct_day:], [0] * (1000 - r.extinct_day))   # no ship at day 780
        self.assertTrue(any(k == "extinct" for _, k, _ in r.events))

    def test_bad_params_are_rejected(self):
        with self.assertRaises(ValueError):
            ps.SimParams(PREG_AGE_MIN=50, PREG_AGE_MAX=20).validate()
        with self.assertRaises(ValueError):
            ps.SimParams(STRATEGY="nonsense").validate()

    def test_series_cover_every_day(self):
        r = run(SIM_LENGTH=300)
        for name, values in r.series.items():
            self.assertEqual(len(values), 300, name)


class TestBase(unittest.TestCase):

    def test_power_goes_to_life_support_first(self):
        base, _ = make_base(strategy(starter_modules={"lss": 1, "greenhouse": 3, "solar": 1}))
        base.receive_ship(0, 0)
        people = adults(30)
        base.allocate(0, people)
        base.produce(0, 30, 0)
        power = base.stats["power"]
        self.assertEqual(power["lss"], 1.0)
        self.assertLess(power["greenhouse"], 1.0)

    def test_people_drink_before_electrolysis_before_crops(self):
        base, _ = make_base(strategy(starter_modules={"lss": 1, "greenhouse": 2, "solar": 4}))
        base.receive_ship(0, 0)
        base.stock["water"] = 12 * 10 + 28 * 0.5      # enough for drinking and half the electrolysis
        people = adults(10)
        base.allocate(0, people)
        needs = base.produce(0, 10, 0)
        self.assertEqual(needs["extra"]["dehydration"], 0.0)
        self.assertEqual(base.stats["food_made"], 0.0)         # crops got nothing
        self.assertGreater(base.stats["o2_made"], 0.0)

    def test_jobs_follow_priority_and_children_do_not_work(self):
        base, _ = make_base(strategy(starter_modules={"lss": 1, "greenhouse": 2, "lab": 1, "hab": 1}))
        base.receive_ship(0, 0)
        people = adults(5)
        kid = col.Martian(0, random.Random(1))
        kid.uid = 99
        base.allocate(0, people + [kid])
        staff = {m.type: m.staff for m in base.modules}
        self.assertEqual(staff["lss"], 1)
        self.assertEqual(sum(m.staff for m in base.modules if m.type == "greenhouse"), 4)
        self.assertEqual(staff["lab"], 0)                        # ran out of people
        self.assertEqual(kid.job, -1)

    def test_homes_spread_across_habitats(self):
        base, _ = make_base(strategy(starter_modules={"hab": 3}))
        base.receive_ship(0, 0)
        people = adults(50)
        base.allocate(0, people)
        sizes = sorted(sum(1 for x in people if x.home == m.mid) for m in base.modules)
        self.assertEqual(sum(sizes), 50)
        self.assertLessEqual(max(sizes), b.BEDS_PER_HAB)

    def test_planner_builds_life_support_when_oxygen_is_short(self):
        base, events = make_base(strategy(starter_modules={"hab": 3, "greenhouse": 4, "recycler": 1, "ice_mine": 1,
                                                           "solar": 6, "workshop": 1}, build_weights={}))
        base.receive_ship(0, 0)
        base.stock.update(materials=500, o2=100)       # water and food are fine, oxygen is about to run out
        people = adults(60)
        base.allocate(0, people)
        base.produce(0, 60, 0)
        base.plan(0, 60, 0)
        self.assertEqual(base.under_construction[0].type, "lss")

    def test_construction_needs_workers(self):
        base, _ = make_base(strategy(starter_modules={"hab": 1}))
        base.receive_ship(0, 0)
        m = base.add_module(0, "solar", built=False)
        base.idle_workers = b.BUILD_CREW
        for day in range(m.build_days - 1):
            base.construct(day)
        self.assertFalse(m.built)
        base.construct(m.build_days)
        self.assertTrue(m.built)
        slow = base.add_module(0, "solar", built=False)
        base.idle_workers = 0
        for day in range(slow.build_days):
            base.construct(day)
        self.assertFalse(slow.built)                             # quarter speed with nobody free

    def test_modules_wear_out_without_materials(self):
        base, _ = make_base(strategy(starter_modules={"solar": 2}, ship_materials=0))
        base.receive_ship(0, 0)
        for day in range(300):
            base.produce(day, 0, 0)
        self.assertLess(base.modules[0].condition, 0.8)
        base.stock["materials"] = 1000
        for day in range(300, 400):
            base.produce(day, 0, 0)
        self.assertEqual(base.modules[0].condition, 1.0)

    def test_research_unlocks_techs_in_strategy_order(self):
        base, events = make_base(strategy(starter_modules={"lab": 1, "solar": 1}, tech_order=("water2",)))
        base.receive_ship(0, 0)
        base.research = b.TECHS["water2"][1]
        base.produce(1, 0, 0)
        self.assertIn("water2", base.techs)
        self.assertTrue(any(k == "tech" for _, k, _ in events))

    def test_cargo_can_be_lost(self):
        base, events = make_base()
        base.params.DISASTER_SCALE = 40                  # loss chance caps at 50%
        lost = [base.receive_ship(780 * n, n) for n in range(1, 40)]
        self.assertTrue(any(lost) and not all(lost))
        self.assertTrue(any(k == "cargo" for _, k, _ in events))

    def test_disasters_happen_and_breaches_kill(self):
        runs = [sim.simulation(ps.SimParams(DISASTER_SCALE=8, SIM_LENGTH=500), seed=n) for n in range(4)]
        kinds = {k for r in runs for _, k, _ in r.events}
        self.assertTrue({"storm", "failure", "epidemic", "breach"} <= kinds, kinds)
        self.assertGreater(sum(r.death_causes["accident"] for r in runs), 0)
        # a breach in a habitat returns how many residents it kills
        s = strategy(starter_modules={"hab": 2, "lss": 2, "greenhouse": 4, "recycler": 1, "ice_mine": 1,
                                      "solar": 6}, ship_modules={})
        base, _ = make_base(s)
        base.receive_ship(0, 0)
        base.params.DISASTER_SCALE = 3000
        hab_hits = [hit for hit in (base.disasters(d) for d in range(200)) if hit]
        self.assertTrue(hab_hits)
        self.assertTrue(all(m.type == "hab" and 1 <= n <= 4 for m, n in hab_hits))


class TestAnalysis(unittest.TestCase):

    def test_summary_and_self_sufficiency(self):
        import analysis
        results = [run(seed=n, SIM_LENGTH=800) for n in range(2)]
        s = analysis.summarize(results)
        self.assertEqual(s["runs"], 2)
        self.assertEqual(s["survived"], 2)
        for v in s["sufficiency"].values():
            self.assertTrue(0 <= v <= 1)
        self.assertIn("colonies survived", analysis.describe(s))
        days, counts = analysis.module_counts(results[0])
        self.assertEqual(sum(c[-1] for c in counts.values()), results[0].series["modules"][days[-1]])


if __name__ == "__main__":
    unittest.main()

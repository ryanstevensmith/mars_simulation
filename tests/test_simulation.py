import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import colony_util as util
import colonysim_params as ps
import simulation as sim


# Switches off scarcity and disasters so a test only sees the behaviour it is about
QUIET = dict(FOOD_PER_SHIP=10000, HAB_PER_SHIP=100000, DUST_STORMS_PER_YEAR=0,
             BREACHES_PER_YEAR=0, EPIDEMICS_PER_YEAR=0)


def run(seed=1, **overrides):
    return sim.simulation(ps.SimParams(**{**QUIET, **overrides}), seed=seed)


class TestUtil(unittest.TestCase):

    def test_age_index_is_clamped(self):
        self.assertEqual(util.table_index(0), 0)        # newborns must not wrap to the last row
        self.assertEqual(util.table_index(1), 0)
        self.assertEqual(util.table_index(100), 99)
        self.assertEqual(util.table_index(150), 99)

    def test_newborns_do_not_die_instantly(self):
        self.assertLess(util.death_hazards()[util.table_index(0)], 0.001)

    def test_everyone_dies_at_cutoff_age(self):
        self.assertEqual(util.death_hazards(0.0)[util.table_index(100)], 1.0)

    def test_per_day_conversion_compounds_back_to_annual(self):
        daily = util.per_day(0.1, 365)
        self.assertAlmostEqual(1 - (1 - daily) ** 365, 0.1)

    def test_ratio_calculator(self):
        self.assertEqual(util.ratioCalculator(80, 1.0), (40, 40))


class TestSimulation(unittest.TestCase):

    def test_no_deaths_no_births_keeps_crew_constant(self):
        r = run(MORTALITY_SCALE=0, MAX_PREG=0, SIM_LENGTH=800, ARRIVAL_PERIOD=780)
        self.assertEqual(r.sizes[0], 80)
        self.assertEqual(r.sizes[779], 80)
        self.assertEqual(r.sizes[780], 160)             # second ship arrives
        self.assertEqual(sum(r.births), 0)
        self.assertEqual(sum(r.deaths), 0)

    def test_same_seed_is_reproducible(self):
        self.assertEqual(run(seed=7, SIM_LENGTH=500).sizes, run(seed=7, SIM_LENGTH=500).sizes)

    def test_population_accounting_balances(self):
        r = run(MORTALITY_SCALE=50, SIM_LENGTH=1000)
        arrived = 80 * (1 + 999 // 780)
        self.assertEqual(len(r.colony), arrived + sum(r.births) - sum(r.deaths))

    def test_births_wait_for_gestation_and_conception_window(self):
        r = run(MORTALITY_SCALE=0, NEWGEN_PERIOD=1000, NEWGEN_WINDOW=10,
                PREG_THRESH=280, SIM_LENGTH=500)
        birth_days = [d for d, n in enumerate(r.births) if n]
        self.assertTrue(birth_days)
        self.assertTrue(all(280 <= d <= 289 for d in birth_days), birth_days)

    def test_max_preg_zero_blocks_births(self):
        self.assertEqual(sum(run(MAX_PREG=0, SIM_LENGTH=1000).births), 0)

    def test_cooldown_spaces_births_for_each_mother(self):
        # a mother can't give birth twice within gestation + cooldown
        r = run(MORTALITY_SCALE=0, SIM_LENGTH=2000, COOLDOWN=1000, ARRIVAL_PERIOD=5000)
        mothers_at_end = [c for c in r.colony if c.getName() == "Astronaut" and c.cooldown_until]
        for c in mothers_at_end:
            self.assertGreaterEqual(c.cooldown_until, 280 + 1000)

    def test_newborns_survive_when_mortality_is_off(self):
        r = run(MORTALITY_SCALE=0, SIM_LENGTH=1500)
        self.assertEqual(len(r.martians), sum(r.births))

    def test_bad_params_are_rejected(self):
        with self.assertRaises(ValueError):
            ps.SimParams(PREG_AGE_MIN=50, PREG_AGE_MAX=20).validate()
        with self.assertRaises(ValueError):
            ps.SimParams(NEWGEN_PERIOD=30, NEWGEN_WINDOW=90).validate()


class TestResourcesAndDisasters(unittest.TestCase):

    def test_food_shortfall_causes_starvation_deaths(self):
        r = run(MORTALITY_SCALE=0, FOOD_PER_SHIP=0, SHIP_FOOD_STOCK=800, SIM_LENGTH=300)
        self.assertGreater(r.death_causes["starvation"], 0)
        self.assertEqual(r.death_causes["natural"], 0)
        self.assertLess(min(r.food_satisfaction), 1.0)

    def test_enough_food_means_no_starvation(self):
        r = run(MORTALITY_SCALE=0, SIM_LENGTH=500)
        self.assertEqual(r.death_causes["starvation"], 0)
        self.assertEqual(min(r.food_satisfaction), 1.0)

    def test_overcrowding_causes_oxygen_deaths(self):
        r = run(MORTALITY_SCALE=0, HAB_PER_SHIP=20, SIM_LENGTH=200)
        self.assertGreater(r.death_causes["oxygen"], 0)

    def test_hunger_suppresses_births(self):
        fed = sum(run(MORTALITY_SCALE=0, SIM_LENGTH=1200, STARVATION_DEATH_RATE=0).births)
        hungry = sum(run(MORTALITY_SCALE=0, SIM_LENGTH=1200, STARVATION_DEATH_RATE=0,
                         FOOD_PER_SHIP=30, SHIP_FOOD_STOCK=0).births)
        self.assertGreater(fed, hungry)

    def test_disasters_are_logged_and_breaches_kill(self):
        r = run(MORTALITY_SCALE=0, BREACHES_PER_YEAR=20, DUST_STORMS_PER_YEAR=20,
                EPIDEMICS_PER_YEAR=20, SIM_LENGTH=365)
        kinds = {kind for _, kind, _ in r.events}
        self.assertEqual(kinds, {"dust storm", "epidemic", "habitat breach"})
        self.assertGreater(r.death_causes["breach"], 0)

    def test_dust_storm_cuts_food_production(self):
        calm = run(MORTALITY_SCALE=0, FOOD_PER_SHIP=80, SHIP_FOOD_STOCK=0, SIM_LENGTH=100)
        stormy = run(MORTALITY_SCALE=0, FOOD_PER_SHIP=80, SHIP_FOOD_STOCK=0, SIM_LENGTH=100,
                     DUST_STORMS_PER_YEAR=1000, DUST_STORM_POWER=0.1)
        self.assertLess(sum(stormy.food_satisfaction), sum(calm.food_satisfaction))

    def test_deaths_by_cause_add_up(self):
        r = sim.simulation(ps.SimParams(SIM_LENGTH=1500, BREACHES_PER_YEAR=2, EPIDEMICS_PER_YEAR=2), seed=3)
        self.assertEqual(sum(r.death_causes.values()), sum(r.deaths))

    def test_extinction_is_final(self):
        r = run(MORTALITY_SCALE=0, FOOD_PER_SHIP=0, SHIP_FOOD_STOCK=0, STARVATION_DEATH_RATE=1,
                SIM_LENGTH=2000)
        self.assertIsNotNone(r.extinct_day)
        self.assertEqual(r.sizes[r.extinct_day:], [0] * (2000 - r.extinct_day))   # no ship lands at day 780
        self.assertEqual(len(r.sizes), 2000)


if __name__ == "__main__":
    unittest.main()

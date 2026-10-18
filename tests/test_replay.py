import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import colonysim_params as ps
import colony_replay as rp
import simulation as sim


def make(seed=2, **overrides):
    params = ps.SimParams(**{"SIM_LENGTH": 1800, "BREACHES_PER_YEAR": 3, "EPIDEMICS_PER_YEAR": 2,
                             "DUST_STORMS_PER_YEAR": 2, **overrides})
    result = sim.simulation(params, seed=seed)
    return result, rp.ReplayState(result, params)


class TestReplay(unittest.TestCase):

    def test_dots_match_population_at_every_sampled_day(self):
        result, state = make()
        for day in (0, 1, 100, 779, 780, 781, 1200, 1799):
            state.seek(day)
            self.assertEqual(len(state.dots), result.sizes[day], day)

    def test_playing_forward_matches_seeking(self):
        result, state = make()
        while not state.finished:
            state.advance(0.05, 40)                      # 2 days per step
            self.assertEqual(len(state.dots), result.sizes[state.day_index])

    def test_seeking_backwards_works(self):
        result, state = make()
        state.seek(1500)
        state.seek(300)
        self.assertEqual(len(state.dots), result.sizes[300])

    def test_counts_split_astronauts_and_martians(self):
        result, state = make(MORTALITY_SCALE=0, STARVATION_DEATH_RATE=0, BREACHES_PER_YEAR=0,
                             EPIDEMICS_PER_YEAR=0, FOOD_PER_SHIP=10000)
        state.seek(1799)
        astronauts, martians = state.counts()
        self.assertEqual(astronauts, 80 * 3)
        self.assertEqual(martians, len(result.martians))

    def test_dots_stay_inside_the_world_and_near_modules(self):
        _, state = make()
        for _ in range(200):
            state.advance(0.05, 20)
        reach = state.spacing * math.sqrt(state.modules + 1) + 3 * state.module_radius
        for d in state.dots.values():
            self.assertLess(math.hypot(d.x - rp.CENTER[0], d.y - rp.CENTER[1]), reach + 50)

    def test_ships_and_deaths_create_effects(self):
        _, state = make()
        kinds = set()
        while not state.finished:
            state.advance(0.05, 30)
            kinds |= {e.kind for e in state.effects}
        self.assertTrue({"ship", "ghost"} <= kinds, kinds)

    def test_modules_grow_with_each_ship(self):
        _, state = make()
        state.seek(0)
        self.assertEqual(state.modules, 1)
        state.seek(1799)
        self.assertEqual(state.modules, 3)

    def test_timeline_can_be_switched_off(self):
        result = sim.simulation(ps.SimParams(SIM_LENGTH=100, RECORD_TIMELINE=False), seed=1)
        self.assertEqual(result.timeline, [])


if __name__ == "__main__":
    unittest.main()

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import colonysim_params as ps
import colony_replay as rp
import simulation as sim

_cache = {}


def make(seed=2, **overrides):
    key = (seed, tuple(sorted(overrides.items())))
    if key not in _cache:
        params = ps.SimParams(**{"SIM_LENGTH": 1800, "DISASTER_SCALE": 3, **overrides})
        _cache[key] = sim.simulation(params, seed=seed)
    result = _cache[key]
    return result, rp.ReplayState(result)


class TestReplay(unittest.TestCase):

    def test_dots_match_population_at_every_sampled_day(self):
        result, state = make()
        for day in (0, 1, 100, 779, 780, 781, 1200, 1799):
            state.seek(day)
            self.assertEqual(len(state.dots), result.sizes[day], day)

    def test_playing_forward_matches_seeking(self):
        result, state = make()
        while not state.finished:
            state.advance(0.05, 60)                      # 3 days per step
            self.assertEqual(len(state.dots), result.sizes[state.day_index])

    def test_seeking_backwards_works(self):
        result, state = make()
        state.seek(1500)
        state.seek(300)
        self.assertEqual(len(state.dots), result.sizes[300])

    def test_built_modules_match_the_model(self):
        result, state = make()
        for day in (0, 400, 800, 1799):
            state.seek(day)
            built = sum(1 for s in state.modules.values() if s == "built")
            self.assertEqual(built, result.series["modules"][day], day)

    def test_everyone_has_a_home_and_jobs_are_real_modules(self):
        result, state = make()
        state.seek(1000)
        for d in state.dots.values():
            self.assertIn(d.home, state.modules)
            self.assertEqual(state.module_types[d.home], "hab")
            if d.job != -1:
                self.assertIn(d.job, state.modules)

    def test_layout_has_no_overlapping_modules(self):
        result, state = make(STRATEGY="frontier", SIM_LENGTH=3000)
        slots = list(state.layout.slots.values())
        self.assertEqual(len(slots), len(state.module_types))
        seen = set()
        for s in slots:
            key = (round(s.x), round(s.y))
            self.assertNotIn(key, seen)
            seen.add(key)

    def test_effects_and_toasts_appear(self):
        _, state = make()
        kinds, toasts = set(), set()
        while not state.finished:
            state.advance(0.05, 40)
            kinds |= {e.kind for e in state.effects}
            toasts |= {t[1] for t in state.toasts}
        self.assertTrue({"ship", "built"} <= kinds, kinds)
        self.assertIn("built", toasts)

    def test_timeline_can_be_switched_off(self):
        result = sim.simulation(ps.SimParams(SIM_LENGTH=100, RECORD_TIMELINE=False), seed=1)
        self.assertEqual(result.timeline, [])


if __name__ == "__main__":
    unittest.main()

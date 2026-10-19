"""Replays a recorded simulation as moving dots. No GUI code: colony_view.py draws this state.

A ReplayState walks the SimResult.timeline in step with a simulated-day clock. Positions
and movement are purely cosmetic (the model itself has no space), but the population always
matches the model: after seek(d), the number of dots equals result.sizes[d].
"""

import math
import random

W, H = 1000.0, 600.0            # world size; the view scales it to the window
CENTER = (W / 2, H / 2 - 10)
LAND_TIME = 1.6                 # real seconds a ship takes to come down
MAX_EFFECTS = 500

DOT_SPEED = (18.0, 40.0)        # world units per real second
PAUSE_TIME = (0.2, 2.5)         # real seconds a dot idles at each stop


class Dot:
    __slots__ = ("uid", "x", "y", "tx", "ty", "speed", "pause", "home", "sex",
                 "birth_day", "martian", "pregnant", "appear")


class Effect:
    """A short-lived visual: kind is 'ship', 'ghost', 'birth' or 'breach'."""
    __slots__ = ("kind", "x", "y", "t", "dur", "data")

    def __init__(self, kind, x, y, dur, data=None):
        self.kind, self.x, self.y, self.t, self.dur, self.data = kind, x, y, 0.0, dur, data


class ReplayState:

    def __init__(self, result, params, seed=0):
        self.result = result
        self.timeline = result.timeline
        self.total_days = len(result.sizes)
        self.max_ships = max(1, math.ceil(params.SIM_LENGTH / params.ARRIVAL_PERIOD))
        # shrink the modules as more ships are expected so the finished colony fits the world
        self.spacing = max(14.0, min(110.0, 310.0 / math.sqrt(self.max_ships)))
        self.module_radius = 0.44 * self.spacing
        self.seed = seed
        self.reset()

    # ---------- layout ----------

    def module_pos(self, k):
        """Habitat k sits on a golden-angle spiral, so the colony grows outwards organically."""
        r = self.spacing * math.sqrt(k + 0.4)
        a = k * 2.399963
        return CENTER[0] + r * math.cos(a), CENTER[1] + 0.8 * r * math.sin(a)

    def farm_pos(self, k):
        x, y = self.module_pos(k)
        return x + self.module_radius * 1.05, y - self.module_radius * 0.95

    def target_zoom(self):
        """Camera zoom that frames the habitats built so far (the view eases towards it)."""
        extent = self.spacing * math.sqrt(max(0, self.modules - 1) + 0.4) + 2.6 * self.module_radius
        return max(0.5, min(3.0, (H / 2 - 40) / extent))

    @property
    def farm_radius(self):
        return self.module_radius * 0.42

    def _point_in(self, cx, cy, radius):
        a = self.rng.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(self.rng.random())
        return cx + r * math.cos(a), cy + r * math.sin(a)

    # ---------- control ----------

    def reset(self, animate=True):
        self.rng = random.Random(self.seed)
        self.day = 0.0
        self.clock = 0.0                # real seconds, drives animations
        self.modules = 0                # habitats built so far
        self.dots = {}
        self.effects = []
        self.storm_until = self.epidemic_until = -1
        self.epidemic_start = -1
        self._next = 0
        self._apply_until(0, animate)
        self.zoom = self.target_zoom()

    def seek(self, day):
        """Jump to a day (forwards or backwards) without animations."""
        day = max(0, min(int(day), self.total_days - 1))
        self.reset(animate=False)
        self.day = float(day)
        self._apply_until(day, False)
        self.zoom = self.target_zoom()
        for dot in self.dots.values():
            dot.appear = -1.0

    @property
    def finished(self):
        return self.day >= self.total_days - 1

    @property
    def day_index(self):
        return max(0, min(int(self.day), self.total_days - 1))

    def advance(self, dt, days_per_second):
        """Move the clock on by dt real seconds and animate everything."""
        if not self.finished:
            self.day = min(self.day + dt * days_per_second, self.total_days - 1)
            self._apply_until(self.day_index, True)
        self.clock += dt
        self.zoom += (self.target_zoom() - self.zoom) * min(1.0, dt * 1.5)    # ease towards it
        self._move_dots(dt)
        self._age_effects(dt)

    # ---------- queries for the view ----------

    def age(self, dot):
        return (self.day_index - dot.birth_day) // 365

    def counts(self):
        """(astronaut dots, martian-born dots) alive right now."""
        martians = sum(1 for d in self.dots.values() if d.martian)
        return len(self.dots) - martians, martians

    @property
    def storm_active(self):
        return self.day_index < self.storm_until

    @property
    def epidemic_active(self):
        return self.day_index < self.epidemic_until

    def infected(self, dot):
        """Cosmetic: during an epidemic a growing share of dots look sick."""
        if not self.epidemic_active:
            return False
        span = max(1, self.epidemic_until - self.epidemic_start)
        share = min(0.7, 1.4 * (self.day_index - self.epidemic_start) / span)
        return ((dot.uid * 2654435761) % 1000) / 1000.0 < share

    def at(self, series):
        return series[self.day_index] if series else 0

    # ---------- events ----------

    def _apply_until(self, day, animate):
        tl = self.timeline
        while self._next < len(tl) and tl[self._next][1] <= day:
            self._apply(tl[self._next], animate)
            self._next += 1

    def _apply(self, ev, animate):
        kind = ev[0]
        if kind == "ship":
            self.modules = max(self.modules, ev[2] + 1)
            if animate:
                x, y = self.module_pos(ev[2])
                self._effect(Effect("ship", x, y, LAND_TIME, ev[2]))
        elif kind == "arrive":
            _, day, uid, sex, age, home = ev
            self.modules = max(self.modules, home + 1)
            dot = self._new_dot(uid, home, sex, day - age * 365, martian=False)
            cx, cy = self.module_pos(home)
            if animate:                                  # appear when the ship touches down
                dot.x, dot.y = self._point_in(cx, cy, self.module_radius * 0.3)
                dot.appear = self.clock + LAND_TIME
            else:
                dot.x, dot.y = self._point_in(cx, cy, self.module_radius * 0.8)
            self._retarget(dot)
        elif kind == "birth":
            _, day, uid, sex, mother_uid = ev
            mother = self.dots.get(mother_uid)
            if mother:
                mother.pregnant = False
                home, (x, y) = mother.home, (mother.x, mother.y)
            else:
                home = max(0, self.modules - 1)
                x, y = self.module_pos(home)
            dot = self._new_dot(uid, home, sex, day, martian=True)
            dot.x, dot.y = x, y
            self._retarget(dot)
            if animate:
                self._effect(Effect("birth", x, y, 1.0))
        elif kind == "conceive":
            dot = self.dots.get(ev[2])
            if dot:
                dot.pregnant = True
        elif kind == "death":
            dot = self.dots.pop(ev[2], None)
            if dot and animate and dot.appear <= self.clock:
                self._effect(Effect("ghost", dot.x, dot.y, 1.4, ev[3]))
        elif kind == "storm":
            self.storm_until = max(self.storm_until, ev[2])
        elif kind == "epidemic":
            if self.day_index >= self.epidemic_until:    # a fresh outbreak, not an extension
                self.epidemic_start = ev[1]
            self.epidemic_until = max(self.epidemic_until, ev[2])
        elif kind == "breach" and animate:
            x, y = self.module_pos(ev[2])
            self._effect(Effect("breach", x, y, 1.6, ev[2]))

    def _effect(self, effect):
        self.effects.append(effect)
        if len(self.effects) > MAX_EFFECTS:               # fast playback: drop the oldest
            del self.effects[:len(self.effects) - MAX_EFFECTS]

    def _new_dot(self, uid, home, sex, birth_day, martian):
        d = Dot()
        d.uid, d.home, d.sex, d.birth_day, d.martian = uid, home, sex, birth_day, martian
        d.pregnant = False
        d.speed = self.rng.uniform(*DOT_SPEED)
        d.pause = self.rng.uniform(0, PAUSE_TIME[1])
        d.appear = -1.0
        d.x = d.y = d.tx = d.ty = 0.0
        self.dots[uid] = d
        return d

    # ---------- movement ----------

    def _retarget(self, dot):
        r = self.rng.random()
        home = dot.home
        if r < 0.70:                                      # stay around home
            dot.tx, dot.ty = self._point_in(*self.module_pos(home), self.module_radius * 0.85)
        elif r < 0.90:                                    # tend the farm
            dot.tx, dot.ty = self._point_in(*self.farm_pos(home), self.farm_radius * 0.8)
        else:                                             # visit another habitat
            k = self.rng.randrange(max(1, self.modules))
            dot.tx, dot.ty = self._point_in(*self.module_pos(k), self.module_radius * 0.85)

    def _move_dots(self, dt):
        clock = self.clock
        for dot in self.dots.values():
            if clock < dot.appear:
                continue
            if dot.pause > 0:
                dot.pause -= dt
                continue
            dx, dy = dot.tx - dot.x, dot.ty - dot.y
            dist = math.hypot(dx, dy)
            step = dot.speed * dt
            if dist <= step:
                dot.x, dot.y = dot.tx, dot.ty
                dot.pause = self.rng.uniform(*PAUSE_TIME)
                self._retarget(dot)
            else:
                dot.x += dx / dist * step
                dot.y += dy / dist * step

    def _age_effects(self, dt):
        for e in self.effects:
            e.t += dt
        self.effects = [e for e in self.effects if e.t < e.dur]

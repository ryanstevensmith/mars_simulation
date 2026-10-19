"""Replays a recorded simulation as a living base. No GUI code: colony_view.py draws this state.

The base is laid out once, up front, from every module the run ever builds: pressurized
modules fill a grid outwards from a central hub (each joined by a corridor to a neighbour
nearer the hub); solar arrays form a farm to the east, reactors sit out west, ice mines
north, and ships land on a pad to the south.

A ReplayState walks the SimResult.timeline in step with a simulated-day clock. Colonists
walk between their habitat, their job and the hub. Positions are cosmetic, but the counts
always match the model: after seek(d), len(dots) == result.sizes[d].
"""

import bisect
import math
import random

CELL = 46.0                     # grid spacing for pressurized modules (world units)
LAND_TIME = 1.6                 # real seconds a ship takes to come down
MAX_EFFECTS = 500
MAX_TOASTS = 6
TOAST_TIME = 4.0
DOT_SPEED = (26.0, 55.0)        # world units per real second
PAUSE_TIME = (0.3, 2.2)         # real seconds a colonist stays at each stop

OUTSIDE = {"solar", "reactor", "ice_mine"}


class Dot:
    __slots__ = ("uid", "x", "y", "tx", "ty", "speed", "pause", "home", "job", "sex",
                 "birth_day", "martian", "pregnant", "appear")


class Effect:
    """A short-lived visual: kind is 'ship', 'ghost', 'birth', 'built', 'failure' or 'breach'."""
    __slots__ = ("kind", "x", "y", "t", "dur", "data")

    def __init__(self, kind, x, y, dur, data=None):
        self.kind, self.x, self.y, self.t, self.dur, self.data = kind, x, y, 0.0, dur, data


class Slot:
    """Where a module sits and how big it is."""
    __slots__ = ("mid", "type", "x", "y", "w", "h", "parent")

    def __init__(self, mid, kind, x, y, w, h, parent=None):
        self.mid, self.type, self.x, self.y, self.w, self.h, self.parent = mid, kind, x, y, w, h, parent


class Layout:
    """Positions for every module the run will ever have, so nothing moves as the base grows."""

    def __init__(self, module_types):
        self.slots = {}
        core = [(mid, t) for mid, t in enumerate(module_types) if t not in OUTSIDE]
        cells = self._cells(len(core) + 1)           # cell 0 is the hub
        self.hub = (0.0, 0.0)
        taken = {cells[0]: None}
        for (mid, kind), cell in zip(core, cells[1:]):
            # corridor to whichever placed neighbour is closest to the hub
            nbrs = [(cell[0] + dx, cell[1] + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            placed = [n for n in nbrs if n in taken]
            parent_cell = min(placed, key=lambda n: n[0] ** 2 + n[1] ** 2) if placed else cells[0]
            parent = taken[parent_cell]
            size = CELL * (0.78 if kind == "greenhouse" else 0.66)
            w = CELL * 0.86 if kind == "greenhouse" else size
            self.slots[mid] = Slot(mid, kind, cell[0] * CELL, cell[1] * CELL, w, size,
                                   parent if parent is not None else -1)
            taken[cell] = mid
        ring = max((math.hypot(*c) for c in cells), default=1.0)
        self.core_radius = (ring + 0.8) * CELL

        r = self.core_radius
        by_type = {k: [mid for mid, t in enumerate(module_types) if t == k] for k in OUTSIDE}
        # solar farm to the east, in a block
        solar = by_type["solar"]
        cols = max(1, math.ceil(math.sqrt(len(solar) * 0.8)))
        for i, mid in enumerate(solar):
            row, col = divmod(i, cols)
            rows = math.ceil(len(solar) / cols)
            self.slots[mid] = Slot(mid, "solar", r + 2.2 * CELL + col * CELL * 1.25,
                                   (row - (rows - 1) / 2) * CELL * 0.8, CELL * 1.1, CELL * 0.62)
        # reactors out west, well away from the habitats
        for i, mid in enumerate(by_type["reactor"]):
            row, col = divmod(i, 4)
            self.slots[mid] = Slot(mid, "reactor", -r - 4.5 * CELL - col * CELL * 1.3,
                                   (row - 1.5) * CELL * 1.3 + (col % 2) * CELL * 0.4, CELL * 0.7, CELL * 0.7)
        # ice mines along an arc to the north
        mines = by_type["ice_mine"]
        for i, mid in enumerate(mines):
            a = math.radians(-90 + (i - (len(mines) - 1) / 2) * min(14.0, 120.0 / max(1, len(mines))))
            rr = r + 3.0 * CELL + (i % 2) * CELL * 0.8
            self.slots[mid] = Slot(mid, "ice_mine", rr * math.cos(a), rr * math.sin(a), CELL * 0.7, CELL * 0.7)
        self.pad = (-0.4 * r, r + 2.6 * CELL)

    @staticmethod
    def _cells(n):
        """Grid cells nearest the hub first, so the base grows as a compact blob."""
        span = int(math.sqrt(n)) + 2
        cells = [(x, y) for x in range(-span, span + 1) for y in range(-span, span + 1)]
        cells.sort(key=lambda c: (c[0] ** 2 + 1.15 * c[1] ** 2, math.atan2(c[1], c[0])))
        return cells[:n]

    def pos(self, mid):
        s = self.slots.get(mid)
        return (s.x, s.y) if s else self.hub


class ReplayState:

    def __init__(self, result, seed=0):
        self.result = result
        self.timeline = result.timeline
        self.events = result.events
        self.total_days = len(result.sizes)
        types = {}
        for e in self.timeline:
            if e[0] == "module":
                types[e[2]] = e[3]
        self.module_types = [types[m] for m in sorted(types)]
        self.layout = Layout(self.module_types)
        self._snap_days = [d for d, _ in result.snapshots]
        self.seed = seed
        self.reset()

    # ---------- control ----------

    def reset(self, animate=True):
        self.rng = random.Random(self.seed)
        self.day = 0.0
        self.clock = 0.0                # real seconds, drives animations
        self.modules = {}               # mid -> "building" | "built"
        self.dots = {}
        self.effects = []
        self.toasts = []                # (clock time, kind, text)
        self.storm_until = self.epidemic_until = -1
        self.epidemic_start = -1
        self.techs = len(self.result.params.strategy.starting_techs)
        self._next = 0
        self._next_event = 0
        self._apply_until(0, animate)
        self.zoom = self.target_zoom()

    def seek(self, day):
        """Jump to a day (forwards or backwards) without animations."""
        day = max(0, min(int(day), self.total_days - 1))
        self.reset(animate=False)
        self.day = float(day)
        self._apply_until(day, False)
        for dot in self.dots.values():
            dot.appear = -1.0
            dot.x, dot.y = self._spot_for(dot)
        self.zoom = self.target_zoom()

    @property
    def finished(self):
        return self.day >= self.total_days - 1

    @property
    def day_index(self):
        return max(0, min(int(self.day), self.total_days - 1))

    def advance(self, dt, days_per_second):
        """Move the clock on by dt real seconds and animate everything."""
        if not self.finished and days_per_second > 0:
            self.day = min(self.day + dt * days_per_second, self.total_days - 1)
            self._apply_until(self.day_index, True)
        self.clock += dt
        self.zoom += (self.target_zoom() - self.zoom) * min(1.0, dt * 1.5)
        self._move_dots(dt)
        self._age_effects(dt)

    # ---------- queries for the view ----------

    def target_zoom(self):
        """Zoom (world units -> 'view units', 1.0 = a 600-unit-high view) framing what exists."""
        extent = self.layout.core_radius * 0.6
        for mid in self.modules:
            s = self.layout.slots[mid]
            extent = max(extent, abs(s.x) + s.w, abs(s.y) * 1.5 + s.h)
        return max(0.25, min(3.0, 280.0 / (extent + CELL)))

    def age(self, dot):
        return (self.day_index - dot.birth_day) // 365

    def counts(self):
        """(earth-born, mars-born) alive right now."""
        martians = sum(1 for d in self.dots.values() if d.martian)
        return len(self.dots) - martians, martians

    @property
    def storm_active(self):
        return self.day_index < self.storm_until

    @property
    def epidemic_active(self):
        return self.day_index < self.epidemic_until

    def infected(self, dot):
        """Cosmetic: during an epidemic a growing share of colonists look sick."""
        if not self.epidemic_active:
            return False
        span = max(1, self.epidemic_until - self.epidemic_start)
        share = min(0.7, 1.4 * (self.day_index - self.epidemic_start) / span)
        return ((dot.uid * 2654435761) % 1000) / 1000.0 < share

    def series(self, name):
        values = self.result.series[name]
        return values[self.day_index] if values else 0

    def module_state(self, mid):
        """(condition, efficiency, build progress) from the latest snapshot at or before today."""
        i = bisect.bisect_right(self._snap_days, self.day_index) - 1
        if i < 0:
            return 1.0, 1.0, 0.0
        snap = self.result.snapshots[i][1]
        return snap[mid] if mid < len(snap) else (1.0, 0.0, 0.0)

    # ---------- events ----------

    def _apply_until(self, day, animate):
        tl = self.timeline
        while self._next < len(tl) and tl[self._next][1] <= day:
            self._apply(tl[self._next], animate)
            self._next += 1
        ev = self.events
        while self._next_event < len(ev) and ev[self._next_event][0] <= day:
            if animate and ev[self._next_event][1] not in ("build",):
                self.toasts.append((self.clock, ev[self._next_event][1], ev[self._next_event][2]))
            self._next_event += 1
        if len(self.toasts) > MAX_TOASTS:
            del self.toasts[:len(self.toasts) - MAX_TOASTS]

    def _apply(self, ev, animate):
        kind = ev[0]
        lay = self.layout
        if kind == "ship":
            if animate:
                self._effect(Effect("ship", lay.pad[0], lay.pad[1], LAND_TIME))
        elif kind == "arrive":
            _, day, uid, sex, age = ev
            dot = self._new_dot(uid, sex, day - age * 365, martian=False)
            dot.x, dot.y = self._near(lay.pad, CELL * 0.5)
            dot.tx, dot.ty = dot.x, dot.y
            dot.appear = self.clock + LAND_TIME if animate else -1.0
            dot.pause = self.rng.uniform(0, 0.6)
        elif kind == "home" or kind == "job":
            dot = self.dots.get(ev[2])
            if dot:
                setattr(dot, kind, ev[3])
                if kind == "home" and dot.tx == dot.x and dot.ty == dot.y:
                    dot.tx, dot.ty = self._spot(ev[3])        # newcomers head for their new home
        elif kind == "birth":
            _, day, uid, sex, mother_uid = ev
            mother = self.dots.get(mother_uid)
            dot = self._new_dot(uid, sex, day, martian=True)
            if mother:
                mother.pregnant = False
                dot.home = mother.home
                dot.x, dot.y = mother.x, mother.y
            else:
                dot.x, dot.y = lay.hub
            dot.tx, dot.ty = dot.x, dot.y
            if animate:
                self._effect(Effect("birth", dot.x, dot.y, 1.0))
        elif kind == "conceive":
            dot = self.dots.get(ev[2])
            if dot:
                dot.pregnant = True
        elif kind == "death":
            dot = self.dots.pop(ev[2], None)
            if dot and animate and dot.appear <= self.clock:
                self._effect(Effect("ghost", dot.x, dot.y, 1.4, ev[3]))
        elif kind == "module":
            _, day, mid, mtype, status = ev
            self.modules[mid] = "built" if status == "built" else "building"
            if animate and status == "built":
                x, y = lay.pos(mid)
                self._effect(Effect("built", x, y, 1.2, mid))
        elif kind == "damage":
            if animate:
                x, y = lay.pos(ev[2])
                self._effect(Effect(ev[3], x, y, 1.6, ev[2]))
        elif kind == "tech":
            self.techs += 1
        elif kind == "storm":
            self.storm_until = max(self.storm_until, ev[2])
        elif kind == "epidemic":
            if self.day_index >= self.epidemic_until:     # a fresh outbreak, not an extension
                self.epidemic_start = ev[1]
            self.epidemic_until = max(self.epidemic_until, ev[2])

    def _effect(self, effect):
        self.effects.append(effect)
        if len(self.effects) > MAX_EFFECTS:               # fast playback: drop the oldest
            del self.effects[:len(self.effects) - MAX_EFFECTS]

    def _new_dot(self, uid, sex, birth_day, martian):
        d = Dot()
        d.uid, d.sex, d.birth_day, d.martian = uid, sex, birth_day, martian
        d.home = d.job = -1
        d.pregnant = False
        d.speed = self.rng.uniform(*DOT_SPEED)
        d.pause = self.rng.uniform(0, PAUSE_TIME[1])
        d.appear = -1.0
        d.x = d.y = d.tx = d.ty = 0.0
        self.dots[uid] = d
        return d

    # ---------- movement ----------

    def _near(self, point, radius):
        a = self.rng.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(self.rng.random())
        return point[0] + r * math.cos(a), point[1] + r * math.sin(a)

    def _spot(self, mid):
        """A random point inside a module (or around the hub)."""
        s = self.layout.slots.get(mid)
        if s is None or mid not in self.modules:
            return self._near(self.layout.hub, CELL * 0.35)
        return (s.x + self.rng.uniform(-0.4, 0.4) * s.w, s.y + self.rng.uniform(-0.4, 0.4) * s.h)

    def _spot_for(self, dot):
        """Where a colonist wants to be next: work, home, the hub or a construction site."""
        r = self.rng.random()
        adult = 16 <= self.age(dot) < 65
        if adult and dot.job >= 0:
            if r < 0.55:
                return self._spot(dot.job)
            if r < 0.85:
                return self._spot(dot.home)
            return self._spot(-1)
        if adult:                                         # idle workers help build
            sites = [m for m, status in self.modules.items() if status == "building"]
            if sites and r < 0.6:
                return self._spot(self.rng.choice(sites))
        if r < 0.65:
            return self._spot(dot.home)
        return self._spot(-1)

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
                dot.tx, dot.ty = self._spot_for(dot)
            else:
                dot.x += dx / dist * step
                dot.y += dy / dist * step

    def _age_effects(self, dt):
        for e in self.effects:
            e.t += dt
        self.effects = [e for e in self.effects if e.t < e.dur]
        self.toasts = [t for t in self.toasts if self.clock - t[0] < TOAST_TIME]

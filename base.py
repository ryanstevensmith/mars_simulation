"""The colony base: modules, crews, power, water, oxygen, food, materials and research.

One connected base made of modules. Every day:
  1. power is generated (solar, reactors) and shared out in priority order, life support first
  2. each module runs at   staffing x power share x condition
  3. water is recycled and mined, then shared: people drink first, then electrolysis (which
     turns water into oxygen), then greenhouses
  4. oxygen comes from life support and greenhouses; food from greenhouses
  5. workshops make materials, which pay for maintenance first and new modules second
  6. labs make research points that unlock technologies

Whatever runs short raises the matching death risk (starvation, dehydration, suffocation)
and holds back births. A planner builds whatever the base is shortest of, weighted by the
colony's strategy.
"""

from dataclasses import dataclass

# ---------------------------------------------------------------- module types


@dataclass(frozen=True)
class ModuleType:
    key: str
    name: str
    pressurized: bool   # part of the connected base (outside modules are reached on foot)
    crew: int           # workers needed for full output
    power_use: float    # kW at full output
    power_out: float    # kW generated at full output
    cost: float         # materials to build locally
    build_days: int     # with a full build crew


MODULE_TYPES = {m.key: m for m in (
    ModuleType("hab",        "Habitat",         True,  0,  6, 0,  60,  60),
    ModuleType("greenhouse", "Greenhouse",      True,  3, 20, 0,  80,  75),
    ModuleType("lss",        "Life Support",    True,  1, 20, 0,  70,  60),
    ModuleType("recycler",   "Water Reclaimer", True,  1, 10, 0,  50,  45),
    ModuleType("workshop",   "Workshop",        True,  4, 25, 0,  70,  60),
    ModuleType("medbay",     "Medical Bay",     True,  2, 10, 0,  60,  60),
    ModuleType("lab",        "Research Lab",    True,  3, 15, 0,  60,  60),
    ModuleType("ice_mine",   "Ice Mine",        False, 3, 30, 0,  60,  60),
    ModuleType("solar",      "Solar Array",     False, 0,  0, 60, 55,  40),
    ModuleType("reactor",    "Fission Reactor", False, 1,  0, 40, 160, 120),
)}

POWER_PRIORITY = ("lss", "recycler", "hab", "medbay", "greenhouse", "ice_mine", "workshop", "lab")
CREW_PRIORITY = ("reactor", "lss", "recycler", "greenhouse", "ice_mine", "medbay", "workshop", "lab")

# per-module output at full efficiency
BEDS_PER_HAB = 20
GH_FOOD = 16.0          # rations a day
GH_O2 = 8.0             # kg a day
GH_WATER = 160.0        # litres a day transpired (reclaimable)
LSS_O2 = 25.0           # kg a day by electrolysis
LSS_WATER = 28.0        # litres a day split into oxygen (lost)
RECYCLER_CAP = 1500.0   # litres a day processed
ICE_WATER = 220.0       # litres a day mined
WORKSHOP_OUT = 6.0      # materials a day
MED_COVER = 80          # people one medical bay looks after
LAB_OUT = 0.2           # research points a day

# per-person needs (children need ~60%)
O2_PER_PERSON = 0.84
WATER_PER_PERSON = 12.0
FOOD_PER_PERSON = 1.0
CHILD_SHARE = 0.6

# upkeep
UPKEEP = 0.12           # materials per module per day
WEAR = 0.0008           # condition lost per day without maintenance (~3.4 years to failure)
REPAIR = 0.004          # condition regained per day when maintained
BUILD_CREW = 4          # idle workers needed for full build speed
PLAN_EVERY = 10         # days between build decisions / crew rotas
CARGO_LOSS_CHANCE = 0.05

# extra daily death chance at a 100% shortfall
SUFFOCATION_RATE = 0.08
DEHYDRATION_RATE = 0.03
STARVATION_RATE = 0.004
EPIDEMIC_RATE = 0.002

# disasters, average events per year (scaled by DISASTER_SCALE, storms also by the site)
STORMS_PER_YEAR = 0.4
EPIDEMICS_PER_YEAR = 0.12       # also scaled by crowding
FAILURES_PER_MODULE_YEAR = 0.06
BREACHES_PER_YEAR = 0.1

TECHS = {
    "crops1":   ("High-yield hydroponics",     240,  "+25% greenhouse food"),
    "water1":   ("Improved water recovery",    320,  "water recycling 90% -> 95%"),
    "panels":   ("Dust-shedding solar panels", 400, "storms cut solar output by 40%, not 65%"),
    "electro":  ("Efficient electrolysers",    480, "+30% life-support oxygen"),
    "sinter":   ("Regolith sintering",         600, "+50% workshop output"),
    "medicine": ("Advanced medicine",          720, "+50% medical coverage, fewer natural deaths"),
    "water2":   ("Closed-loop water",          880, "water recycling -> 98%"),
    "led":      ("Efficient grow lights",      1040, "-40% greenhouse power"),
    "robots":   ("Maintenance robots",         1200, "-40% upkeep, faster repairs"),
    "crops2":   ("Mars-adapted crops",         1400, "+25% greenhouse food, -30% greenhouse water"),
}

RESOURCES = ("food", "water", "o2", "materials")


def condition_factor(c):
    """Modules work fully above 60% condition, fade below it and stop under 5%."""
    return 0.0 if c < 0.05 else min(1.0, c / 0.6)


class Module:
    __slots__ = ("mid", "type", "built", "progress", "build_days", "condition", "staff", "number")

    def __init__(self, mid, kind, number):
        self.mid = mid
        self.type = kind
        self.number = number         # "Greenhouse 3"
        self.built = False
        self.progress = 0.0
        self.build_days = MODULE_TYPES[kind].build_days
        self.condition = 1.0
        self.staff = 0

    @property
    def spec(self):
        return MODULE_TYPES[self.type]

    @property
    def label(self):
        return self.spec.name + " " + str(self.number)

    @property
    def operating(self):
        return self.built and self.condition >= 0.05

    def staffing(self):
        crew = self.spec.crew
        return 1.0 if crew == 0 else min(1.0, self.staff / crew)


class Base:

    def __init__(self, params, rng, log, event):
        self.params = params
        self.strategy = params.strategy
        self.site = params.site
        self.rng = rng
        self.log = log              # replay timeline
        self.event = event          # human-readable mission log: event(day, kind, text)

        self.modules = []
        self.counts = {k: 0 for k in MODULE_TYPES}
        self.stock = {"food": 0.0, "water": 0.0, "o2": 0.0, "materials": 0.0}
        self.research = 0.0
        self.techs = set(self.strategy.starting_techs)
        order = list(self.strategy.tech_order) + [t for t in TECHS if t not in self.strategy.tech_order]
        self.tech_queue = [t for t in order if t not in self.techs]

        self.storm_until = self.epidemic_until = self.epidemic_start = -1
        self.idle_workers = 0
        self.crowding = 1.0
        self.stats = {}             # latest daily figures (also what the planner looks at)

    # ---------------------------------------------------------------- modules

    def add_module(self, day, kind, built, build_days=None):
        self.counts[kind] += 1
        m = Module(len(self.modules), kind, self.counts[kind])
        if build_days is not None:
            m.build_days = build_days
        m.built = built
        self.modules.append(m)
        self.log(("module", day, m.mid, kind, "built" if built else "start"))
        return m

    def operating(self, kind):
        return [m for m in self.modules if m.type == kind and m.operating]

    @property
    def beds(self):
        return BEDS_PER_HAB * sum(1 for m in self.modules if m.type == "hab" and m.operating)

    @property
    def under_construction(self):
        return [m for m in self.modules if not m.built]

    def has(self, tech):
        return tech in self.techs

    # ---------------------------------------------------------------- ships

    def receive_ship(self, day, ship_no):
        """Unload a ship. The first one lands the starter base; later ones may lose their cargo."""
        s = self.strategy
        if ship_no == 0:
            for kind, n in s.starter_modules.items():
                for _ in range(n):
                    self.add_module(day, kind, built=True)
            k = self.params.SUPPLY_SCALE
            self.stock.update(food=s.starting_food * k, water=20000.0 * k, o2=3000.0 * k,
                              materials=s.ship_materials * k)
            self.event(day, "ship", "First landing: {} colonists and a starter base of {} modules".format(
                self.params.colonists_per_ship, len(self.modules)))
            return False

        if self.rng.random() < min(0.5, CARGO_LOSS_CHANCE * self.params.DISASTER_SCALE):
            self.event(day, "cargo", "Cargo ship lost on the way - colonists arrived without supplies")
            return True
        self.stock["food"] += s.ship_food * self.params.SUPPLY_SCALE
        self.stock["materials"] += s.ship_materials * self.params.SUPPLY_SCALE
        for kind, n in s.ship_modules.items():
            for _ in range(n):           # prefabs: no materials needed, quick to assemble
                self.add_module(day, kind, built=False, build_days=int(MODULE_TYPES[kind].build_days * 0.4))
        self.event(day, "ship", "Ship {} landed: {} colonists, {} prefab modules".format(
            ship_no + 1, self.params.colonists_per_ship, sum(s.ship_modules.values())))
        return False

    # ---------------------------------------------------------------- homes and jobs

    def allocate(self, day, colony):
        """Give everyone a bed and every working-age adult a job. Changes go to the timeline."""
        habs = [m for m in self.modules if m.type == "hab" and m.built]
        residents = {m.mid: [] for m in habs}
        homeless = []
        for x in colony:
            (residents[x.home] if x.home in residents else homeless).append(x)

        def move_home(x, mid):
            if x.home != mid:
                x.home = mid
                self.log(("home", day, x.uid, mid))

        for x in homeless:
            if not habs:
                move_home(x, -1)
                continue
            mid = min(residents, key=lambda k: len(residents[k]))
            residents[mid].append(x)
            move_home(x, mid)
        # spread people out of overfull habitats into any with free beds
        for mid in sorted(residents, key=lambda k: -len(residents[k])):
            while len(residents[mid]) > BEDS_PER_HAB:
                target = min(residents, key=lambda k: len(residents[k]))
                if len(residents[target]) >= BEDS_PER_HAB:
                    break
                x = residents[mid].pop()
                residents[target].append(x)
                move_home(x, target)

        # jobs
        lo, hi = self.params.WORK_AGE_MIN, self.params.WORK_AGE_MAX
        workplaces = sorted((m for m in self.modules if m.operating and m.spec.crew > 0),
                            key=lambda m: (CREW_PRIORITY.index(m.type), m.mid))
        crews = {m.mid: [] for m in workplaces}
        pool = []
        for x in colony:
            if not lo <= x.getAge(day) < hi:
                if x.job != -1:
                    x.job = -1
                    self.log(("job", day, x.uid, -1))
                continue
            if x.job in crews:
                crews[x.job].append(x)
            else:
                pool.append(x)
        for m in workplaces:                         # release extras (e.g. after a downgrade)
            while len(crews[m.mid]) > m.spec.crew:
                pool.append(crews[m.mid].pop())
        for m in workplaces:                         # fill vacancies, most important first
            while len(crews[m.mid]) < m.spec.crew and pool:
                crews[m.mid].append(pool.pop())
        for m in self.modules:
            m.staff = len(crews.get(m.mid, ()))
        for mid, crew in crews.items():
            for x in crew:
                if x.job != mid:
                    x.job = mid
                    self.log(("job", day, x.uid, mid))
        for x in pool:
            if x.job != -1:
                x.job = -1
                self.log(("job", day, x.uid, -1))
        self.idle_workers = len(pool)

    def on_death(self, x):
        if 0 <= x.job < len(self.modules):
            self.modules[x.job].staff -= 1

    # ---------------------------------------------------------------- disasters

    def disasters(self, day):
        """Roll for today's disasters. Returns (habitat mid, deaths) if a breach hits a habitat."""
        scale = self.params.DISASTER_SCALE
        rng = self.rng
        if scale <= 0:
            return None
        if rng.random() < STORMS_PER_YEAR * self.site.storms * scale / 365:
            length = rng.randint(30, 120)
            self.storm_until = max(self.storm_until, day + length)
            self.log(("storm", day, self.storm_until))
            self.event(day, "storm", "Dust storm: solar output cut for {} days".format(length))
        if rng.random() < EPIDEMICS_PER_YEAR * scale * max(0.5, min(3.0, self.crowding)) / 365:
            length = rng.randint(20, 60)
            if day >= self.epidemic_until:
                self.epidemic_start = day
            self.epidemic_until = max(self.epidemic_until, day + length)
            self.log(("epidemic", day, self.epidemic_until))
            self.event(day, "epidemic", "Epidemic outbreak ({} days)".format(length))
        built = [m for m in self.modules if m.built]
        if built and rng.random() < FAILURES_PER_MODULE_YEAR * scale * len(built) / 365:
            m = rng.choice(built)
            m.condition = max(0.0, m.condition - 0.5)
            self.log(("damage", day, m.mid, "failure"))
            self.event(day, "failure", "Equipment failure in " + m.label)
        if rng.random() < BREACHES_PER_YEAR * scale / 365:
            inside = [m for m in built if m.spec.pressurized]
            if inside:
                m = rng.choice(inside)
                m.condition = max(0.0, m.condition - 0.7)
                self.log(("damage", day, m.mid, "breach"))
                if m.type == "hab":
                    return m, rng.randint(1, 4)
                self.event(day, "breach", "Hull breach in " + m.label)
        return None

    # ---------------------------------------------------------------- the daily economy

    def produce(self, day, adults, children):
        """Run the base for a day. Returns how well people's needs were met."""
        st = self.stats = {}
        storm = day < self.storm_until
        has = self.has

        # module efficiency before power: staffing x condition, summed per type
        raw = {k: 0.0 for k in MODULE_TYPES}
        for m in self.modules:
            if m.operating:
                raw[m.type] += m.staffing() * condition_factor(m.condition)

        # power
        solar = self.site.solar * ((0.6 if has("panels") else 0.35) if storm else 1.0)
        supply = (raw["solar"] * MODULE_TYPES["solar"].power_out * solar
                  + raw["reactor"] * MODULE_TYPES["reactor"].power_out)
        demand = {k: raw[k] * MODULE_TYPES[k].power_use for k in POWER_PRIORITY}
        if has("led"):
            demand["greenhouse"] *= 0.6
        power = {}
        left = supply
        for k in POWER_PRIORITY:
            give = min(demand[k], left)
            power[k] = give / demand[k] if demand[k] > 0 else 1.0
            left -= give
        eff = {k: raw[k] * power.get(k, 1.0) for k in MODULE_TYPES}
        st["power_supply"], st["power_demand"] = supply, sum(demand.values())

        people = adults + CHILD_SHARE * children
        s = self.stock

        # water: people first, then greenhouses, then electrolysis
        recycle = 0.98 if has("water2") else 0.95 if has("water1") else 0.90
        use = people * WATER_PER_PERSON
        gh_water = eff["greenhouse"] * GH_WATER * (0.7 if has("crops2") else 1.0)
        lss_water = eff["lss"] * LSS_WATER
        reclaimed = min(eff["recycler"] * RECYCLER_CAP, use + gh_water) * recycle
        mined = eff["ice_mine"] * ICE_WATER * self.site.ice
        available = s["water"] + reclaimed + mined
        drink = min(use, available)
        available -= drink
        lss_given = min(lss_water, available)      # breathing matters more than crops
        available -= lss_given
        gh_given = min(gh_water, available)
        available -= gh_given
        water_sat = drink / use if use > 0 else 1.0
        gh_frac = gh_given / gh_water if gh_water > 0 else 1.0
        lss_frac = lss_given / lss_water if lss_water > 0 else 1.0
        s["water"] = min(available, 30000 + 15000 * len(self.operating("recycler")))
        st["water_in"] = reclaimed + mined
        st["water_out"] = use + gh_water + lss_water
        st["water_use"] = use + gh_water

        # oxygen
        o2_made = (eff["lss"] * LSS_O2 * (1.3 if has("electro") else 1.0) * lss_frac
                   + eff["greenhouse"] * GH_O2 * gh_frac)
        o2_need = people * O2_PER_PERSON
        available = s["o2"] + o2_made
        breathe = min(o2_need, available)
        o2_sat = breathe / o2_need if o2_need > 0 else 1.0
        s["o2"] = min(available - breathe, 3000 + 1500 * len(self.operating("lss")))
        st["o2_made"], st["o2_need"] = o2_made, o2_need

        # food
        yield_ = 1.0 + 0.25 * has("crops1") + 0.25 * has("crops2")
        food_made = eff["greenhouse"] * GH_FOOD * yield_ * gh_frac
        food_need = people * FOOD_PER_PERSON
        available = s["food"] + food_made
        eat = min(food_need, available)
        food_sat = eat / food_need if food_need > 0 else 1.0
        s["food"] = min(available - eat, 25000 + 4000 * len(self.operating("greenhouse")))
        st["food_made"], st["food_need"] = food_made, food_need

        # materials: maintenance first
        made = eff["workshop"] * WORKSHOP_OUT * (1.5 if has("sinter") else 1.0)
        s["materials"] = min(s["materials"] + made, 3000 + 2000 * len(self.operating("workshop")))
        built = [m for m in self.modules if m.built]
        upkeep = len(built) * UPKEEP * (0.6 if has("robots") else 1.0)
        maintained = 1.0 if upkeep <= s["materials"] else (s["materials"] / upkeep if upkeep else 1.0)
        s["materials"] = max(0.0, s["materials"] - upkeep)
        repair = REPAIR * (1.5 if has("robots") else 1.0) * maintained
        for m in built:
            m.condition = max(0.0, min(1.0, m.condition + repair - WEAR))
        st["materials_made"], st["upkeep"] = made, upkeep

        # research
        self.research += eff["lab"] * LAB_OUT * self.strategy.research_rate
        if self.tech_queue and self.research >= TECHS[self.tech_queue[0]][1]:
            tech = self.tech_queue.pop(0)
            self.research -= TECHS[tech][1]
            self.techs.add(tech)
            self.log(("tech", day, tech))
            self.event(day, "tech", "Breakthrough: {} ({})".format(TECHS[tech][0], TECHS[tech][2]))

        # health and housing
        pop = adults + children
        coverage = min(1.0, eff["medbay"] * MED_COVER * (1.5 if has("medicine") else 1.0) / pop) if pop else 1.0
        beds = self.beds
        self.crowding = pop / beds if beds else (3.0 if pop else 0.0)
        housing = 1.0 if self.crowding <= 0.9 else max(0.15, 1.0 - (self.crowding - 0.9) * 4.25)

        st.update(food_sat=food_sat, water_sat=water_sat, o2_sat=o2_sat, coverage=coverage,
                  crowding=self.crowding, beds=beds, storm=storm, power=power)
        epidemic = day < self.epidemic_until
        return {
            "extra": {
                "suffocation": SUFFOCATION_RATE * (1 - o2_sat),
                "dehydration": DEHYDRATION_RATE * (1 - water_sat),
                "starvation": STARVATION_RATE * (1 - food_sat),
                "epidemic": EPIDEMIC_RATE * (1 - 0.6 * coverage) if epidemic else 0.0,
            },
            "natural_scale": self.site.radiation * (1 - 0.3 * coverage) * (0.8 if has("medicine") else 1.0),
            "fertility": min(food_sat, water_sat, o2_sat) * housing * self.strategy.fertility,
        }

    # ---------------------------------------------------------------- building

    def plan(self, day, pop, incoming):
        """Every PLAN_EVERY days: start building whatever the base is shortest of.

        As many sites as there are idle build crews for, picking the most urgent need each time.
        """
        if not self.stats:
            return
        idle = self.idle_workers
        slots = min(4, max(1, idle // BUILD_CREW) - len(self.under_construction))
        for _ in range(slots):
            kind = self._choose(pop, incoming, idle)
            if not kind:
                break
            self.stock["materials"] -= self.cost(kind)
            idle -= MODULE_TYPES[kind].crew
            m = self.add_module(day, kind, built=False)
            self.event(day, "build", "Construction started: " + m.label)

    def _choose(self, pop, incoming, idle):
        st = self.stats
        w = self.strategy.build_weights
        has = self.has
        planned = {k: 0 for k in MODULE_TYPES}
        for m in self.under_construction:
            planned[m.type] += 1

        def ratio(made, need):
            return made / need if need > 0 else 2.0

        def urgency(stock, made, need):
            """Extra priority when a reserve will run dry soon."""
            if made >= need:
                return 0.0
            days = stock / (need - made)
            return 1.0 if days < 60 else 0.5 if days < 180 else 0.0

        yield_ = 1.0 + 0.25 * has("crops1") + 0.25 * has("crops2")
        food_made = st["food_made"] + planned["greenhouse"] * GH_FOOD * yield_
        o2_made = st["o2_made"] + planned["lss"] * LSS_O2 + planned["greenhouse"] * GH_O2
        water_in = st["water_in"] + planned["ice_mine"] * ICE_WATER * self.site.ice
        rec_cap = RECYCLER_CAP * (len(self.operating("recycler")) + planned["recycler"])
        supply = (st["power_supply"] + planned["solar"] * MODULE_TYPES["solar"].power_out * self.site.solar
                  + planned["reactor"] * MODULE_TYPES["reactor"].power_out)
        beds = st["beds"] + BEDS_PER_HAB * planned["hab"]
        coverage = st["coverage"] + planned["medbay"] * MED_COVER / max(1, pop)
        labs_wanted = max(1.0, pop / 250) * w.get("lab", 1.0)
        food_urgency = urgency(self.stock["food"], food_made, st["food_need"])
        o2_urgency = urgency(self.stock["o2"], o2_made, st["o2_need"])
        water_urgency = urgency(self.stock["water"], water_in, st["water_out"])

        scores = {
            "hab": 1.5 * ((pop + incoming) / max(1, beds) - 0.85),
            "greenhouse": 1.1 - ratio(food_made, st["food_need"]) + food_urgency + 0.3 * o2_urgency,
            "lss": 1.15 - ratio(o2_made, st["o2_need"]) + o2_urgency,
            # recycling is the cheap fix while there's waste water going unprocessed; then mine more
            "recycler": 1.2 * (1.0 - ratio(rec_cap, st["water_use"]))
                        + (water_urgency if rec_cap < st["water_use"] else 0.0),
            "ice_mine": (0.4 if water_in < st["water_out"] else 0.0)
                        + water_urgency * (1.0 if rec_cap >= 0.9 * st["water_use"] else 0.4),
            "power": 1.15 - ratio(supply, st["power_demand"]),
            "workshop": 1.3 - ratio(st["materials_made"] + planned["workshop"] * WORKSHOP_OUT, st["upkeep"])
                        - (0.6 if self.stock["materials"] > 1500 else 0.0),
            "medbay": 0.9 - coverage,
            "lab": 0.4 * (1 - (len(self.operating("lab")) + planned["lab"]) / labs_wanted),
        }
        power_kind = "reactor" if self.strategy.prefer_reactors else "solar"
        if power_kind == "reactor" and self.stock["materials"] < self.cost("reactor"):
            power_kind = "solar"
        scores[power_kind] = scores.pop("power")

        best, best_score = None, 0.05
        for kind, score in scores.items():
            score *= w.get(kind, 1.0)
            spec = MODULE_TYPES[kind]
            if spec.crew > idle:
                score *= 0.3                         # nobody free to run it
            if score > best_score and self.stock["materials"] >= self.cost(kind):
                best, best_score = kind, score
        return best

    def cost(self, kind):
        return MODULE_TYPES[kind].cost * self.strategy.build_cost

    def construct(self, day):
        """Idle workers push construction along. Returns True if anything was finished."""
        sites = self.under_construction
        if not sites:
            return False
        per_site = max(0.25, min(1.0, self.idle_workers / (BUILD_CREW * len(sites)))) * self.strategy.build_speed
        finished = False
        for m in sites:
            m.progress += per_site
            if m.progress >= m.build_days:
                m.built = True
                finished = True
                self.log(("module", day, m.mid, m.type, "built"))
                self.event(day, "built", m.label + " completed")
        return finished

    def snapshot(self):
        """Module state for the viewer: (condition, efficiency, build progress) per module."""
        power = self.stats.get("power", {})
        return tuple((round(m.condition, 2),
                      round(m.staffing() * condition_factor(m.condition) * power.get(m.type, 1.0), 2)
                      if m.operating else 0.0,
                      1.0 if m.built else round(m.progress / m.build_days, 2))
                     for m in self.modules)

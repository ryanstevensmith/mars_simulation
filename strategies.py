"""Colony strategies and landing sites: the handful of choices made before launch.

A strategy decides what the first ship lands, what every later ship carries, what the base
prefers to build, how keen the colony is on children and which technologies it researches
first. A landing site sets the local conditions.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Strategy:
    key: str
    name: str
    tagline: str
    description: str
    colonists_per_ship: int
    starter_modules: dict           # module type -> count, built on day 0
    ship_modules: dict              # prefab modules on each later ship (assembled on arrival)
    starting_food: float            # rations landed with the first ship
    ship_food: float                # rations on each later ship
    ship_materials: float           # materials on every ship
    build_weights: dict = field(default_factory=dict)    # module type -> priority multiplier
    fertility: float = 1.0          # multiplier on the birth rate
    research_rate: float = 1.0
    starting_techs: tuple = ()
    tech_order: tuple = ()          # researched first (the rest follow in the default order)
    prefer_reactors: bool = False   # build reactors rather than solar for new power
    build_speed: float = 1.0        # construction speed multiplier
    build_cost: float = 1.0         # materials cost multiplier
    strengths: tuple = ()
    weaknesses: tuple = ()


@dataclass(frozen=True)
class Site:
    key: str
    name: str
    description: str
    solar: float        # sunlight multiplier
    ice: float          # ice-mining multiplier
    storms: float       # dust-storm frequency multiplier
    radiation: float    # natural-mortality multiplier (thicker air = better shielding)


STRATEGIES = {s.key: s for s in (
    Strategy(
        key="balanced", name="Balanced Settlement",
        tagline="A bit of everything",
        description="A steady, well-rounded base that grows with the ships and builds whatever is short.",
        colonists_per_ship=60,
        starter_modules={"hab": 3, "greenhouse": 4, "lss": 1, "recycler": 1, "ice_mine": 1,
                         "solar": 4, "workshop": 1, "medbay": 1},
        ship_modules={"hab": 3, "greenhouse": 3, "solar": 2, "lss": 1},
        starting_food=12000, ship_food=8000, ship_materials=300,
        strengths=("No weak spots",), weaknesses=("No standout strengths",),
    ),
    Strategy(
        key="agri", name="Agricultural Colony",
        tagline="Food focus",
        description="Greenhouses first. Big food reserves and water capacity make it hard to starve.",
        colonists_per_ship=50,
        starter_modules={"hab": 3, "greenhouse": 6, "lss": 1, "recycler": 2, "ice_mine": 2,
                         "solar": 6, "workshop": 1, "medbay": 1},
        ship_modules={"hab": 3, "greenhouse": 4, "solar": 3, "recycler": 1},
        starting_food=20000, ship_food=12000, ship_materials=250,
        build_weights={"greenhouse": 1.6, "recycler": 1.3, "ice_mine": 1.3},
        fertility=1.1,
        tech_order=("crops1", "water1", "led", "crops2", "water2"),
        strengths=("Huge food security", "Plenty of water"), weaknesses=("Fewer colonists", "Power hungry"),
    ),
    Strategy(
        key="frontier", name="Frontier Town",
        tagline="Population focus",
        description="Pack the ships with people and raise families. Grows fast, lives on the edge.",
        colonists_per_ship=100,
        starter_modules={"hab": 4, "greenhouse": 6, "lss": 2, "recycler": 2, "ice_mine": 2,
                         "solar": 7, "workshop": 1, "medbay": 1},
        ship_modules={"hab": 5, "greenhouse": 5, "solar": 3, "lss": 1, "recycler": 1},
        starting_food=10000, ship_food=8000, ship_materials=200,
        build_weights={"hab": 2.0, "medbay": 1.3},
        fertility=1.6,
        tech_order=("medicine", "crops1", "water1"),
        strengths=("Fastest growth", "Most Mars-born"), weaknesses=("Thin margins", "Crowding and disease"),
    ),
    Strategy(
        key="tech", name="Research Outpost",
        tagline="Technology focus",
        description="A small expert crew with reactors and labs. Out-invents its problems over time.",
        colonists_per_ship=40,
        starter_modules={"hab": 2, "greenhouse": 3, "lss": 1, "recycler": 1, "ice_mine": 1,
                         "reactor": 3, "solar": 1, "workshop": 1, "medbay": 1, "lab": 2},
        ship_modules={"hab": 2, "greenhouse": 2, "lab": 1, "reactor": 1},
        starting_food=8000, ship_food=6000, ship_materials=300,
        build_weights={"lab": 2.0, "reactor": 1.5},
        fertility=0.8, research_rate=1.5,
        starting_techs=("water1", "panels"),
        tech_order=("electro", "led", "robots", "water2", "medicine"),
        prefer_reactors=True,
        strengths=("Storm-proof power", "Rapid technology"), weaknesses=("Small population", "Slow to grow"),
    ),
    Strategy(
        key="industrial", name="Industrial Base",
        tagline="Self-sufficiency focus",
        description="Workshops and ice mines first. Builds its own base instead of waiting for Earth.",
        colonists_per_ship=60,
        starter_modules={"hab": 3, "greenhouse": 4, "lss": 1, "recycler": 1, "ice_mine": 2,
                         "solar": 5, "workshop": 3, "medbay": 1},
        ship_modules={"hab": 2, "greenhouse": 2, "solar": 2},
        starting_food=12000, ship_food=7000, ship_materials=700,
        build_weights={"workshop": 1.5, "ice_mine": 1.4},
        tech_order=("sinter", "robots"),
        build_speed=1.6, build_cost=0.75,
        strengths=("Builds fastest", "Tough to break"), weaknesses=("Less food in reserve",),
    ),
)}

SITES = {s.key: s for s in (
    Site("arcadia", "Arcadia Planitia",
         "Buried ice sheets close to the surface. Average sunshine.",
         solar=0.9, ice=1.5, storms=1.0, radiation=1.0),
    Site("jezero", "Jezero Crater",
         "A sunny ancient river delta, but little accessible ice.",
         solar=1.1, ice=0.6, storms=0.8, radiation=1.0),
    Site("hellas", "Hellas Basin",
         "The deepest basin. Thicker air shields radiation, but global dust storms start here.",
         solar=0.85, ice=1.1, storms=1.8, radiation=0.85),
)}


@dataclass(frozen=True)
class Difficulty:
    key: str
    name: str
    description: str
    disasters: float    # -> SimParams.DISASTER_SCALE
    supplies: float     # -> SimParams.SUPPLY_SCALE


DIFFICULTIES = {d.key: d for d in (
    Difficulty("forgiving", "Forgiving", "Rare disasters and generous supply ships.", 0.4, 1.4),
    Difficulty("realistic", "Realistic", "Mars as best we understand it.", 1.0, 1.0),
    Difficulty("brutal", "Brutal", "Frequent disasters, lost cargo, thin supplies.", 6.0, 0.4),
)}


def get_strategy(strategy):
    return strategy if isinstance(strategy, Strategy) else STRATEGIES[strategy]


def get_site(site):
    return site if isinstance(site, Site) else SITES[site]

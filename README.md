# mars_sim

A simulation of a Martian settlement. Pick a strategy, a landing site and a difficulty,
launch, and watch one connected base grow: ships land colonists and prefab modules, people
work, raise families and die, and the base builds whatever it is shortest of - until it
thrives or runs out of air.

## Run

```
pip install -r requirements.txt
python mars_gui.py
```

Run it from this folder. The window has three tabs once a mission has run:

- **Colony** - a live map of the base. Play, pause, change speed (1 day/s to 2 years/s),
  scrub to any day, switch between runs, and hover over any module for its condition,
  output and crew.
- **Dashboard** - survival, population, Mars-born share, base size, technology and
  self-sufficiency across all runs, plus charts for one run (population, production vs need,
  power, base modules over time, deaths by cause, technology timeline).
- **Mission log** - every landing, disaster, construction, breakthrough and milestone,
  filterable.

Compare every strategy at every site over many runs (survival and final population heatmaps):

```
python sweep.py --difficulty brutal --runs 20
```

Tests (no GUI libraries needed): `python -m unittest discover -s tests`

## The choices

| Strategy | Idea |
|----------|------|
| Balanced Settlement | A bit of everything; builds whatever is short |
| Agricultural Colony | Greenhouses and water first; very hard to starve |
| Frontier Town | 100 colonists a ship and big families; fastest growth, thinnest margins |
| Research Outpost | Small crew, reactors and labs; storm-proof and out-invents its problems |
| Industrial Base | Workshops and ice mines; builds fastest and cheapest |

Each strategy sets the starter base, what every ship carries, build priorities, birth rate
and research order (`strategies.py`).

| Landing site | Sunlight | Ice | Dust storms | Radiation |
|--------------|---------:|----:|------------:|----------:|
| Arcadia Planitia | 90% | 150% | 100% | 100% |
| Jezero Crater | 110% | 60% | 80% | 100% |
| Hellas Basin | 85% | 110% | 180% | 85% |

**Difficulty:** Forgiving (0.4x disasters, 1.4x supplies), Realistic, Brutal (6x disasters,
0.4x supplies - colonies genuinely die). **Advanced:** colonists per ship, time between ships, seed.

## How the base works (`base.py`)

One connected base made of modules:

| Module | Crew | Power | Does |
|--------|-----:|------:|------|
| Habitat | 0 | 6 kW | 20 beds |
| Greenhouse | 3 | 20 kW | 16 rations/day and 8 kg O2/day, transpires 160 L water |
| Life Support | 1 | 20 kW | 25 kg O2/day by electrolysis (uses 28 L water) |
| Water Reclaimer | 1 | 10 kW | Recycles up to 1,500 L/day at 90% (up to 98% with tech) |
| Ice Mine | 3 | 30 kW | 220 L/day of new water (x site ice) |
| Solar Array | 0 | +60 kW | x site sunlight; cut to 35% in dust storms |
| Fission Reactor | 1 | +40 kW | Steady power, expensive |
| Workshop | 4 | 25 kW | 6 materials/day for maintenance and construction |
| Medical Bay | 2 | 10 kW | Cares for 80 people; cuts epidemic and natural deaths |
| Research Lab | 3 | 15 kW | Research points that unlock technologies |

Each person needs 0.84 kg O2, 12 L water and 1 ration a day (children ~60%).

Every day:
1. **Power** is shared in priority order: life support, water, habitats, medical,
   greenhouses, mines, workshops, labs. A storm or a shortfall shuts the least important first.
2. Each module runs at **crew x power x condition**. Working-age adults (16-65) are given jobs
   in priority order; anyone left over builds.
3. **Water**: recycled plus mined; people drink first, then electrolysis, then crops.
4. **Oxygen** and **food** from life support and greenhouses.
5. **Materials** pay for maintenance; unmaintained modules wear out (about 3.4 years to failure).
6. **Research** unlocks 10 technologies in the strategy's order (better recycling, dust-shedding
   panels, efficient electrolysers, Mars-adapted crops, maintenance robots...).

Shortfalls kill: suffocation (oxygen), dehydration, starvation, plus epidemics (worse when
crowded, better with medical cover), accidents (habitat breaches) and natural causes
(`death_prob.csv`). Shortages and crowding also hold back births.

**Disasters:** dust storms (30-120 days), epidemics, equipment failures, hull breaches and lost
cargo ships. **Planner:** every 10 days the base starts building whatever it is shortest of
(beds, food, oxygen, water, power, materials, medical cover, research), weighted by the strategy
and with extra urgency when a reserve will run out within months.

## Files

| File | Purpose |
|------|---------|
| `simulation.py` | The day-by-day model: people, births, deaths, milestones. `simulation(params, seed=...)` |
| `base.py` | Modules, crews, power, water, oxygen, food, materials, research, disasters, the build planner |
| `strategies.py` | Strategies, landing sites and difficulties |
| `colonysim_params.py` | `SimParams`: the launch choices plus a few advanced knobs |
| `colonists.py` | `Astronaut` and `Martian` (born on Mars) |
| `colony_util.py` | Loads the CSV tables and converts annual probabilities to daily ones |
| `analysis.py` | Summaries across runs (survival, self-sufficiency, module counts) |
| `colony_replay.py` | Lays out the base and replays a run as moving colonists (no GUI code) |
| `colony_view.py` | Draws the live base map and its playback bar |
| `dashboard.py` | Dashboard tab (cards + matplotlib charts) |
| `mars_gui.py` / `theme.py` | Main window and its styling |
| `sweep.py` | Strategy x site comparison over many runs |

Positions on the map are cosmetic, but the counts always match the model.

`death_prob.csv` and `preg_prob.csv` are `age,probability` read as **annual** probabilities.
The death table as shipped gives very low natural mortality (about 0.02% a year at age 40);
if the numbers were meant in other units, fix the CSV or set `MORTALITY_SCALE`.

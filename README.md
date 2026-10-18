# mars_sim

A simulation for a Martian settlement. Ships of astronauts arrive from Earth on a
fixed period; colonists age, die, conceive and give birth day by day. Several runs
are plotted together so you can see how much the outcome varies.

## Run

```
pip install -r requirements.txt
python mars_gui.py
```

Run it from this folder. To compare colony designs over many runs (extinction odds and
final population for each ship capacity x arrival period, saved as heatmaps):

```
python sweep.py --capacity 40 80 120 --period 780 1560 --runs 20 --years 30
```

Tests (no GUI libraries needed):

```
python -m unittest discover -s tests
```

## How it works

| File | Purpose |
|------|---------|
| `simulation.py` | The day-by-day model. No GUI dependency; call `simulation(params, progress=None, seed=None)` |
| `colonists.py` | `Astronaut` and `Martian` (born on Mars) |
| `colonysim_params.py` | `SimParams` dataclass holding every tunable number |
| `colony_replay.py` | Turns a run's recorded event log into moving dots (no GUI code, unit tested) |
| `colony_view.py` | Qt widgets that draw the live colony view and its playback controls |
| `analysis.py` | Summary stats across runs (extinction odds, final population, main killer) |
| `sweep.py` | Parameter sweep over ship capacity and arrival period, in parallel |
| `colony_util.py` | Loads the CSV tables once and converts annual probabilities to daily ones |
| `mars_gui.py` / `colonysim.ui` | PyQt5 front end; the simulation runs in a worker thread |

### Colony view

When a run finishes, a live map of the colony opens and starts playing (WATCH COLONY reopens it,
SHOW CHARTS gives the plots). Each ship lands a new habitat dome with a farm beside it; dots are
colonists wandering between home, farm and neighbours.

- Blue = Earth-born, amber = Mars-born, small = children, faded = over 65, pink ring = pregnant
- A white ring marks a birth; a drifting wisp marks a death, coloured by cause
  (grey natural, orange starvation, purple oxygen, green epidemic, red breach)
- Dust storms tint the map and blow dust; epidemics turn dots green; breaches flash a dome red;
  the farm greens with the food supply and the dome turns red as it overcrowds
- Controls: play/pause, speed from 1 day/s to 2 years/s, restart, a scrub slider (drag to any day,
  forwards or backwards), and a run selector. The strip at the bottom is population over time with
  disaster ticks.

Positions are cosmetic: the model has no space, but the dot count always equals the model's population.

### Parameters

| Parameter | Meaning |
|-----------|---------|
| Sim Length | Days simulated |
| Ship Capacity / Arrival Period | Astronauts per ship / days between ships (first ship lands on day 0) |
| M/F Crew Ratio | Male : female ratio of each crew |
| Death Threshold | Age from which natural death is checked (0 = use the whole table) |
| Cooldown | Days after a birth before the mother can conceive again |
| Max Pregnancies | Cap on concurrent pregnancies in the colony |
| New Gen Period / Window | Conceptions can only start during the first *Window* days of each *Period* (set Period <= 0 for always open) |
| Preg Threshold | Days from conception to birth |
| Repro Min / Max Age | Childbearing age range |

The "Resources, Disasters & Runs" block below those has Runs, Seed (set it for reproducible
runs; run *n* uses `SEED + n`), Mortality Scale (multiplies the death rates), and the food,
habitat and disaster numbers. Other values (storm severity, starvation rates, ...) are in `SimParams`.

### Resources and disasters

- **Food:** every landed ship brings a farm (`FOOD_PER_SHIP` a day, for the rest of the sim)
  and some stored supplies. Everyone eats `FOOD_PER_PERSON` a day. When the stock runs out,
  the shortfall raises everyone's death chance (starvation) and suppresses conceptions.
- **Habitat / oxygen:** each ship adds `HAB_PER_SHIP` people of capacity. Overcrowding raises
  the death chance.
- **Disasters** (average events per year): *dust storms* cut farm output for 30-90 days,
  *epidemics* raise everyone's death chance for 20-60 days, *breaches* kill a few people
  and shrink the habitat by 25% for 30 days.
- If the colony dies out it stays dead (no more ships). Deaths are tallied by cause.

With the defaults food sets the carrying capacity, so the colony levels off rather than
growing forever. Set the disaster rates to 0 and the food/habitat numbers high to get the
plain population model back.

### Probability tables

`death_prob.csv` and `preg_prob.csv` are `age,probability` and are read as **annual**
probabilities. The simulation converts them to a per-day chance. The conception
rate is spread over the conception window, so a woman has the annual chance once per window.

The death table as shipped gives very low mortality (about 0.02% a year at age 40).
If the numbers were meant to be something else (per 1000, per day, ...) fix the units
in the CSV or use `MORTALITY_SCALE`.

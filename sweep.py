"""Parameter sweep: how do ship capacity and arrival period change the colony's odds?

    python sweep.py                                   # 4x4 grid, 10 runs per cell
    python sweep.py --capacity 40 80 120 --period 400 780 --runs 20 --years 20
    python sweep.py --out sweep.png --workers 4

Prints a table of extinction probability and median final population for every
combination and saves heatmaps of both. Cells run in parallel, one process per core.
"""

import argparse
import itertools
import statistics
from concurrent.futures import ProcessPoolExecutor

import colonysim_params as ps
import simulation as sim


def run_cell(args):
    """Run one grid cell (capacity, period) `runs` times; returns (capacity, period, extinct, finals)."""
    capacity, period, runs, years, seed = args
    params = ps.SimParams(SHIP_CAPACITY=capacity, ARRIVAL_PERIOD=period, SIM_LENGTH=int(years * 365), RECORD_TIMELINE=False)
    results = [sim.simulation(params, seed=seed + n) for n in range(runs)]
    extinct = sum(r.extinct_day is not None for r in results)
    return capacity, period, extinct, [r.sizes[-1] for r in results]


def sweep(capacities, periods, runs, years, seed, workers):
    cells = [(c, p, runs, years, seed) for c, p in itertools.product(capacities, periods)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return {(c, p): (extinct, finals) for c, p, extinct, finals in pool.map(run_cell, cells)}


def print_table(data, capacities, periods, runs):
    print("\nextinction probability / median final population  (rows: ship capacity, columns: arrival period in days)")
    print("capacity".rjust(9) + "".join(str(p).rjust(16) for p in periods))
    for c in capacities:
        row = str(c).rjust(9)
        for p in periods:
            extinct, finals = data[(c, p)]
            row += "{:.0%} / {:g}".format(extinct / runs, statistics.median(finals)).rjust(16)
        print(row)


def save_heatmaps(data, capacities, periods, runs, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))
    panels = (
        ("Extinction probability", lambda e, f: e / runs, "Reds", 0, 1),
        ("Median final population", lambda e, f: statistics.median(f), "Greens", 0, None),
    )
    for ax, (title, value, cmap, vmin, vmax) in zip(axes, panels):
        grid = [[value(*data[(c, p)]) for p in periods] for c in capacities]
        im = ax.imshow(grid, cmap=cmap, aspect="auto", origin="lower", vmin=vmin, vmax=vmax)
        ax.set_xticks(range(len(periods)), [str(p) for p in periods])
        ax.set_yticks(range(len(capacities)), [str(c) for c in capacities])
        ax.set_xlabel("Arrival period (days)")
        ax.set_ylabel("Ship capacity")
        ax.set_title(title)
        for i, row in enumerate(grid):
            for j, v in enumerate(row):
                ax.text(j, i, "{:.0%}".format(v) if title.startswith("Ext") else "{:g}".format(v),
                        ha="center", va="center", fontsize=9)
        fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print("saved", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--capacity", type=int, nargs="+", default=[20, 40, 80, 120])
    ap.add_argument("--period", type=int, nargs="+", default=[390, 780, 1170, 1560])
    ap.add_argument("--runs", type=int, default=10, help="simulations per cell")
    ap.add_argument("--years", type=float, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=None, help="processes (default: all cores)")
    ap.add_argument("--out", default="sweep.png")
    a = ap.parse_args()

    data = sweep(a.capacity, a.period, a.runs, a.years, a.seed, a.workers)
    print_table(data, a.capacity, a.period, a.runs)
    save_heatmaps(data, a.capacity, a.period, a.runs, a.out)

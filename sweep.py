"""Compare every strategy at every landing site over many runs.

    python sweep.py                                    # all strategies x sites, 10 runs each
    python sweep.py --difficulty brutal --runs 20 --years 40
    python sweep.py --strategies frontier tech --sites hellas --out frontier_vs_tech.png

Prints a table of survival rate and median final population for every combination and
saves heatmaps of both. Runs go in parallel, one process per core.
"""

import argparse
import itertools
import statistics
from concurrent.futures import ProcessPoolExecutor

import colonysim_params as ps
import simulation as sim
import strategies


def run_cell(args):
    """Run one (strategy, site) cell `runs` times; returns (strategy, site, survived, finals)."""
    strategy, site, difficulty, runs, years, seed = args
    d = strategies.DIFFICULTIES[difficulty]
    params = ps.SimParams(STRATEGY=strategy, SITE=site, SIM_LENGTH=int(years * 365),
                          DISASTER_SCALE=d.disasters, SUPPLY_SCALE=d.supplies, RECORD_TIMELINE=False)
    results = [sim.simulation(params, seed=seed + n) for n in range(runs)]
    survived = sum(r.extinct_day is None for r in results)
    return strategy, site, survived, [r.sizes[-1] for r in results]


def sweep(strats, sites, difficulty, runs, years, seed, workers):
    cells = [(s, site, difficulty, runs, years, seed) for s, site in itertools.product(strats, sites)]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return {(s, site): (ok, finals) for s, site, ok, finals in pool.map(run_cell, cells)}


def print_table(data, strats, sites, runs):
    print("\nsurvival / median final population")
    print("".rjust(22) + "".join(strategies.SITES[s].name.rjust(20) for s in sites))
    for s in strats:
        row = strategies.STRATEGIES[s].name.rjust(22)
        for site in sites:
            ok, finals = data[(s, site)]
            row += "{:.0%} / {:,.0f}".format(ok / runs, statistics.median(finals)).rjust(20)
        print(row)


def save_heatmaps(data, strats, sites, runs, path, difficulty):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    panels = (
        ("Survival rate", lambda ok, f: ok / runs, "RdYlGn", 0, 1, "{:.0%}"),
        ("Median final population", lambda ok, f: statistics.median(f), "Greens", 0, None, "{:,.0f}"),
    )
    for ax, (title, value, cmap, vmin, vmax, fmt) in zip(axes, panels):
        grid = [[value(*data[(s, site)]) for site in sites] for s in strats]
        im = ax.imshow(grid, cmap=cmap, aspect="auto", vmin=vmin, vmax=vmax)
        ax.set_xticks(range(len(sites)), [strategies.SITES[s].name for s in sites])
        ax.set_yticks(range(len(strats)), [strategies.STRATEGIES[s].name for s in strats])
        ax.set_title("{} ({}, {} runs each)".format(title, difficulty, runs))
        for i, row in enumerate(grid):
            for j, v in enumerate(row):
                ax.text(j, i, fmt.format(v), ha="center", va="center", fontsize=9)
        fig.colorbar(im, ax=ax)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    print("saved", path)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--strategies", nargs="+", default=list(strategies.STRATEGIES), choices=list(strategies.STRATEGIES))
    ap.add_argument("--sites", nargs="+", default=list(strategies.SITES), choices=list(strategies.SITES))
    ap.add_argument("--difficulty", default="realistic", choices=list(strategies.DIFFICULTIES))
    ap.add_argument("--runs", type=int, default=10, help="simulations per cell")
    ap.add_argument("--years", type=float, default=30)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--workers", type=int, default=None, help="processes (default: all cores)")
    ap.add_argument("--out", default="sweep.png")
    a = ap.parse_args()

    data = sweep(a.strategies, a.sites, a.difficulty, a.runs, a.years, a.seed, a.workers)
    print_table(data, a.strategies, a.sites, a.runs)
    save_heatmaps(data, a.strategies, a.sites, a.runs, a.out, a.difficulty)

"""Dashboard tab: headline cards across all runs plus charts for one run (embedded matplotlib)."""

from PyQt5 import QtCore, QtWidgets

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.figure import Figure

import analysis
from base import MODULE_TYPES, TECHS
from simulation import CAUSES

BG, PANEL, TEXT, MUTED, GRID = "#0f0c0d", "#17131a", "#efe6df", "#9b8f93", "#2c2530"
ACCENT = "#ff7a3d"
MODULE_COLORS = {"hab": "#d9dee6", "greenhouse": "#4fd18b", "lss": "#4aa3ff", "recycler": "#38c9c0",
                 "workshop": "#ff9a4d", "medbay": "#f4a6b0", "lab": "#b48cff", "ice_mine": "#bfe9ff",
                 "solar": "#2f5d9e", "reactor": "#ffd23f"}
CAUSE_COLORS = {"natural": "#8a8a8a", "starvation": "#ff9a3c", "dehydration": "#5ab0ff",
                "suffocation": "#b07cff", "epidemic": "#8dff6a", "accident": "#ff4d4d"}
RESOURCE_COLORS = {"food": "#4fd18b", "water": "#4aa3ff", "o2": "#d9dee6"}


def rolling(values, window=30):
    out, total = [], 0.0
    for i, v in enumerate(values):
        total += v
        if i >= window:
            total -= values[i - window]
        out.append(total / min(i + 1, window))
    return out


class StatCard(QtWidgets.QFrame):

    def __init__(self, title):
        super().__init__()
        self.setObjectName("card")
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)
        t = QtWidgets.QLabel(title.upper())
        t.setObjectName("statTitle")
        self.value = QtWidgets.QLabel("-")
        self.value.setObjectName("statValue")
        self.sub = QtWidgets.QLabel("")
        self.sub.setObjectName("statSub")
        for w in (t, self.value, self.sub):
            layout.addWidget(w)

    def set(self, value, sub="", color=None):
        self.value.setText(value)
        self.value.setStyleSheet("color: {};".format(color) if color else "")
        self.sub.setText(sub)


class Dashboard(QtWidgets.QWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = []
        self.cards = {k: StatCard(t) for k, t in (
            ("survival", "Survival"), ("population", "Final population"), ("mars", "Mars-born"),
            ("base", "Base size"), ("tech", "Technology"), ("self", "Self-sufficiency"))}
        cards = QtWidgets.QHBoxLayout()
        cards.setSpacing(10)
        for c in self.cards.values():
            cards.addWidget(c, 1)

        self.run = QtWidgets.QComboBox()
        self.run.currentIndexChanged.connect(self.draw)
        top = QtWidgets.QHBoxLayout()
        label = QtWidgets.QLabel("CHARTS FOR")
        label.setObjectName("statTitle")
        top.addWidget(label)
        top.addWidget(self.run)
        top.addStretch(1)

        self.figure = Figure(facecolor=BG)
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setStyleSheet("background: {};".format(BG))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.setSpacing(10)
        layout.addLayout(cards)
        layout.addLayout(top)
        layout.addWidget(self.canvas, 1)

    def set_results(self, results):
        self.results = results
        s = analysis.summarize(results)
        good, warn, bad = "#4fd18b", "#ffc04d", "#ff5a5f"
        surv = s["survived"] / s["runs"]
        self.cards["survival"].set("{}/{}".format(s["survived"], s["runs"]),
                                   "colonies made it" if surv == 1 else "median collapse day {:,.0f}".format(
                                       s["median_extinction_day"]) if s["median_extinction_day"] else "",
                                   good if surv == 1 else warn if surv >= 0.5 else bad)
        self.cards["population"].set("{:,.0f}".format(s["final_median"]),
                                     "range {:,} - {:,}".format(s["final_min"], s["final_max"]))
        self.cards["mars"].set("{:.0%}".format(s["mars_born_median"]), "of the final population")
        self.cards["base"].set("{:,.0f}".format(s["modules_median"]), "modules built")
        self.cards["tech"].set("{:.0f}/{}".format(s["techs_median"], s["techs_total"]), "technologies unlocked")
        suf = s["sufficiency"]
        low = min(suf.values())
        self.cards["self"].set("{:.0%}".format(low), "food {:.0%}  water {:.0%}  O2 {:.0%}".format(
            suf["food"], suf["water"], suf["o2"]), good if low >= 0.99 else warn if low > 0.8 else bad)

        self.run.blockSignals(True)
        self.run.clear()
        for n, r in enumerate(results, 1):
            self.run.addItem("Run {}".format(n))
        self.run.blockSignals(False)
        self.draw()

    def _style(self, ax, title):
        ax.set_facecolor(PANEL)
        ax.set_title(title, color=TEXT, fontsize=9.5, loc="left", pad=8, fontweight="bold")
        ax.tick_params(colors=MUTED, labelsize=7.5)
        for spine in ax.spines.values():
            spine.set_color(GRID)
        ax.grid(color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)

    def draw(self):
        if not self.results:
            return
        fig = self.figure
        fig.clear()
        r = self.results[max(0, self.run.currentIndex())]
        years = [d / 365 for d in range(len(r.sizes))]
        axes = fig.subplots(2, 3)
        fig.subplots_adjust(left=0.05, right=0.985, top=0.93, bottom=0.08, wspace=0.22, hspace=0.42)

        ax = axes[0][0]
        self._style(ax, "Population")
        for other in self.results:
            if other is not r:
                ax.plot(years, other.sizes, color=MUTED, alpha=0.35, linewidth=0.9)
        ax.plot(years, r.sizes, color=ACCENT, linewidth=1.8)
        if r.extinct_day is not None:
            ax.axvline(r.extinct_day / 365, color="#ff5a5f", linewidth=1, linestyle="--")
        ax.set_xlabel("years", color=MUTED, fontsize=7.5)

        ax = axes[0][1]
        self._style(ax, "Local production vs need (30-day avg)")
        se = r.series
        for name, made, need in (("food", "food_made", "food_need"), ("water", "water_in", "water_out"),
                                 ("o2", "o2_made", "o2_need")):
            ratio = [min(2.0, m / n) * 100 if n > 0 else 100 for m, n in zip(se[made], se[need])]
            ax.plot(years, rolling(ratio), color=RESOURCE_COLORS[name], linewidth=1.3,
                    label={"o2": "oxygen"}.get(name, name))
        ax.axhline(100, color=TEXT, linewidth=0.8, linestyle="--", alpha=0.5)
        ax.set_ylim(0, 205)
        ax.set_ylabel("%", color=MUTED, fontsize=7.5)
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=7.5, loc="lower right")

        ax = axes[0][2]
        self._style(ax, "Power (kW)")
        ax.fill_between(years, se["power_supply"], color="#ffd23f", alpha=0.25, linewidth=0)
        ax.plot(years, se["power_supply"], color="#ffd23f", linewidth=1.2, label="generated")
        ax.plot(years, se["power_demand"], color=ACCENT, linewidth=1.2, label="demand")
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=7.5, loc="upper left")

        ax = axes[1][0]
        self._style(ax, "Base modules")
        if r.timeline:
            days, counts = analysis.module_counts(r)
            kinds = [k for k in MODULE_TYPES if counts[k][-1] > 0]
            ax.stackplot([d / 365 for d in days], [counts[k] for k in kinds],
                         colors=[MODULE_COLORS[k] for k in kinds],
                         labels=[MODULE_TYPES[k].name for k in kinds], alpha=0.9)
            ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=6.5, loc="upper left", ncol=2)
        ax.set_xlabel("years", color=MUTED, fontsize=7.5)

        ax = axes[1][1]
        self._style(ax, "Deaths by cause (each run)")
        bottom = [0] * len(self.results)
        xs = list(range(1, len(self.results) + 1))
        for cause in CAUSES:
            vals = [res.death_causes[cause] for res in self.results]
            if any(vals):
                ax.bar(xs, vals, bottom=bottom, color=CAUSE_COLORS[cause], label=cause, width=0.65)
                bottom = [b + v for b, v in zip(bottom, vals)]
        ax.set_xticks(xs)
        ax.set_xlabel("run", color=MUTED, fontsize=7.5)
        ax.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=6.5, loc="upper left", ncol=2)
        ax.set_ylim(0, max(bottom + [1]) * 1.35)

        ax = axes[1][2]
        self._style(ax, "Technology unlocked")
        start = list(r.params.strategy.starting_techs)
        unlocked = [(0, t) for t in start] + [(d, t) for d, t in r.techs if d is not None]
        names = [TECHS[t][0] for _, t in unlocked]
        ax.barh(range(len(unlocked)), [d / 365 for d, _ in unlocked], color="#b48cff", height=0.62, alpha=0.35)
        ax.scatter([d / 365 for d, _ in unlocked], range(len(unlocked)), color="#b48cff", s=16, zorder=3)
        for i, name in enumerate(names):
            ax.text(0.15, i, name, va="center", fontsize=7, color=TEXT)
        ax.set_yticks([])
        ax.set_ylim(len(unlocked) - 0.5 if unlocked else 1, -0.6)
        ax.set_xlim(0, len(r.sizes) / 365)
        ax.set_xlabel("year unlocked", color=MUTED, fontsize=7.5)
        self.canvas.draw_idle()

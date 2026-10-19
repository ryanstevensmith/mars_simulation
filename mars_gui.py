"""Mars Colony Simulator - main window.

Pick a strategy, a landing site and a difficulty, launch, then watch the base grow, read the
dashboard and the mission log. Runs are simulated in parallel worker processes.
"""

import sys
from concurrent.futures import ProcessPoolExecutor, as_completed

from PyQt5 import QtCore, QtGui, QtWidgets

import colonysim_params as ps
import simulation as sim
import strategies
import analysis
import theme
from colony_view import ColonyPanel, EVENT_COLORS
from dashboard import Dashboard


class SimWorker(QtCore.QObject):
    """Runs the simulations off the GUI thread (in parallel processes when there are several)."""

    progress = QtCore.pyqtSignal(int, str)        # percent, message
    finished = QtCore.pyqtSignal(list)            # list of SimResult, in run order
    failed = QtCore.pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    @QtCore.pyqtSlot()
    def run(self):
        p = self.params
        seeds = [None if p.SEED is None else p.SEED + n for n in range(p.RUNS)]
        try:
            if p.RUNS == 1:
                result = sim.simulation(p, seed=seeds[0], progress=lambda done, total: self.progress.emit(
                    int(100 * done / total), "Simulating day {:,} of {:,}".format(done, total)))
                self.finished.emit([result])
                return
            results = [None] * p.RUNS
            self.progress.emit(2, "Simulating {} colonies in parallel...".format(p.RUNS))
            with ProcessPoolExecutor() as pool:
                futures = {pool.submit(sim.run_one, (p, s)): n for n, s in enumerate(seeds)}
                for done, future in enumerate(as_completed(futures), 1):
                    results[futures[future]] = future.result()
                    self.progress.emit(int(100 * done / p.RUNS), "{} of {} colonies simulated".format(done, p.RUNS))
            self.finished.emit(results)
        except Exception as e:
            self.failed.emit(str(e))


# ------------------------------------------------------------------ setup panel widgets


def label(text, name):
    w = QtWidgets.QLabel(text)
    w.setObjectName(name)
    w.setWordWrap(True)
    return w


class StrategyCard(QtWidgets.QFrame):
    """One strategy. Compact when not selected; the selected card shows its description."""
    clicked = QtCore.pyqtSignal(str)

    def __init__(self, strategy):
        super().__init__()
        self.key = strategy.key
        self.setObjectName("card")
        self.setCursor(QtCore.Qt.PointingHandCursor)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 9, 12, 9)
        layout.setSpacing(3)
        head = QtWidgets.QHBoxLayout()
        head.addWidget(label(strategy.name, "cardTitle"), 1)
        tag = label(strategy.tagline.upper(), "cardTag")
        tag.setWordWrap(False)
        head.addWidget(tag)
        layout.addLayout(head)
        self.details = QtWidgets.QWidget()
        d = QtWidgets.QVBoxLayout(self.details)
        d.setContentsMargins(0, 2, 0, 0)
        d.setSpacing(3)
        d.addWidget(label(strategy.description, "cardText"))
        d.addWidget(label("+ " + "  ·  ".join(strategy.strengths), "good"))
        d.addWidget(label("− " + "  ·  ".join(strategy.weaknesses), "bad"))
        layout.addWidget(self.details)
        layout.addWidget(label("{} colonists per ship  ·  {} starter modules".format(
            strategy.colonists_per_ship, sum(strategy.starter_modules.values())), "cardText"))

    def set_selected(self, on):
        self.details.setVisible(on)
        self.setProperty("selected", "true" if on else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event):
        self.clicked.emit(self.key)


class Segmented(QtWidgets.QWidget):
    """A row of exclusive toggle buttons, one per option, with a description underneath."""
    changed = QtCore.pyqtSignal(str)

    def __init__(self, options, describe):
        super().__init__()
        self.describe = describe
        self.group = QtWidgets.QButtonGroup(self)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        row = QtWidgets.QHBoxLayout()
        row.setSpacing(6)
        self.buttons = {}
        for key, text in options:
            b = QtWidgets.QPushButton(text)
            b.setCheckable(True)
            b.setCursor(QtCore.Qt.PointingHandCursor)
            self.group.addButton(b)
            row.addWidget(b)
            self.buttons[key] = b
            b.clicked.connect(lambda _, k=key: self.select(k))
        layout.addLayout(row)
        self.info = label("", "muted")
        layout.addWidget(self.info)

    def select(self, key):
        self.key = key
        self.buttons[key].setChecked(True)
        self.info.setText(self.describe(key))
        self.changed.emit(key)


class SetupPanel(QtWidgets.QScrollArea):
    launch = QtCore.pyqtSignal(object)            # SimParams

    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.setMinimumWidth(400)
        self.setMaximumWidth(460)
        inner = QtWidgets.QWidget()
        inner.setObjectName("setup")
        self.setWidget(inner)
        lay = QtWidgets.QVBoxLayout(inner)
        lay.setContentsMargins(18, 18, 18, 18)
        lay.setSpacing(8)

        lay.addWidget(label("MARS COLONY", "title"))
        lay.addWidget(label("Plan a settlement, launch it, and watch it live or die.", "subtitle"))

        lay.addWidget(label("1 · STRATEGY", "section"))
        self.cards = {}
        for s in strategies.STRATEGIES.values():
            card = StrategyCard(s)
            card.clicked.connect(self.select_strategy)
            self.cards[s.key] = card
            lay.addWidget(card)

        lay.addWidget(label("2 · LANDING SITE", "section"))
        self.site = Segmented([(k, s.name) for k, s in strategies.SITES.items()], self.describe_site)
        lay.addWidget(self.site)

        lay.addWidget(label("3 · DIFFICULTY", "section"))
        self.difficulty = Segmented([(k, d.name) for k, d in strategies.DIFFICULTIES.items()],
                                    lambda k: strategies.DIFFICULTIES[k].description)
        lay.addWidget(self.difficulty)

        lay.addWidget(label("4 · MISSION", "section"))
        grid = QtWidgets.QGridLayout()
        grid.setHorizontalSpacing(10)
        self.years = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.years.setRange(5, 60)
        self.years.setValue(30)
        self.years_label = label("30 years", "muted")
        self.years.valueChanged.connect(lambda v: self.years_label.setText("{} years".format(v)))
        self.runs = QtWidgets.QSpinBox()
        self.runs.setRange(1, 12)
        self.runs.setValue(5)
        grid.addWidget(label("Duration", "muted"), 0, 0)
        grid.addWidget(self.years, 0, 1)
        grid.addWidget(self.years_label, 0, 2)
        grid.addWidget(label("Runs to compare", "muted"), 1, 0)
        grid.addWidget(self.runs, 1, 1, 1, 2)
        lay.addLayout(grid)

        self.advanced_toggle = QtWidgets.QPushButton("▸  Advanced")
        self.advanced_toggle.setObjectName("link")
        self.advanced_toggle.setCursor(QtCore.Qt.PointingHandCursor)
        self.advanced = QtWidgets.QWidget()
        adv = QtWidgets.QGridLayout(self.advanced)
        adv.setContentsMargins(0, 0, 0, 0)
        self.colonists = QtWidgets.QSpinBox()
        self.colonists.setRange(0, 500)
        self.colonists.setSpecialValueText("strategy default")
        self.interval = QtWidgets.QSpinBox()
        self.interval.setRange(6, 120)
        self.interval.setValue(26)
        self.interval.setSuffix(" months")
        self.seed = QtWidgets.QLineEdit()
        self.seed.setPlaceholderText("random")
        adv.addWidget(label("Colonists per ship", "muted"), 0, 0)
        adv.addWidget(self.colonists, 0, 1)
        adv.addWidget(label("Time between ships", "muted"), 1, 0)
        adv.addWidget(self.interval, 1, 1)
        adv.addWidget(label("Seed", "muted"), 2, 0)
        adv.addWidget(self.seed, 2, 1)
        self.advanced.setVisible(False)
        self.advanced_toggle.clicked.connect(self.toggle_advanced)
        lay.addWidget(self.advanced_toggle)
        lay.addWidget(self.advanced)

        lay.addSpacing(6)
        self.launch_button = QtWidgets.QPushButton("LAUNCH MISSION")
        self.launch_button.setObjectName("launch")
        self.launch_button.setCursor(QtCore.Qt.PointingHandCursor)
        self.launch_button.clicked.connect(self.on_launch)
        lay.addWidget(self.launch_button)
        self.progress = QtWidgets.QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        self.progress.setVisible(False)
        lay.addWidget(self.progress)
        self.status = label("", "muted")
        lay.addWidget(self.status)
        lay.addStretch(1)

        self.select_strategy("balanced")
        self.site.select("arcadia")
        self.difficulty.select("realistic")

    def describe_site(self, key):
        s = strategies.SITES[key]
        return "{}  Sunlight {:.0%} · ice {:.0%} · storms {:.0%}".format(
            s.description, s.solar, s.ice, s.storms)

    def select_strategy(self, key):
        self.strategy = key
        for k, card in self.cards.items():
            card.set_selected(k == key)

    def toggle_advanced(self):
        on = not self.advanced.isVisible()
        self.advanced.setVisible(on)
        self.advanced_toggle.setText(("▾" if on else "▸") + "  Advanced")

    def params(self):
        seed_text = self.seed.text().strip()
        if seed_text and not seed_text.lstrip("-").isdigit():
            raise ValueError("Seed must be a whole number (or blank for random)")
        d = strategies.DIFFICULTIES[self.difficulty.key]
        p = ps.SimParams(
            STRATEGY=self.strategy, SITE=self.site.key, SIM_LENGTH=self.years.value() * 365,
            RUNS=self.runs.value(), SEED=int(seed_text) if seed_text else None,
            COLONISTS_PER_SHIP=self.colonists.value() or None,
            ARRIVAL_PERIOD=int(round(self.interval.value() * 30.4)),
            DISASTER_SCALE=d.disasters, SUPPLY_SCALE=d.supplies)
        p.validate()
        return p

    def on_launch(self):
        try:
            self.launch.emit(self.params())
        except ValueError as e:
            self.status.setText(str(e))

    def busy(self, on):
        self.launch_button.setEnabled(not on)
        self.launch_button.setText("SIMULATING..." if on else "LAUNCH MISSION")
        self.progress.setVisible(on)
        self.progress.setValue(0)


# ------------------------------------------------------------------ mission log


class MissionLog(QtWidgets.QWidget):
    FILTERS = (("Everything", None), ("Disasters", {"storm", "epidemic", "failure", "breach", "cargo", "extinct"}),
               ("Construction", {"build", "built"}), ("Milestones & tech", {"milestone", "tech", "ship"}))

    def __init__(self):
        super().__init__()
        self.results = []
        self.run = QtWidgets.QComboBox()
        self.filter = QtWidgets.QComboBox()
        for name, _ in self.FILTERS:
            self.filter.addItem(name)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels(["Day", "Year", "Event"])
        self.tree.setRootIsDecorated(False)
        self.tree.setAlternatingRowColors(True)
        self.tree.setColumnWidth(0, 80)
        self.tree.setColumnWidth(1, 60)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(label("RUN", "statTitle"))
        top.addWidget(self.run)
        top.addSpacing(12)
        top.addWidget(label("SHOW", "statTitle"))
        top.addWidget(self.filter)
        top.addStretch(1)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 10)
        layout.addLayout(top)
        layout.addWidget(self.tree, 1)
        self.run.currentIndexChanged.connect(self.fill)
        self.filter.currentIndexChanged.connect(self.fill)

    def set_results(self, results):
        self.results = results
        self.run.blockSignals(True)
        self.run.clear()
        for n in range(len(results)):
            self.run.addItem("Run {}".format(n + 1))
        self.run.blockSignals(False)
        self.fill()

    def fill(self):
        self.tree.clear()
        if not self.results:
            return
        kinds = self.FILTERS[self.filter.currentIndex()][1]
        items = []
        for day, kind, text in self.results[max(0, self.run.currentIndex())].events:
            if kinds and kind not in kinds:
                continue
            item = QtWidgets.QTreeWidgetItem(["{:,}".format(day), "{:.1f}".format(day / 365), text])
            item.setForeground(2, QtGui.QBrush(EVENT_COLORS.get(kind, theme.TEXT)))
            for col in (0, 1):
                item.setForeground(col, QtGui.QBrush(theme.MUTED))
            items.append(item)
        self.tree.addTopLevelItems(items)


# ------------------------------------------------------------------ main window


class MainWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Mars Colony Simulator")
        self.resize(1480, 900)
        self.thread = None
        self.worker = None

        self.setup = SetupPanel()
        self.colony = ColonyPanel()
        self.dashboard = Dashboard()
        self.log = MissionLog()
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self.colony, "Colony")
        self.tabs.addTab(self.dashboard, "Dashboard")
        self.tabs.addTab(self.log, "Mission log")
        for i in (1, 2):
            self.tabs.setTabEnabled(i, False)

        root = QtWidgets.QWidget()
        root.setObjectName("root")
        layout = QtWidgets.QHBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.setup)
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(root)
        self.setup.launch.connect(self.start)

    def start(self, params):
        self.params = params
        self.setup.busy(True)
        self.setup.status.setText("")
        self.colony.set_placeholder("Simulating {} at {}...".format(params.strategy.name, params.site.name))
        self.thread = QtCore.QThread()
        self.worker = SimWorker(params)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.on_progress)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.on_thread_done)
        self.thread.start()

    def on_progress(self, percent, message):
        self.setup.progress.setValue(percent)
        self.setup.status.setText(message)

    def on_failed(self, message):
        self.setup.status.setText("Error: " + message)

    def on_thread_done(self):
        self.setup.busy(False)
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = self.worker = None

    def on_finished(self, results):
        self.setup.status.setText(analysis.describe(analysis.summarize(results)))
        self.colony.set_results(results)
        self.dashboard.set_results(results)
        self.log.set_results(results)
        for i in (1, 2):
            self.tabs.setTabEnabled(i, True)
        self.tabs.setCurrentWidget(self.colony)


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()

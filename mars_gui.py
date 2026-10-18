import sys
from pathlib import Path

from PyQt5 import QtCore, QtWidgets, uic

import matplotlib
matplotlib.use("Qt5Agg")
import matplotlib.pyplot as plt

import simulation as sim
import colonysim_params as ps
import colony_util as util
import analysis
import colony_view

UI_FILE = Path(__file__).resolve().parent / 'colonysim.ui'


class SimWorker(QtCore.QObject):
    """Runs the simulations off the GUI thread; talks back only through signals."""

    progress = QtCore.pyqtSignal(int, int, int)   # run number, days done, total days
    finished = QtCore.pyqtSignal(list)            # list of SimResult
    failed = QtCore.pyqtSignal(str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    @QtCore.pyqtSlot()
    def run(self):
        try:
            results = []
            for n in range(self.params.RUNS):
                seed = None if self.params.SEED is None else self.params.SEED + n
                results.append(sim.simulation(
                    self.params,
                    progress=lambda done, total, n=n: self.progress.emit(n + 1, done, total),
                    seed=seed))
            self.finished.emit(results)
        except Exception as e:
            self.failed.emit(str(e))


class MyWindow(QtWidgets.QMainWindow):

    def __init__(self):
        super(MyWindow, self).__init__()

        self.ui = uic.loadUi(str(UI_FILE), self)
        self.thread = None
        self.worker = None

        # Pre-fill lineEdits with defaults
        defaults = ps.SimParams()
        self.ui.lineEdit_simLength.setText(str(defaults.SIM_LENGTH))
        self.ui.lineEdit_capacity.setText(str(defaults.SHIP_CAPACITY))
        self.ui.lineEdit_arrival.setText(str(defaults.ARRIVAL_PERIOD))
        self.ui.lineEdit_crewRatio.setText(str(defaults.CREW_RATIO))
        self.ui.lineEdit_deathThresh.setText(str(defaults.DEATH_THRESH))
        self.ui.lineEdit_cooldown.setText(str(defaults.COOLDOWN))
        self.ui.lineEdit_maxPreg.setText(str(defaults.MAX_PREG))
        self.ui.lineEdit_newGenPeriod.setText(str(defaults.NEWGEN_PERIOD))
        self.ui.lineEdit_newGenWindow.setText(str(defaults.NEWGEN_WINDOW))
        self.ui.lineEdit_pregThresh.setText(str(defaults.PREG_THRESH))
        self.ui.lineEdit_reproMinAge.setText(str(defaults.PREG_AGE_MIN))
        self.ui.lineEdit_reproMaxAge.setText(str(defaults.PREG_AGE_MAX))

        self.add_extra_fields(defaults)
        self.add_result_buttons()

        # Text change functions
        self.calcYears()
        self.showCrewRatios()
        self.ui.lineEdit_simLength.textChanged.connect(self.calcYears)
        self.ui.lineEdit_capacity.textChanged.connect(self.showCrewRatios)
        self.ui.lineEdit_crewRatio.textChanged.connect(self.showCrewRatios)

        # Button functions
        self.ui.pushButtonStart.clicked.connect(self.pushButtonStartClicked)

    # (attribute, label, SimParams field, type) for the fields added in code below the .ui's own
    EXTRA_FIELDS = (
        ("runs", "Runs", "RUNS", int),
        ("seed", "Seed (blank = random)", "SEED", int),
        ("mortality", "Mortality Scale", "MORTALITY_SCALE", float),
        ("foodPerShip", "Food / Ship / Day", "FOOD_PER_SHIP", float),
        ("shipFood", "Food Stock / Ship", "SHIP_FOOD_STOCK", float),
        ("habPerShip", "Habitat / Ship (people)", "HAB_PER_SHIP", int),
        ("storms", "Dust Storms / Year", "DUST_STORMS_PER_YEAR", float),
        ("breaches", "Breaches / Year", "BREACHES_PER_YEAR", float),
        ("epidemics", "Epidemics / Year", "EPIDEMICS_PER_YEAR", float),
    )

    def add_extra_fields(self, defaults):
        """Add the resource / disaster / run fields to the parameter column (rows 14+ are free)."""
        grid = self.ui.gridLayout
        header = QtWidgets.QLabel("Resources, Disasters & Runs")
        header.setAlignment(QtCore.Qt.AlignCenter)
        font = header.font()
        font.setBold(True)
        header.setFont(font)
        grid.addWidget(header, 14, 0)

        form = QtWidgets.QFormLayout()
        self.extra_edits = {}
        for attr, label, field, _ in self.EXTRA_FIELDS:
            edit = QtWidgets.QLineEdit("" if getattr(defaults, field) is None else str(getattr(defaults, field)))
            self.extra_edits[field] = edit
            form.addRow(label, edit)
        grid.addLayout(form, 15, 0)

    def add_result_buttons(self):
        self.results = None
        self.colony_window = None
        self.watch_button = QtWidgets.QPushButton("WATCH COLONY")
        self.charts_button = QtWidgets.QPushButton("SHOW CHARTS")
        row = QtWidgets.QHBoxLayout()
        row.addWidget(self.watch_button)
        row.addWidget(self.charts_button)
        self.ui.gridLayout.addLayout(row, 45, 0)
        for b in (self.watch_button, self.charts_button):
            b.setEnabled(False)
        self.watch_button.clicked.connect(self.show_colony)
        self.charts_button.clicked.connect(lambda: self.plot(self.results))

    def show_colony(self):
        """Open the animated colony view (it starts playing straight away)."""
        if self.colony_window is not None:
            self.colony_window.close()
        self.colony_window = colony_view.ColonyWindow(self.results, self.params)
        self.colony_window.show()
        self.colony_window.toggle_play()

    def read_params(self):
        """Build a validated SimParams from the form. Raises ValueError on bad input."""
        try:
            params = ps.SimParams(
                SIM_LENGTH=int(self.ui.lineEdit_simLength.text()),
                SHIP_CAPACITY=int(self.ui.lineEdit_capacity.text()),
                ARRIVAL_PERIOD=int(self.ui.lineEdit_arrival.text()),
                CREW_RATIO=float(self.ui.lineEdit_crewRatio.text()),
                DEATH_THRESH=int(self.ui.lineEdit_deathThresh.text()),
                COOLDOWN=int(self.ui.lineEdit_cooldown.text()),
                MAX_PREG=int(self.ui.lineEdit_maxPreg.text()),
                NEWGEN_PERIOD=int(self.ui.lineEdit_newGenPeriod.text()),
                NEWGEN_WINDOW=int(self.ui.lineEdit_newGenWindow.text()),
                PREG_THRESH=int(self.ui.lineEdit_pregThresh.text()),
                PREG_AGE_MIN=int(self.ui.lineEdit_reproMinAge.text()),
                PREG_AGE_MAX=int(self.ui.lineEdit_reproMaxAge.text()),
                **self.read_extra_fields(),
            )
        except ValueError:
            raise ValueError("Every parameter must be a number (whole days/years, ratio can be decimal)")
        params.validate()
        return params

    def read_extra_fields(self):
        values = {}
        for _, _, field, kind in self.EXTRA_FIELDS:
            text = self.extra_edits[field].text().strip()
            values[field] = None if (field == "SEED" and not text) else kind(text)
        return values

    def pushButtonStartClicked(self):
        try:
            params = self.read_params()
        except ValueError as e:
            self.ui.label_progress.setText("Error: " + str(e))
            return

        self.ui.pushButtonStart.setEnabled(False)
        self.ui.listFinalPop.clear()
        self.params = params

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

    def on_progress(self, run, done, total):
        self.ui.label_progress.setText("Run " + str(run) + " of " + str(self.params.RUNS)
                                       + " - progress: " + str(done) + " of " + str(total))

    def on_failed(self, message):
        self.ui.label_progress.setText("Error: " + message)

    def on_thread_done(self):
        self.ui.pushButtonStart.setEnabled(True)
        self.thread.deleteLater()
        self.worker.deleteLater()
        self.thread = None
        self.worker = None

    def on_finished(self, results):
        last = results[-1]
        for x in last.martians:
            self.ui.listFinalPop.addItem(str(x.getAge(last.end_day)) + " " + str(x.getSex()) + ", "
                                         + str(x.getName()) + ", " + str(x.getArrivalDate()))

        self.ui.label_progress.setText("Done: " + analysis.describe(analysis.summarize(results)))
        for day, kind, detail in last.events:
            self.ui.listFinalPop.insertItem(0, "day " + str(day) + ": " + kind + " (" + detail + ")")

        self.results = results
        self.watch_button.setEnabled(True)
        self.charts_button.setEnabled(True)
        self.show_colony()

    def plot(self, results):
        fig, (ax_pop, ax_food, ax_death) = plt.subplots(3, 1, figsize=(9, 10))
        days = range(len(results[0].sizes))

        for r in results:
            ax_pop.plot(days, r.sizes, alpha=0.4)
        ax_pop.plot(days, self.mean_series(results, "sizes"), color="black", linewidth=2, label="mean population")
        ax_pop.plot(days, self.mean_series(results, "habitat"), color="tab:red", linestyle="--", label="habitat capacity")
        for day, kind, _ in results[0].events:
            if kind == "habitat breach":
                ax_pop.axvline(day, color="tab:red", alpha=0.3)
        ax_pop.set_xlabel("Day")
        ax_pop.set_ylabel("Population")
        ax_pop.set_title("Population (thin lines: each run; red ticks: breaches in run 1)")
        ax_pop.legend()

        ax_food.plot(days, self.mean_series(results, "food_satisfaction"), color="tab:green")
        ax_food.set_ylim(0, 1.05)
        ax_food.set_ylabel("Share of food need met (mean)")
        ax_stock = ax_food.twinx()
        ax_stock.plot(days, self.mean_series(results, "food_stock"), color="tab:orange", alpha=0.7)
        ax_stock.set_ylabel("Food stock (mean)", color="tab:orange")
        ax_food.set_xlabel("Day")
        ax_food.set_title("Food")

        causes = sim.CAUSES
        means = [sum(r.death_causes[c] for r in results) / len(results) for c in causes]
        ax_death.bar(causes, means, color="tab:gray")
        ax_death.set_ylabel("Deaths per run (mean)")
        ax_death.set_title("Causes of death")

        fig.tight_layout()
        fig.show()   # non-blocking; plt.show() would start a second event loop

    @staticmethod
    def mean_series(results, name):
        return [sum(getattr(r, name)[d] for r in results) / len(results) for d in range(len(results[0].sizes))]

    def calcYears(self):
        text = self.ui.lineEdit_simLength.text()

        try:
            yrs = int(text) / 365.0
            self.ui.label_simYears.setText("= " + str(round(yrs, 2)) + " years")
        except ValueError:
            self.ui.label_simYears.setText("= N/A")

    def showCrewRatios(self):
        try:
            male_crew, female_crew = util.ratioCalculator(
                int(self.ui.lineEdit_capacity.text()), float(self.ui.lineEdit_crewRatio.text()))
            self.ui.label_crewRatioDisplay.setText(
                "= " + str(male_crew) + " M, " + str(female_crew) + " F crew members")
        except ValueError:
            self.ui.label_crewRatioDisplay.setText("= N/A, set ratio")


if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    window = MyWindow()
    window.show()

    sys.exit(app.exec_())

"""Qt widgets that draw a colony_replay.ReplayState: the animated colony map and its playback window."""

import math
import random

from PyQt5 import QtCore, QtGui, QtWidgets

import colony_replay as rp

# Palette (dark Mars night)
SKY_TOP, SKY_BOTTOM = QtGui.QColor("#140b0a"), QtGui.QColor("#2d1912")
ASTRONAUT = QtGui.QColor("#5ad1ff")
MARTIAN = QtGui.QColor("#ffb84d")
PREGNANT = QtGui.QColor("#ff7bd5")
SICK = QtGui.QColor("#8dff6a")
DOME = QtGui.QColor("#6fd6c9")
OVERCROWDED = QtGui.QColor("#ff5a4d")
FARM_DRY, FARM_LUSH = QtGui.QColor("#6b4a2b"), QtGui.QColor("#4fd16a")
STORM = QtGui.QColor(214, 128, 64)
CAUSE_COLORS = {
    "natural": QtGui.QColor("#c9c9c9"), "starvation": QtGui.QColor("#ff9a3c"),
    "oxygen": QtGui.QColor("#b07cff"), "epidemic": QtGui.QColor("#8dff6a"),
    "breach": QtGui.QColor("#ff4d4d"),
}
TEXT = QtGui.QColor("#f2e6dc")
DIM = QtGui.QColor(242, 230, 220, 150)
SPARK_H = 64

SPEEDS = (("1 day / s", 1), ("1 week / s", 7), ("1 month / s", 30), ("3 months / s", 90),
          ("6 months / s", 180), ("1 year / s", 365), ("2 years / s", 730))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return QtGui.QColor(int(a.red() + (b.red() - a.red()) * t),
                        int(a.green() + (b.green() - a.green()) * t),
                        int(a.blue() + (b.blue() - a.blue()) * t))


def with_alpha(color, alpha):
    c = QtGui.QColor(color)
    c.setAlpha(max(0, min(255, int(alpha))))
    return c


class ColonyView(QtWidgets.QWidget):
    dayChanged = QtCore.pyqtSignal(int)
    playbackEnded = QtCore.pyqtSignal()

    def __init__(self, result, params, parent=None):
        super().__init__(parent)
        self.setMinimumSize(640, 420)
        self.set_run(result, params)
        self.playing = False
        self.days_per_second = 90
        self._last_day = -1
        self._background = None
        self._spark = None
        self._clock = QtCore.QElapsedTimer()
        self._clock.start()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_run(self, result, params):
        self.result = result
        self.params = params
        self.state = rp.ReplayState(result, params)
        self._spark = None
        self._last_day = -1
        self.update()

    # ---------- playback ----------

    def play(self):
        if self.state.finished:
            self.state.reset()
        self.playing = True

    def pause(self):
        self.playing = False

    def restart(self):
        self.state.reset()
        self.update()

    def seek(self, day):
        self.state.seek(day)
        self.update()

    def _tick(self):
        dt = min(self._clock.restart() / 1000.0, 0.1)
        was_finished = self.state.finished
        self.state.advance(dt, self.days_per_second if self.playing else 0)
        if self.playing and self.state.finished and not was_finished:
            self.playing = False
            self.playbackEnded.emit()
        if self.state.day_index != self._last_day:
            self._last_day = self.state.day_index
            self.dayChanged.emit(self._last_day)
        self.update()

    # ---------- geometry ----------

    def _transform(self):
        avail_h = self.height() - SPARK_H - 20
        s = min(self.width() / rp.W, avail_h / rp.H)
        return s, (self.width() - rp.W * s) / 2, (avail_h - rp.H * s) / 2

    def resizeEvent(self, event):
        self._background = None
        self._spark = None
        super().resizeEvent(event)

    def _make_background(self):
        bg = QtGui.QPixmap(self.size())
        p = QtGui.QPainter(bg)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        grad = QtGui.QLinearGradient(0, 0, 0, self.height())
        grad.setColorAt(0, SKY_TOP)
        grad.setColorAt(1, SKY_BOTTOM)
        p.fillRect(self.rect(), grad)
        rng = random.Random(7)
        for _ in range(26):                              # craters and dunes, just for texture
            x, y = rng.uniform(0, self.width()), rng.uniform(0, self.height())
            r = rng.uniform(14, 70)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 190, 150, 14), 1.2))
            p.setBrush(QtGui.QColor(0, 0, 0, 26))
            p.drawEllipse(QtCore.QPointF(x, y), r, r * rng.uniform(0.35, 0.6))
        for _ in range(120):
            p.setPen(QtGui.QColor(255, 220, 190, rng.randint(10, 40)))
            p.drawPoint(rng.randrange(self.width()), rng.randrange(self.height()))
        p.end()
        return bg

    # ---------- painting ----------

    def paintEvent(self, event):
        if self._background is None or self._background.size() != self.size():
            self._background = self._make_background()
        st = self.state
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.drawPixmap(0, 0, self._background)

        pop = st.at(self.result.sizes)
        capacity = st.at(self.result.habitat)
        food = st.at(self.result.food_satisfaction) if pop else 1.0
        crowd = (pop / capacity) if capacity else 0.0

        p.save()
        s, ox, oy = self._transform()
        p.translate(ox + rp.CENTER[0] * s, oy + rp.CENTER[1] * s)      # camera: zoom about the colony
        p.scale(s * st.zoom, s * st.zoom)
        p.translate(-rp.CENTER[0], -rp.CENTER[1])
        self._draw_modules(p, food, crowd)
        self._draw_dots(p, s)
        self._draw_effects(p, s)
        p.restore()

        if st.storm_active:
            self._draw_storm(p)
        self._draw_hud(p, pop, capacity, food, crowd)
        self._draw_sparkline(p)
        p.end()

    def _draw_modules(self, p, food, crowd):
        st = self.state
        r, fr = st.module_radius, st.farm_radius
        dome = mix(DOME, OVERCROWDED, (crowd - 0.85) / 0.3)    # turns red as it fills up
        farm = mix(FARM_DRY, FARM_LUSH, food)
        for k in range(st.modules):
            x, y = st.module_pos(k)
            grad = QtGui.QRadialGradient(x, y, r)
            grad.setColorAt(0, with_alpha(dome, 20))
            grad.setColorAt(0.85, with_alpha(dome, 40))
            grad.setColorAt(1, with_alpha(dome, 120))
            p.setBrush(grad)
            p.setPen(QtGui.QPen(with_alpha(dome, 200), 1.6))
            p.drawEllipse(QtCore.QPointF(x, y), r, r)

            fx, fy = st.farm_pos(k)
            p.setBrush(with_alpha(farm, 190))
            p.setPen(QtGui.QPen(with_alpha(mix(farm, TEXT, 0.4), 220), 1.2))
            p.drawEllipse(QtCore.QPointF(fx, fy), fr, fr)

    def _draw_dots(self, p, scale):
        st = self.state
        clock = st.clock
        p.setPen(QtCore.Qt.NoPen)
        pulse = 0.5 + 0.5 * math.sin(clock * 7)
        for d in st.dots.values():
            if clock < d.appear:
                continue
            age = st.age(d)
            radius = 2.0 + min(age, 18) * 0.09 if age < 18 else 3.6
            color = MARTIAN if d.martian else ASTRONAUT
            if age >= 65:
                color = with_alpha(color, 150)
            if st.infected(d):
                color = mix(color, SICK, 0.55 + 0.4 * pulse)
            p.setBrush(color)
            p.drawEllipse(QtCore.QPointF(d.x, d.y), radius, radius)
            if d.pregnant:
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(PREGNANT, 1.1))
                p.drawEllipse(QtCore.QPointF(d.x, d.y), radius + 2.2, radius + 2.2)
                p.setPen(QtCore.Qt.NoPen)

    def _draw_effects(self, p, scale):
        st = self.state
        for e in st.effects:
            f = e.t / e.dur
            if e.kind == "ghost":                              # a death: a coloured wisp drifting up
                c = with_alpha(CAUSE_COLORS.get(e.data, CAUSE_COLORS["natural"]), 230 * (1 - f))
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(c)
                p.drawEllipse(QtCore.QPointF(e.x, e.y - 14 * f), 3.4 * (1 - 0.5 * f), 3.4 * (1 - 0.5 * f))
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(c, 1.0))
                p.drawEllipse(QtCore.QPointF(e.x, e.y - 14 * f), 3 + 9 * f, 3 + 9 * f)
            elif e.kind == "birth":
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(with_alpha(QtGui.QColor("white"), 230 * (1 - f)), 1.6))
                p.drawEllipse(QtCore.QPointF(e.x, e.y), 3 + 15 * f, 3 + 15 * f)
            elif e.kind == "breach":
                rad = st.module_radius * (1.0 + 0.8 * f)
                p.setBrush(with_alpha(CAUSE_COLORS["breach"], 90 * (1 - f)))
                p.setPen(QtGui.QPen(with_alpha(CAUSE_COLORS["breach"], 255 * (1 - f)), 2.4))
                p.drawEllipse(QtCore.QPointF(e.x, e.y), rad, rad)
            elif e.kind == "ship":
                self._draw_ship(p, e, f)

    def _draw_ship(self, p, e, f):
        drop = (1 - f) ** 2 * 280
        x, y = e.x, e.y - drop
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 170, 70, 200))            # exhaust flame
        flame = QtGui.QPolygonF([QtCore.QPointF(x - 3, y + 6), QtCore.QPointF(x + 3, y + 6),
                                 QtCore.QPointF(x, y + 6 + 16 * (1 - f) + 4)])
        p.drawPolygon(flame)
        p.setBrush(QtGui.QColor("#e9edf2"))                    # hull
        hull = QtGui.QPolygonF([QtCore.QPointF(x, y - 12), QtCore.QPointF(x + 5, y + 6),
                                QtCore.QPointF(x - 5, y + 6)])
        p.drawPolygon(hull)
        if f > 0.8:                                           # touchdown dust
            k = (f - 0.8) / 0.2
            p.setBrush(QtCore.Qt.NoBrush)
            p.setPen(QtGui.QPen(QtGui.QColor(255, 200, 150, int(200 * (1 - k))), 1.5))
            p.drawEllipse(QtCore.QPointF(e.x, e.y), 6 + 26 * k, 3 + 10 * k)

    def _draw_storm(self, p):
        w, h = self.width(), self.height() - SPARK_H
        p.fillRect(0, 0, w, h, with_alpha(STORM, 50))
        clock = self.state.clock
        p.setPen(QtGui.QPen(QtGui.QColor(255, 210, 160, 90), 1.2))
        for i in range(110):                                   # wind-blown dust streaks
            speed = 260 + (i % 7) * 70
            x = (i * 53 + clock * speed) % (w + 40) - 20
            y = (i * 97) % max(1, h)
            p.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x - 16 - (i % 5) * 4, y + 2))

    def _draw_hud(self, p, pop, capacity, food, crowd):
        st = self.state
        w = self.width()
        astronauts, martians = st.counts()
        day = st.day_index

        p.setPen(TEXT)
        font = p.font()
        font.setPointSize(13)
        font.setBold(True)
        p.setFont(font)
        p.drawText(14, 26, "Day {}  -  year {:.1f}".format(day, day / 365.0))
        font.setPointSize(10)
        font.setBold(False)
        p.setFont(font)
        p.drawText(14, 46, "Population {}".format(pop))
        p.setPen(DIM)
        p.drawText(14, 64, "{} astronauts   {} Martian-born".format(astronauts, martians))
        self._legend_dot(p, 14, 82, ASTRONAUT, "Earth-born")
        self._legend_dot(p, 100, 82, MARTIAN, "Mars-born")
        self._legend_dot(p, 182, 82, PREGNANT, "pregnant", ring=True)

        # bars (right): food met, habitat load
        bx = w - 190
        self._bar(p, bx, 18, 170, "Food", food, mix(QtGui.QColor("#ff9a3c"), FARM_LUSH, food))
        self._bar(p, bx, 52, 170, "Habitat {}/{}".format(pop, int(capacity)),
                  min(1.0, crowd), mix(DOME, OVERCROWDED, (crowd - 0.85) / 0.3))

        # banners
        banners = []
        if st.storm_active:
            banners.append(("DUST STORM", STORM))
        if st.epidemic_active:
            banners.append(("EPIDEMIC", SICK))
        if any(e.kind == "breach" for e in st.effects):
            banners.append(("HABITAT BREACH", CAUSE_COLORS["breach"]))
        if st.finished and pop == 0:
            banners.append(("COLONY LOST", OVERCROWDED))
        font.setBold(True)
        font.setPointSize(11)
        p.setFont(font)
        y = 26
        for text, color in banners:
            tw = p.fontMetrics().horizontalAdvance(text)
            p.setPen(color)
            p.drawText(int((w - tw) / 2), y, text)
            y += 20

    def _legend_dot(self, p, x, y, color, label, ring=False):
        p.setBrush(QtCore.Qt.NoBrush if ring else color)
        p.setPen(QtGui.QPen(color, 1.3) if ring else QtCore.Qt.NoPen)
        p.drawEllipse(QtCore.QPointF(x + 4, y - 3), 3.5, 3.5)
        p.setPen(DIM)
        p.drawText(x + 12, y, label)

    def _bar(self, p, x, y, width, label, value, color):
        p.setPen(DIM)
        font = p.font()
        font.setPointSize(8)
        font.setBold(False)
        p.setFont(font)
        p.drawText(x, y + 9, label)
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(255, 255, 255, 30))
        p.drawRoundedRect(QtCore.QRectF(x, y + 14, width, 7), 3, 3)
        p.setBrush(color)
        p.drawRoundedRect(QtCore.QRectF(x, y + 14, max(2.0, width * max(0.0, min(1.0, value))), 7), 3, 3)

    def _draw_sparkline(self, p):
        sizes = self.result.sizes
        left, right = 14, self.width() - 14
        top, bottom = self.height() - SPARK_H + 6, self.height() - 14
        if right - left < 20 or not sizes:
            return
        if self._spark is None:                                # rebuild only when resized / new run
            n = len(sizes)
            peak = max(max(sizes), 1)
            path = QtGui.QPainterPath()
            path.moveTo(left, bottom)
            for px in range(int(right - left) + 1):
                v = sizes[min(n - 1, int(px / max(1, right - left) * (n - 1)))]
                path.lineTo(left + px, bottom - (bottom - top) * v / peak)
            path.lineTo(right, bottom)
            self._spark = (path, peak)
        path, peak = self._spark
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(QtGui.QColor(90, 209, 255, 55))
        p.drawPath(path)
        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(ASTRONAUT, 1.2))
        p.drawPath(path)
        n = len(sizes)
        for day, kind, _ in self.result.events:                # disaster ticks along the bottom
            x = left + (right - left) * day / max(1, n - 1)
            color = {"dust storm": STORM, "epidemic": SICK}.get(kind, CAUSE_COLORS["breach"])
            p.setPen(QtGui.QPen(with_alpha(color, 200), 1.3))
            p.drawLine(QtCore.QPointF(x, bottom), QtCore.QPointF(x, bottom + 5))
        x = left + (right - left) * self.state.day_index / max(1, n - 1)
        p.setPen(QtGui.QPen(QtGui.QColor("white"), 1.5))
        p.drawLine(QtCore.QPointF(x, top - 2), QtCore.QPointF(x, bottom + 5))
        font = p.font()
        font.setPointSize(8)
        p.setFont(font)
        p.setPen(DIM)
        p.drawText(left, top - 2, "population over time (peak {})".format(peak))


class ColonyWindow(QtWidgets.QMainWindow):
    """The colony map plus play / speed / scrub controls."""

    def __init__(self, results, params, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mars Colony - live view")
        self.resize(1040, 760)
        self.results = results
        self.params = params

        self.view = ColonyView(results[0], params)
        self.play_button = QtWidgets.QPushButton("Play")
        self.restart_button = QtWidgets.QPushButton("Restart")
        self.speed = QtWidgets.QComboBox()
        for label, _ in SPEEDS:
            self.speed.addItem(label)
        self.speed.setCurrentIndex(3)
        self.runs = QtWidgets.QComboBox()
        for n, r in enumerate(results, 1):
            self.runs.addItem("Run {} (final pop {})".format(n, r.sizes[-1]))
        self.runs.setVisible(len(results) > 1)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setRange(0, max(0, len(results[0].sizes) - 1))
        self.day_label = QtWidgets.QLabel("day 0")
        self.day_label.setMinimumWidth(70)

        controls = QtWidgets.QHBoxLayout()
        for w in (self.play_button, self.restart_button, self.speed, self.runs):
            controls.addWidget(w)
        controls.addWidget(self.slider, 1)
        controls.addWidget(self.day_label)

        central = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 6)
        layout.addWidget(self.view, 1)
        layout.addLayout(controls)
        self.setCentralWidget(central)

        self.play_button.clicked.connect(self.toggle_play)
        self.restart_button.clicked.connect(self.restart)
        self.speed.currentIndexChanged.connect(self.speed_changed)
        self.runs.currentIndexChanged.connect(self.run_changed)
        self.slider.sliderMoved.connect(self.view.seek)
        self.slider.sliderPressed.connect(self.view.pause)
        self.view.dayChanged.connect(self.on_day)
        self.view.playbackEnded.connect(lambda: self.play_button.setText("Play"))
        self.speed_changed()

    def toggle_play(self):
        if self.view.playing:
            self.view.pause()
            self.play_button.setText("Play")
        else:
            self.view.play()
            self.play_button.setText("Pause")

    def restart(self):
        self.view.restart()
        self.view.play()
        self.play_button.setText("Pause")

    def speed_changed(self):
        self.view.days_per_second = SPEEDS[self.speed.currentIndex()][1]

    def run_changed(self, index):
        self.view.pause()
        self.play_button.setText("Play")
        self.view.set_run(self.results[index], self.params)
        self.slider.setRange(0, max(0, len(self.results[index].sizes) - 1))

    def on_day(self, day):
        self.day_label.setText("day {}".format(day))
        if not self.slider.isSliderDown():
            self.slider.setValue(day)

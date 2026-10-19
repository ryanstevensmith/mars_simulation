"""Qt widgets that draw a colony_replay.ReplayState: the live base map and its playback bar."""

import math
import random

from PyQt5 import QtCore, QtGui, QtWidgets

import colony_replay as rp
from base import MODULE_TYPES, TECHS
import theme

C = QtGui.QColor
CELL = rp.CELL

MODULE_COLORS = {
    "hab": C("#d9dee6"), "greenhouse": C("#4fd18b"), "lss": C("#4aa3ff"), "recycler": C("#38c9c0"),
    "workshop": C("#ff9a4d"), "medbay": C("#f4f4f4"), "lab": C("#b48cff"), "ice_mine": C("#bfe9ff"),
    "solar": C("#2f5d9e"), "reactor": C("#ffd23f"),
}
EARTH = C("#5ad1ff")
MARS = C("#ffb84d")
PREGNANT = C("#ff7bd5")
SICK = C("#8dff6a")
STORM = C(214, 128, 64)
CAUSE_COLORS = {
    "natural": C("#c9c9c9"), "starvation": C("#ff9a3c"), "dehydration": C("#5ab0ff"),
    "suffocation": C("#b07cff"), "epidemic": C("#8dff6a"), "accident": C("#ff4d4d"),
}
EVENT_COLORS = {
    "ship": EARTH, "cargo": C("#ff5a5f"), "storm": C("#e0904a"), "epidemic": SICK, "failure": C("#ffb84d"),
    "breach": C("#ff4d4d"), "built": C("#d9dee6"), "build": C("#9b8f93"), "tech": C("#b48cff"),
    "milestone": C("#ffd23f"), "extinct": C("#ff5a5f"),
}
SPARK_H = 58
HUD_H = 64

SPEEDS = (("1 day / s", 1), ("1 week / s", 7), ("1 month / s", 30), ("3 months / s", 90),
          ("6 months / s", 180), ("1 year / s", 365), ("2 years / s", 730))


def mix(a, b, t):
    t = max(0.0, min(1.0, t))
    return C(int(a.red() + (b.red() - a.red()) * t), int(a.green() + (b.green() - a.green()) * t),
             int(a.blue() + (b.blue() - a.blue()) * t))


def alpha(color, a):
    c = C(color)
    c.setAlpha(max(0, min(255, int(a))))
    return c


def reserve_days(stock, made, need):
    """Days until a stock runs out (None = production covers need)."""
    if made >= need:
        return None
    return stock / (need - made)


class ColonyView(QtWidgets.QWidget):
    dayChanged = QtCore.pyqtSignal(int)
    playbackEnded = QtCore.pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(560, 420)
        self.setMouseTracking(True)
        self.state = None
        self.result = None
        self.playing = False
        self.days_per_second = 90
        self.placeholder = "Choose a strategy and launch a mission"
        self._last_day = -1
        self._background = None
        self._spark = None
        self._hover = None
        self._mouse = None
        self._clock = QtCore.QElapsedTimer()
        self._clock.start()
        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_result(self, result):
        self.result = result
        self.state = rp.ReplayState(result) if result else None
        self._spark = None
        self._last_day = -1
        self.update()

    # ---------- playback ----------

    def play(self):
        if self.state:
            if self.state.finished:
                self.state.reset()
            self.playing = True

    def pause(self):
        self.playing = False

    def restart(self):
        if self.state:
            self.state.reset()

    def seek(self, day):
        if self.state:
            self.state.seek(day)
            self.update()

    def _tick(self):
        dt = min(self._clock.restart() / 1000.0, 0.1)
        st = self.state
        if st is None:
            return
        was_finished = st.finished
        st.advance(dt, self.days_per_second if self.playing else 0)
        if self.playing and st.finished and not was_finished:
            self.playing = False
            self.playbackEnded.emit()
        if st.day_index != self._last_day:
            self._last_day = st.day_index
            self.dayChanged.emit(self._last_day)
        if self.isVisible():
            self.update()

    # ---------- geometry ----------

    def _scale(self):
        avail = self.height() - SPARK_H - HUD_H
        return min(self.width(), avail * 1.6) / 600.0 * (self.state.zoom if self.state else 1.0)

    def _center(self):
        return self.width() / 2, HUD_H + (self.height() - SPARK_H - HUD_H) / 2

    def _to_world(self, px, py):
        s = self._scale()
        cx, cy = self._center()
        return (px - cx) / s, (py - cy) / s

    def resizeEvent(self, event):
        self._background = None
        self._spark = None
        super().resizeEvent(event)

    def mouseMoveEvent(self, event):
        self._mouse = event.pos()
        self._hover = None
        if self.state:
            wx, wy = self._to_world(event.x(), event.y())
            for mid in self.state.modules:
                s = self.state.layout.slots[mid]
                if abs(wx - s.x) <= s.w / 2 and abs(wy - s.y) <= s.h / 2:
                    self._hover = mid
                    break

    def leaveEvent(self, event):
        self._hover = None

    def _make_background(self):
        bg = QtGui.QPixmap(self.size())
        p = QtGui.QPainter(bg)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        grad = QtGui.QRadialGradient(self.width() / 2, self.height() / 2, max(self.width(), self.height()) * 0.75)
        grad.setColorAt(0, C("#4a2619"))
        grad.setColorAt(1, C("#1c0f0b"))
        p.fillRect(self.rect(), grad)
        rng = random.Random(7)
        for _ in range(40):                              # dunes and craters for texture
            x, y = rng.uniform(0, self.width()), rng.uniform(0, self.height())
            r = rng.uniform(16, 90)
            p.setPen(QtGui.QPen(C(255, 190, 150, 12), 1.2))
            p.setBrush(C(0, 0, 0, 22))
            p.drawEllipse(QtCore.QPointF(x, y), r, r * rng.uniform(0.35, 0.6))
        for _ in range(500):
            p.setPen(C(255, 215, 180, rng.randint(8, 30)))
            p.drawPoint(rng.randrange(max(1, self.width())), rng.randrange(max(1, self.height())))
        p.end()
        return bg

    # ---------- painting ----------

    def paintEvent(self, event):
        if self._background is None or self._background.size() != self.size():
            self._background = self._make_background()
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        p.drawPixmap(0, 0, self._background)
        st = self.state
        if st is None:
            p.setPen(theme.MUTED)
            f = p.font()
            f.setPointSize(13)
            p.setFont(f)
            p.drawText(self.rect(), QtCore.Qt.AlignCenter, self.placeholder)
            p.end()
            return

        p.save()
        cx, cy = self._center()
        s = self._scale()
        p.translate(cx, cy)
        p.scale(s, s)
        self._draw_ground(p)
        self._draw_corridors(p)
        self._draw_modules(p, s)
        self._draw_dots(p, s)
        self._draw_effects(p)
        p.restore()

        if st.storm_active:
            self._draw_storm(p)
        self._draw_hud(p)
        self._draw_toasts(p)
        self._draw_hover(p)
        self._draw_sparkline(p)
        p.end()

    def _draw_ground(self, p):
        lay = self.state.layout
        r = lay.core_radius
        grad = QtGui.QRadialGradient(0, 0, r * 1.5)
        grad.setColorAt(0, C(255, 200, 160, 26))
        grad.setColorAt(1, C(255, 200, 160, 0))
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(grad)
        p.drawEllipse(QtCore.QPointF(0, 0), r * 1.5, r * 1.5)
        # rover tracks out to the fields, the reactors, the mines and the landing pad
        pen = QtGui.QPen(C(255, 225, 200, 45), 3.0, QtCore.Qt.DashLine)
        p.setPen(pen)
        targets = [lay.pad]
        for kind in ("solar", "reactor", "ice_mine"):
            spots = [(sl.x, sl.y) for sl in lay.slots.values() if sl.type == kind and sl.mid in self.state.modules]
            if spots:
                targets.append((sum(x for x, _ in spots) / len(spots), sum(y for _, y in spots) / len(spots)))
        for x, y in targets:
            p.drawLine(QtCore.QPointF(0, 0), QtCore.QPointF(x, y))
        # landing pad
        p.setPen(QtGui.QPen(C(255, 255, 255, 60), 2))
        p.setBrush(C(60, 50, 50, 140))
        p.drawEllipse(QtCore.QPointF(*lay.pad), CELL * 0.55, CELL * 0.55)
        p.setPen(QtGui.QPen(C(255, 210, 120, 110), 2))
        p.drawEllipse(QtCore.QPointF(*lay.pad), CELL * 0.3, CELL * 0.3)

    def _draw_corridors(self, p):
        st = self.state
        lay = st.layout
        pen = QtGui.QPen(C("#7d8090"), CELL * 0.24, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
        p.setPen(pen)
        for mid in st.modules:
            s = lay.slots[mid]
            if s.parent is None:
                continue
            px, py = lay.pos(s.parent) if s.parent >= 0 else lay.hub
            p.drawLine(QtCore.QPointF(s.x, s.y), QtCore.QPointF(px, py))
        # cables to the reactors
        p.setPen(QtGui.QPen(C(255, 210, 60, 70), 1.5, QtCore.Qt.DotLine))
        for mid in st.modules:
            s = lay.slots[mid]
            if s.type == "reactor":
                p.drawLine(QtCore.QPointF(s.x, s.y), QtCore.QPointF(-lay.core_radius * 0.7, 0))
        p.setPen(QtGui.QPen(C("#5b5e6b"), 2))
        p.setBrush(C("#b9bcc6"))
        p.drawEllipse(QtCore.QPointF(0, 0), CELL * 0.42, CELL * 0.42)
        p.setBrush(C("#e8eaf0"))
        p.drawEllipse(QtCore.QPointF(0, 0), CELL * 0.18, CELL * 0.18)

    def _draw_modules(self, p, scale):
        st = self.state
        storm = st.storm_active
        blink = 0.5 + 0.5 * math.sin(st.clock * 9)
        for mid, status in st.modules.items():
            s = st.layout.slots[mid]
            cond, eff, progress = st.module_state(mid)
            rect = QtCore.QRectF(s.x - s.w / 2, s.y - s.h / 2, s.w, s.h)
            if status == "building":
                self._draw_construction(p, s, rect, progress)
                continue
            base = MODULE_COLORS[s.type]
            if cond < 0.05:
                base = C("#4a4246")
            self._draw_shape(p, s, rect, base, eff, storm)
            if cond < 0.6:                                         # damage tint, flashing when bad
                a = (0.6 - cond) / 0.6 * (150 + 80 * blink if cond < 0.3 else 140)
                p.setPen(QtGui.QPen(alpha(C("#ff4d4d"), a), 2.2))
                p.setBrush(alpha(C("#ff4d4d"), a * 0.25))
                p.drawRoundedRect(rect.adjusted(-2, -2, 2, 2), 5, 5)
            if mid == self._hover:
                p.setPen(QtGui.QPen(C("white"), 1.6))
                p.setBrush(QtCore.Qt.NoBrush)
                p.drawRoundedRect(rect.adjusted(-3, -3, 3, 3), 6, 6)

    def _draw_shape(self, p, s, rect, color, eff, storm):
        kind = s.type
        glow = 0.35 + 0.65 * eff
        x, y, w, h = s.x, s.y, s.w, s.h
        dark = color.darker(170)
        p.setPen(QtGui.QPen(dark, 1.4))
        if kind == "hab":
            p.setBrush(color)
            p.drawRoundedRect(rect, w * 0.3, h * 0.3)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(alpha(C("#ffcf73"), 255 * glow))
            for dx in (-0.22, 0.22):
                for dy in (-0.22, 0.22):
                    p.drawEllipse(QtCore.QPointF(x + dx * w, y + dy * h), w * 0.09, w * 0.09)
        elif kind == "greenhouse":
            p.setBrush(alpha(mix(C("#24432f"), color, glow), 235))
            p.drawRoundedRect(rect, 4, 4)
            p.setPen(QtGui.QPen(alpha(C("#c8ffd8"), 110 * glow), 1.0))
            for i in (1, 2, 3):
                p.drawLine(QtCore.QPointF(rect.left() + w * i / 4, rect.top() + 3),
                           QtCore.QPointF(rect.left() + w * i / 4, rect.bottom() - 3))
        elif kind in ("lss", "recycler"):
            p.setBrush(color)
            p.drawEllipse(rect)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(alpha(C("white"), 120 + 100 * glow))
            if kind == "lss":
                p.drawEllipse(QtCore.QPointF(x - w * 0.15, y), w * 0.13, w * 0.13)
                p.drawEllipse(QtCore.QPointF(x + w * 0.15, y), w * 0.13, w * 0.13)
            else:
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(alpha(C("white"), 160 * glow + 60), 1.6))
                p.drawEllipse(QtCore.QPointF(x, y), w * 0.24, w * 0.24)
        elif kind == "workshop":
            p.setBrush(color)
            p.drawRect(rect)
            p.setBrush(dark)
            p.setPen(QtCore.Qt.NoPen)
            p.drawRect(rect.adjusted(w * 0.25, h * 0.25, -w * 0.25, -h * 0.25))
            p.setBrush(alpha(C("#fff2d6"), 220 * glow))
            p.drawEllipse(QtCore.QPointF(x, y), w * 0.08, w * 0.08)
        elif kind == "medbay":
            p.setBrush(color)
            p.drawRoundedRect(rect, 4, 4)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(alpha(C("#ff4d5e"), 140 + 115 * glow))
            p.drawRect(QtCore.QRectF(x - w * 0.08, y - h * 0.28, w * 0.16, h * 0.56))
            p.drawRect(QtCore.QRectF(x - w * 0.28, y - h * 0.08, w * 0.56, h * 0.16))
        elif kind == "lab":
            p.setBrush(color)
            pts = [QtCore.QPointF(x + w / 2 * math.cos(math.radians(60 * i + 30)),
                                  y + h / 2 * math.sin(math.radians(60 * i + 30))) for i in range(6)]
            p.drawPolygon(QtGui.QPolygonF(pts))
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(alpha(C("#efe6ff"), 220 * glow))
            p.drawEllipse(QtCore.QPointF(x, y), w * 0.12, w * 0.12)
        elif kind == "ice_mine":
            p.setBrush(color)
            pts = [QtCore.QPointF(x, y - h / 2), QtCore.QPointF(x + w / 2, y),
                   QtCore.QPointF(x, y + h / 2), QtCore.QPointF(x - w / 2, y)]
            p.drawPolygon(QtGui.QPolygonF(pts))
            p.setPen(QtGui.QPen(C("#2b4a5c"), 2.0))
            p.drawLine(QtCore.QPointF(x, y - h * 0.25), QtCore.QPointF(x, y + h * 0.25))
        elif kind == "solar":
            out = 0.35 if storm else 1.0
            p.setBrush(mix(C("#141c2c"), color, out * (0.5 + 0.5 * eff)))
            p.setPen(QtGui.QPen(C("#9fb4d6"), 0.8))
            p.drawRect(rect)
            p.setPen(QtGui.QPen(alpha(C("#9fb4d6"), 90), 0.6))
            for i in (1, 2, 3):
                p.drawLine(QtCore.QPointF(rect.left() + w * i / 4, rect.top()),
                           QtCore.QPointF(rect.left() + w * i / 4, rect.bottom()))
            p.drawLine(QtCore.QPointF(rect.left(), y), QtCore.QPointF(rect.right(), y))
        elif kind == "reactor":
            p.setBrush(C("#2a2a2a"))
            p.drawEllipse(rect)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(alpha(color, 120 + 135 * glow))
            for i in range(3):
                p.drawPie(rect.adjusted(w * 0.12, h * 0.12, -w * 0.12, -h * 0.12), int((90 + 120 * i) * 16), 60 * 16)

    def _draw_construction(self, p, s, rect, progress):
        p.setPen(QtGui.QPen(C(255, 196, 77, 210), 1.4, QtCore.Qt.DashLine))
        p.setBrush(C(255, 196, 77, 35))
        p.drawRect(rect)
        p.setPen(QtGui.QPen(C(255, 196, 77, 120), 1.0))
        p.drawLine(rect.topLeft(), rect.bottomRight())
        p.drawLine(rect.topRight(), rect.bottomLeft())
        p.setPen(QtGui.QPen(C("#ffc44d"), 2.4))
        p.setBrush(QtCore.Qt.NoBrush)
        r = min(s.w, s.h) * 0.3
        p.drawArc(QtCore.QRectF(s.x - r, s.y - r, 2 * r, 2 * r), 90 * 16, int(-360 * 16 * progress))

    def _draw_dots(self, p, scale):
        st = self.state
        clock = st.clock
        grow = max(1.0, 2.4 / (2.9 * scale))         # keep adults at least ~2.4 px across when zoomed out
        p.setPen(QtCore.Qt.NoPen)
        pulse = 0.5 + 0.5 * math.sin(clock * 7)
        for d in st.dots.values():
            if clock < d.appear:
                continue
            age = st.age(d)
            radius = (1.6 + min(age, 18) * 0.07 if age < 18 else 2.9) * grow
            color = MARS if d.martian else EARTH
            if age >= 65:
                color = alpha(color, 150)
            if st.infected(d):
                color = mix(color, SICK, 0.55 + 0.4 * pulse)
            p.setBrush(color)
            p.drawEllipse(QtCore.QPointF(d.x, d.y), radius, radius)
            if d.pregnant:
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(PREGNANT, 0.9))
                p.drawEllipse(QtCore.QPointF(d.x, d.y), radius + 1.8 * grow, radius + 1.8 * grow)
                p.setPen(QtCore.Qt.NoPen)

    def _draw_effects(self, p):
        for e in self.state.effects:
            f = e.t / e.dur
            if e.kind == "ghost":
                c = alpha(CAUSE_COLORS.get(e.data, CAUSE_COLORS["natural"]), 230 * (1 - f))
                p.setPen(QtCore.Qt.NoPen)
                p.setBrush(c)
                p.drawEllipse(QtCore.QPointF(e.x, e.y - 12 * f), 2.8 * (1 - 0.5 * f), 2.8 * (1 - 0.5 * f))
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(c, 0.9))
                p.drawEllipse(QtCore.QPointF(e.x, e.y - 12 * f), 3 + 8 * f, 3 + 8 * f)
            elif e.kind == "birth":
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(alpha(C("white"), 230 * (1 - f)), 1.3))
                p.drawEllipse(QtCore.QPointF(e.x, e.y), 3 + 13 * f, 3 + 13 * f)
            elif e.kind == "built":
                p.setBrush(QtCore.Qt.NoBrush)
                p.setPen(QtGui.QPen(alpha(C("#fff2c4"), 220 * (1 - f)), 2.0))
                p.drawEllipse(QtCore.QPointF(e.x, e.y), CELL * (0.4 + 0.6 * f), CELL * (0.4 + 0.6 * f))
            elif e.kind in ("breach", "failure"):
                color = C("#ff4d4d") if e.kind == "breach" else C("#ffb84d")
                rad = CELL * (0.45 + 0.7 * f)
                p.setBrush(alpha(color, 90 * (1 - f)))
                p.setPen(QtGui.QPen(alpha(color, 255 * (1 - f)), 2.4))
                p.drawEllipse(QtCore.QPointF(e.x, e.y), rad, rad)
            elif e.kind == "ship":
                self._draw_ship(p, e, f)

    def _draw_ship(self, p, e, f):
        drop = (1 - f) ** 2 * 320
        x, y = e.x, e.y - drop
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(C(255, 170, 70, 210))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x - 4, y + 9), QtCore.QPointF(x + 4, y + 9),
                                       QtCore.QPointF(x, y + 9 + 22 * (1 - f) + 5)]))
        p.setBrush(C("#e9edf2"))
        p.drawPolygon(QtGui.QPolygonF([QtCore.QPointF(x, y - 17), QtCore.QPointF(x + 7, y + 9),
                                       QtCore.QPointF(x - 7, y + 9)]))
        if f > 0.8:
            k = (f - 0.8) / 0.2
            p.setBrush(QtCore.Qt.NoBrush)
            p.setPen(QtGui.QPen(C(255, 200, 150, int(200 * (1 - k))), 1.5))
            p.drawEllipse(QtCore.QPointF(e.x, e.y), 8 + 34 * k, 4 + 13 * k)

    def _draw_storm(self, p):
        w, h = self.width(), self.height() - SPARK_H
        p.fillRect(0, 0, w, h, alpha(STORM, 55))
        clock = self.state.clock
        p.setPen(QtGui.QPen(C(255, 210, 160, 90), 1.2))
        for i in range(120):
            speed = 260 + (i % 7) * 70
            x = (i * 53 + clock * speed) % (w + 40) - 20
            y = (i * 97) % max(1, h)
            p.drawLine(QtCore.QPointF(x, y), QtCore.QPointF(x - 16 - (i % 5) * 4, y + 2))

    # ---------- overlays ----------

    def _font(self, p, size, bold=False):
        f = p.font()
        f.setPointSizeF(size)
        f.setBold(bold)
        p.setFont(f)

    def _draw_hud(self, p):
        st = self.state
        w = self.width()
        p.fillRect(QtCore.QRectF(0, 0, w, HUD_H), C(12, 9, 10, 200))
        day = st.day_index
        earth, mars = st.counts()
        pop = len(st.dots)

        self._font(p, 15, True)
        p.setPen(theme.TEXT)
        p.drawText(16, 28, "Day {:,}".format(day))
        self._font(p, 9)
        p.setPen(theme.MUTED)
        p.drawText(16, 47, "Year {:.1f}".format(day / 365.0))

        def status(made, need, stock):
            days = reserve_days(stock, made, need)
            if days is None:
                return "stable", theme.GOOD
            return "{:.0f} days".format(days), theme.WARN if days > 180 else theme.BAD

        se = st.series
        chips = [("POPULATION", "{:,}".format(pop), "{:,} Earth  {:,} Mars".format(earth, mars), EARTH)]
        for name, made, need, stock in (("FOOD", "food_made", "food_need", "food"),
                                        ("WATER", "water_in", "water_out", "water"),
                                        ("OXYGEN", "o2_made", "o2_need", "o2")):
            text, color = status(se(made), se(need), se(stock))
            chips.append((name, text, "{:,.0f} in store".format(se(stock)), color))
        supply, demand = se("power_supply"), se("power_demand")
        pct = supply / demand if demand else 1.0
        chips.append(("POWER", "{:.0f}%".format(min(999, pct * 100)), "{:,.0f} kW made".format(supply),
                      theme.GOOD if pct >= 1 else theme.WARN if pct > 0.8 else theme.BAD))
        beds = se("beds")
        chips.append(("BEDS", "{:,}/{:,}".format(pop, int(beds)), "crowding {:.0%}".format(pop / beds if beds else 0),
                      theme.GOOD if pop <= beds else theme.WARN if pop <= beds * 1.15 else theme.BAD))
        chips.append(("MATERIALS", "{:,.0f}".format(se("materials")), "building {}".format(
            sum(1 for v in st.modules.values() if v == "building")), MODULE_COLORS["workshop"]))
        techs = st.techs
        chips.append(("TECH", "{}/{}".format(techs, len(TECHS)), "research {:.0f}".format(se("research")),
                      MODULE_COLORS["lab"]))

        x = 150
        chip_w = max(92, (w - x - 12) / len(chips))
        for title, value, sub, color in chips:
            if x + chip_w > w + 4:
                break
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(color)
            p.drawRoundedRect(QtCore.QRectF(x, 12, 3, 40), 1.5, 1.5)
            self._font(p, 7.5, True)
            p.setPen(theme.MUTED)
            p.drawText(QtCore.QPointF(x + 10, 21), title)
            self._font(p, 12, True)
            p.setPen(color if color in (theme.GOOD, theme.WARN, theme.BAD) else theme.TEXT)
            p.drawText(QtCore.QPointF(x + 10, 39), value)
            self._font(p, 7.5)
            p.setPen(theme.MUTED)
            p.drawText(QtCore.QPointF(x + 10, 53), sub)
            x += chip_w

        banners = []
        if st.storm_active:
            banners.append(("DUST STORM - SOLAR OUTPUT DOWN", STORM))
        if st.epidemic_active:
            banners.append(("EPIDEMIC", SICK))
        if st.result.extinct_day is not None and day >= st.result.extinct_day:
            banners.append(("COLONY LOST", theme.BAD))
        self._font(p, 10, True)
        y = HUD_H + 24
        for text, color in banners:
            tw = p.fontMetrics().horizontalAdvance(text)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(C(12, 9, 10, 170))
            p.drawRoundedRect(QtCore.QRectF((w - tw) / 2 - 12, y - 16, tw + 24, 24), 12, 12)
            p.setPen(color)
            p.drawText(int((w - tw) / 2), y, text)
            y += 30

        # legend
        self._font(p, 8)
        lx, ly = w - 236, self.height() - SPARK_H - 14
        for color, label, ring in ((EARTH, "Earth-born", False), (MARS, "Mars-born", False),
                                   (PREGNANT, "pregnant", True)):
            p.setBrush(QtCore.Qt.NoBrush if ring else color)
            p.setPen(QtGui.QPen(color, 1.3) if ring else QtCore.Qt.NoPen)
            p.drawEllipse(QtCore.QPointF(lx + 4, ly - 3), 3.5, 3.5)
            p.setPen(theme.MUTED)
            p.drawText(lx + 12, ly, label)
            lx += 78

    def _draw_toasts(self, p):
        st = self.state
        self._font(p, 9)
        y = self.height() - SPARK_H - 18
        for t, kind, text in reversed(st.toasts):
            age = st.clock - t
            a = 1.0 if age < rp.TOAST_TIME - 1 else max(0.0, rp.TOAST_TIME - age)
            color = EVENT_COLORS.get(kind, theme.TEXT)
            tw = p.fontMetrics().horizontalAdvance(text)
            p.setPen(QtCore.Qt.NoPen)
            p.setBrush(C(12, 9, 10, int(180 * a)))
            p.drawRoundedRect(QtCore.QRectF(12, y - 15, tw + 26, 21), 6, 6)
            p.setBrush(alpha(color, 255 * a))
            p.drawEllipse(QtCore.QPointF(22, y - 4.5), 3.5, 3.5)
            p.setPen(alpha(theme.TEXT, 255 * a))
            p.drawText(30, y, text)
            y -= 25

    def _draw_hover(self, p):
        st = self.state
        if self._hover is None or self._mouse is None or self._hover not in st.modules:
            return
        mid = self._hover
        kind = st.module_types[mid]
        cond, eff, progress = st.module_state(mid)
        number = sum(1 for m in range(mid + 1) if st.module_types[m] == kind)
        lines = [MODULE_TYPES[kind].name + " " + str(number)]
        if st.modules[mid] == "building":
            lines.append("Under construction - {:.0%}".format(progress))
        else:
            lines.append("Condition {:.0%}   Output {:.0%}".format(cond, eff))
            if MODULE_TYPES[kind].crew:
                workers = sum(1 for d in st.dots.values() if d.job == mid)
                lines.append("Crew {}/{}".format(workers, MODULE_TYPES[kind].crew))
            if kind == "hab":
                lines.append("Residents {}".format(sum(1 for d in st.dots.values() if d.home == mid)))
        self._font(p, 9)
        fm = p.fontMetrics()
        bw = max(fm.horizontalAdvance(t) for t in lines) + 20
        bh = 18 * len(lines) + 10
        x = min(self._mouse.x() + 16, self.width() - bw - 4)
        y = min(self._mouse.y() + 16, self.height() - bh - 4)
        p.setPen(QtGui.QPen(theme.BORDER, 1))
        p.setBrush(C(20, 16, 18, 235))
        p.drawRoundedRect(QtCore.QRectF(x, y, bw, bh), 6, 6)
        for i, t in enumerate(lines):
            if i == 0:
                self._font(p, 9, True)
            p.setPen(theme.TEXT if i == 0 else theme.MUTED)
            p.drawText(int(x + 10), int(y + 20 + 18 * i), t)
            if i == 0:
                self._font(p, 9)

    def _draw_sparkline(self, p):
        sizes = self.result.sizes
        top, bottom = self.height() - SPARK_H + 8, self.height() - 12
        left, right = 14, self.width() - 14
        p.fillRect(QtCore.QRectF(0, self.height() - SPARK_H, self.width(), SPARK_H), C(12, 9, 10, 210))
        if right - left < 20 or not sizes:
            return
        n = len(sizes)
        if self._spark is None:
            peak = max(max(sizes), 1)
            path = QtGui.QPainterPath()
            path.moveTo(left, bottom)
            for px in range(int(right - left) + 1):
                v = sizes[min(n - 1, int(px / max(1, right - left) * (n - 1)))]
                path.lineTo(left + px, bottom - (bottom - top - 10) * v / peak)
            path.lineTo(right, bottom)
            self._spark = (path, peak)
        path, peak = self._spark
        p.setPen(QtCore.Qt.NoPen)
        p.setBrush(alpha(EARTH, 50))
        p.drawPath(path)
        p.setBrush(QtCore.Qt.NoBrush)
        p.setPen(QtGui.QPen(EARTH, 1.2))
        p.drawPath(path)
        for day, kind, _ in self.result.events:
            if kind in ("storm", "epidemic", "breach", "cargo", "milestone", "tech"):
                x = left + (right - left) * day / max(1, n - 1)
                p.setPen(QtGui.QPen(alpha(EVENT_COLORS[kind], 210), 1.3))
                p.drawLine(QtCore.QPointF(x, bottom), QtCore.QPointF(x, bottom + 5))
        x = left + (right - left) * self.state.day_index / max(1, n - 1)
        p.setPen(QtGui.QPen(C("white"), 1.5))
        p.drawLine(QtCore.QPointF(x, top), QtCore.QPointF(x, bottom + 5))
        self._font(p, 7.5)
        p.setPen(theme.MUTED)
        p.drawText(left, top + 4, "POPULATION  (peak {:,})".format(peak))


class ColonyPanel(QtWidgets.QWidget):
    """The colony map plus play / speed / scrub controls and a run selector."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.results = []
        self.view = ColonyView()
        self.play_button = QtWidgets.QPushButton("Play")
        self.play_button.setObjectName("primarySmall")
        self.restart_button = QtWidgets.QPushButton("Restart")
        self.speed = QtWidgets.QComboBox()
        for label, _ in SPEEDS:
            self.speed.addItem(label)
        self.speed.setCurrentIndex(3)
        self.runs = QtWidgets.QComboBox()
        self.runs.setMinimumWidth(170)
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.day_label = QtWidgets.QLabel("")
        self.day_label.setMinimumWidth(80)
        self.day_label.setObjectName("muted")

        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(10, 6, 10, 8)
        for widget in (self.play_button, self.restart_button, self.speed, self.runs):
            bar.addWidget(widget)
        bar.addWidget(self.slider, 1)
        bar.addWidget(self.day_label)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.view, 1)
        layout.addLayout(bar)

        self.play_button.clicked.connect(self.toggle_play)
        self.restart_button.clicked.connect(self.restart)
        self.speed.currentIndexChanged.connect(self.speed_changed)
        self.runs.currentIndexChanged.connect(self.run_changed)
        self.slider.sliderMoved.connect(self.view.seek)
        self.slider.sliderPressed.connect(self._pause)
        self.view.dayChanged.connect(self.on_day)
        self.view.playbackEnded.connect(lambda: self.play_button.setText("Play"))
        self.speed_changed()
        self._set_enabled(False)

    def _set_enabled(self, on):
        for w in (self.play_button, self.restart_button, self.speed, self.runs, self.slider):
            w.setEnabled(on)

    def set_results(self, results, autoplay=True):
        self.results = results
        self.runs.blockSignals(True)
        self.runs.clear()
        for n, r in enumerate(results, 1):
            fate = "lost day {:,}".format(r.extinct_day) if r.extinct_day is not None else "{:,} people".format(r.sizes[-1])
            self.runs.addItem("Run {} - {}".format(n, fate))
        self.runs.blockSignals(False)
        self.runs.setVisible(len(results) > 1)
        self._set_enabled(True)
        self.run_changed(0)
        if autoplay:
            self.toggle_play()

    def set_placeholder(self, text):
        self.view.placeholder = text
        self.view.update()

    def toggle_play(self):
        if self.view.playing:
            self._pause()
        else:
            self.view.play()
            self.play_button.setText("Pause")

    def _pause(self):
        self.view.pause()
        self.play_button.setText("Play")

    def restart(self):
        self.view.restart()
        self.view.play()
        self.play_button.setText("Pause")

    def speed_changed(self):
        self.view.days_per_second = SPEEDS[self.speed.currentIndex()][1]

    def run_changed(self, index):
        if not self.results:
            return
        self._pause()
        self.view.set_result(self.results[index])
        self.slider.setRange(0, max(0, len(self.results[index].sizes) - 1))

    def on_day(self, day):
        self.day_label.setText("day {:,}".format(day))
        if not self.slider.isSliderDown():
            self.slider.blockSignals(True)
            self.slider.setValue(day)
            self.slider.blockSignals(False)

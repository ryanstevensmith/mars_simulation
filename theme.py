"""Colours and the Qt stylesheet for the whole app (dark 'mission control')."""

from PyQt5 import QtGui

BG = QtGui.QColor("#0f0c0d")
PANEL = QtGui.QColor("#17131a")
CARD = QtGui.QColor("#201b23")
BORDER = QtGui.QColor("#342d38")
TEXT = QtGui.QColor("#efe6df")
MUTED = QtGui.QColor("#9b8f93")
ACCENT = QtGui.QColor("#ff7a3d")
GOOD = QtGui.QColor("#4fd18b")
WARN = QtGui.QColor("#ffc04d")
BAD = QtGui.QColor("#ff5a5f")

STYLESHEET = """
* { font-family: "Segoe UI", "Helvetica Neue", Arial; font-size: 10pt; color: #efe6df; }
QMainWindow, QWidget#root { background: #0f0c0d; }
QWidget#setup { background: #17131a; }
QScrollArea { border: none; background: #17131a; }
QScrollArea > QWidget > QWidget { background: #17131a; }

QLabel#title { font-size: 18pt; font-weight: 700; letter-spacing: 2px; color: #efe6df; }
QLabel#subtitle { color: #9b8f93; font-size: 9pt; }
QLabel#section { color: #ff7a3d; font-size: 8pt; font-weight: 700; letter-spacing: 1.5px; margin-top: 10px; }
QLabel#muted { color: #9b8f93; font-size: 9pt; }
QLabel#statValue { font-size: 18pt; font-weight: 700; }
QLabel#statTitle { color: #9b8f93; font-size: 8pt; font-weight: 700; letter-spacing: 1px; }
QLabel#statSub { color: #9b8f93; font-size: 8.5pt; }

QFrame#card { background: #201b23; border: 1px solid #342d38; border-radius: 10px; }
QFrame#card:hover { border-color: #5a4d5f; }
QFrame#card[selected="true"] { border: 2px solid #ff7a3d; background: #2a1f22; }
QLabel#cardTitle { font-size: 11pt; font-weight: 700; }
QLabel#cardTag { color: #ff7a3d; font-size: 8.5pt; font-weight: 600; }
QLabel#cardText { color: #b5a9ad; font-size: 8.5pt; }
QLabel#good { color: #7fe0a8; font-size: 8.5pt; }
QLabel#bad { color: #ff9a9d; font-size: 8.5pt; }
QLabel#chip { background: #2c2530; border-radius: 8px; padding: 2px 8px; font-size: 8pt; color: #cfc3c7; }
QLabel#chipGood { background: #1d3328; border-radius: 8px; padding: 2px 8px; font-size: 8pt; color: #7fe0a8; }
QLabel#chipBad { background: #3a1f24; border-radius: 8px; padding: 2px 8px; font-size: 8pt; color: #ff9a9d; }

QPushButton { background: #2a2430; border: 1px solid #3d3542; border-radius: 7px; padding: 6px 14px; }
QPushButton:hover { background: #352d3b; }
QPushButton:disabled { color: #6b6266; background: #1f1a22; }
QPushButton:checked { background: #ff7a3d; border-color: #ff7a3d; color: #1a0d07; font-weight: 700; }
QPushButton#launch { background: #ff7a3d; border: none; border-radius: 9px; padding: 12px; font-size: 12pt;
                     font-weight: 800; letter-spacing: 2px; color: #1a0d07; }
QPushButton#launch:hover { background: #ff9259; }
QPushButton#launch:disabled { background: #5a3a2c; color: #1a0d07; }
QPushButton#primarySmall { background: #ff7a3d; border: none; color: #1a0d07; font-weight: 700; min-width: 64px; }
QPushButton#primarySmall:hover { background: #ff9259; }
QPushButton#link { background: transparent; border: none; color: #9b8f93; text-align: left; padding: 4px 0; }
QPushButton#link:hover { color: #efe6df; }

QComboBox, QSpinBox, QLineEdit { background: #201b23; border: 1px solid #3d3542; border-radius: 6px; padding: 4px 8px; }
QComboBox::drop-down { border: none; width: 18px; }
QComboBox QAbstractItemView { background: #201b23; selection-background-color: #ff7a3d; selection-color: #1a0d07; }
QSlider::groove:horizontal { height: 4px; background: #342d38; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ff7a3d; border-radius: 2px; }
QSlider::handle:horizontal { background: #efe6df; width: 14px; height: 14px; margin: -5px 0; border-radius: 7px; }
QProgressBar { background: #201b23; border: none; border-radius: 4px; height: 8px; text-align: center; font-size: 1pt; }
QProgressBar::chunk { background: #ff7a3d; border-radius: 4px; }

QTabWidget::pane { border: none; background: #0f0c0d; }
QTabBar::tab { background: transparent; color: #9b8f93; padding: 10px 18px; font-weight: 600; border: none;
               border-bottom: 2px solid transparent; }
QTabBar::tab:selected { color: #efe6df; border-bottom: 2px solid #ff7a3d; }
QTabBar::tab:hover { color: #efe6df; }

QTreeWidget { background: #141016; border: none; alternate-background-color: #18141b; }
QTreeWidget::item { padding: 4px; }
QHeaderView::section { background: #17131a; color: #9b8f93; border: none; padding: 6px; font-weight: 700; }
QScrollBar:vertical { background: transparent; width: 10px; }
QScrollBar::handle:vertical { background: #3d3542; border-radius: 5px; min-height: 30px; }
QScrollBar::add-line, QScrollBar::sub-line { height: 0; }
QToolTip { background: #201b23; color: #efe6df; border: 1px solid #342d38; }
"""

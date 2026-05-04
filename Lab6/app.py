"""
Lab Task 6 – Reaction Game GUI  (fixed version)
================================================
Fixes applied vs previous version:
  • Countdown display now driven by CD:<n> messages from Arduino
    so it shows the ACTUAL Arduino countdown, not a Qt timer guess.
  • _reset_cd() no longer clobbers style mid-round.
  • RESULT:NONE handled (no crash, no CSV write for nobody).
  • False-start RESULT line uses "−1" strings → clamped safely.
  • Opponent combo in Stats tab updated after every round.

Install:  pip install pyqt6 pyserial matplotlib
Run:      python app.py
"""

import sys, os, csv, glob, statistics
from datetime import datetime

import serial
import serial.tools.list_ports

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QGridLayout, QLabel, QPushButton, QLineEdit, QComboBox,
    QTabWidget, QGroupBox, QScrollArea, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QObject
from PyQt6.QtGui  import QFont



# ─────────────────────────────────────────────
#  PATHS
# ─────────────────────────────────────────────
DATA_DIR  = os.path.join(os.path.dirname(__file__), "player_data")
BAUD_RATE = 9600
os.makedirs(DATA_DIR, exist_ok=True)

# ─────────────────────────────────────────────
#  COLOURS
# ─────────────────────────────────────────────
C = {
    "bg":       "#0F1117",
    "surface":  "#1A1D27",
    "surface2": "#242736",
    "border":   "#2E3347",
    "accent":   "#00D4AA",
    "accent2":  "#FF6B6B",
    "p1":       "#4FC3F7",
    "p2":       "#FFB74D",
    "text":     "#E8EAF6",
    "muted":    "#7B809A",
    "success":  "#69F0AE",
    "warning":  "#FFD740",
    "danger":   "#FF5252",
}

STYLE = f"""
QMainWindow, QWidget {{
    background: {C['bg']}; color: {C['text']};
    font-family: "Courier New", monospace; font-size: 13px;
}}
QTabWidget::pane {{
    border: 1px solid {C['border']}; background: {C['surface']}; border-radius: 6px;
}}
QTabBar::tab {{
    background: {C['surface2']}; color: {C['muted']};
    padding: 8px 20px; border: 1px solid {C['border']};
    border-bottom: none; border-radius: 4px 4px 0 0;
    margin-right: 2px; font-size: 11px; letter-spacing: 1px;
}}
QTabBar::tab:selected {{
    background: {C['surface']}; color: {C['accent']};
    border-bottom: 2px solid {C['accent']};
}}
QPushButton {{
    background: {C['surface2']}; color: {C['text']};
    border: 1px solid {C['border']}; border-radius: 5px;
    padding: 7px 16px; font-family: "Courier New", monospace;
    font-size: 12px; letter-spacing: 1px;
}}
QPushButton:hover  {{ background: {C['border']}; border-color: {C['accent']}; color: {C['accent']}; }}
QPushButton:pressed {{ background: {C['accent']}; color: {C['bg']}; }}
QPushButton:disabled {{ color: {C['muted']}; border-color: {C['border']}; }}
QLineEdit, QComboBox {{
    background: {C['surface2']}; color: {C['text']};
    border: 1px solid {C['border']}; border-radius: 4px;
    padding: 5px 9px; font-family: "Courier New", monospace; font-size: 13px;
}}
QLineEdit:focus, QComboBox:focus {{ border-color: {C['accent']}; }}
QComboBox QAbstractItemView {{
    background: {C['surface2']}; color: {C['text']};
    selection-background-color: {C['border']};
}}
QGroupBox {{
    border: 1px solid {C['border']}; border-radius: 6px;
    margin-top: 14px; padding: 10px;
    font-size: 10px; color: {C['muted']}; letter-spacing: 1px;
}}
QGroupBox::title {{
    subcontrol-origin: margin; left: 10px; padding: 0 4px;
}}
QScrollArea {{ border: none; }}
QLabel {{ background: transparent; }}
"""

# ─────────────────────────────────────────────
#  DATA LAYER
#
#  Storage is per MATCHUP not per player.
#  Files:
#    alice_vs_bob.csv   — one row per completed game for this pairing
#
#  Matchup key is always alphabetically sorted so
#  alice_vs_bob == bob_vs_alice (same file).
#
#  Score rules:
#    Winner of a game  → +1
#    Loser  of a game  → -1  (never below 0)
#
#  Scores are calculated fresh from the CSV every time —
#  no separate JSON file needed.
# ─────────────────────────────────────────────
HEADERS = ["timestamp", "game_num", "winner",
           "p1_reaction_ms", "p2_reaction_ms", "session_id"]

def _safe(name: str) -> str:
    """Clean a name so it is safe to use in a filename."""
    return "".join(c for c in name if c.isalnum() or c in "-_").lower()

def _matchup_key(a: str, b: str) -> str:
    """Always returns names in alphabetical order so A vs B == B vs A."""
    pair = sorted([_safe(a), _safe(b)])
    return f"{pair[0]}_vs_{pair[1]}"

def _csv_path(a: str, b: str) -> str:
    return os.path.join(DATA_DIR, f"{_matchup_key(a, b)}.csv")

# ── GAME HISTORY ──────────────────────────────
def save_game(a: str, b: str, winner_name: str,
              p1_rt: int, p2_rt: int, session_id: str):
    """Append one completed game to the matchup CSV."""
    path   = _csv_path(a, b)
    is_new = not os.path.exists(path)
    game_num = 1
    if not is_new:
        with open(path, newline="") as f:
            game_num = sum(1 for _ in csv.reader(f))  # count rows incl. header
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if is_new:
            w.writerow(HEADERS)
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    game_num, winner_name, p1_rt, p2_rt, session_id])

def load_matchup(a: str, b: str) -> list[dict]:
    """Load full game history for this matchup."""
    path = _csv_path(a, b)
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def calc_scores(a: str, b: str) -> tuple[int, int]:
    """
    Calculate persistent scores directly from the CSV.
    Replay every game in order: winner +1, loser -1 (floor 0).
    Returns (a_score, b_score).
    """
    games   = load_matchup(a, b)
    a_score = 0
    b_score = 0
    for g in games:
        winner = g.get("winner", "").strip().lower()
        if winner == a.lower():
            a_score += 1
            b_score = max(0, b_score - 1)
        elif winner == b.lower():
            b_score += 1
            a_score = max(0, a_score - 1)
    return a_score, b_score

def known_matchups() -> list[str]:
    """Return list of all matchup names from existing CSV files."""
    files = glob.glob(os.path.join(DATA_DIR, "*_vs_*.csv"))
    names = []
    for f in files:
        base = os.path.splitext(os.path.basename(f))[0]
        parts = base.split("_vs_")
        if len(parts) == 2:
            names.append(f"{parts[0].capitalize()} vs {parts[1].capitalize()}")
    return sorted(names)



# ─────────────────────────────────────────────
#  SERIAL WORKER
# ─────────────────────────────────────────────
class SerialWorker(QObject):
    message = pyqtSignal(str)
    lost    = pyqtSignal()

    def __init__(self, port, baud):
        super().__init__()
        self.port = port; self.baud = baud
        self._run = True; self.ser = None

    def run(self):
        try:
            self.ser = serial.Serial(self.port, self.baud, timeout=0.01)
        except serial.SerialException as e:
            self.message.emit(f"ERROR:{e}"); return
        while self._run:
            try:
                if self.ser.in_waiting:
                    line = self.ser.readline().decode("utf-8", errors="ignore").strip()
                    if line:
                        self.message.emit(line)
            except serial.SerialException:
                self.lost.emit(); break

    def send(self, msg: str):
        if self.ser and self.ser.is_open:
            self.ser.write((msg + "\n").encode())

    def stop(self):
        self._run = False
        if self.ser and self.ser.is_open:
            self.ser.close()

# ─────────────────────────────────────────────
#  WIDGET HELPERS
# ─────────────────────────────────────────────
def lbl(text="", size=13, color=None, bold=False):
    w = QLabel(text)
    f = QFont("Courier New", size)
    f.setBold(bold)
    w.setFont(f)
    if color:
        w.setStyleSheet(f"color:{color};")
    return w

# Shared style builders so BigNum never loses its size
def _num_style(color, border_color=None):
    bc = border_color or C["border"]
    return (f"color:{color}; background:{C['surface2']};"
            f"border:1px solid {bc}; border-radius:4px; padding:5px 12px;")

class BigNum(QLabel):
    """Large monospaced readout that can flash its border."""
    def __init__(self, val="---", color=C["accent"], size=26):
        super().__init__(val)
        self._color = color
        self._size  = size
        self.setFont(QFont("Courier New", size, QFont.Weight.Bold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(_num_style(color))

    def set_val(self, v: str):
        self.setText(v)

    def flash(self):
        self.setStyleSheet(_num_style(self._color, C["accent"]))
        QTimer.singleShot(700, lambda: self.setStyleSheet(_num_style(self._color)))

class Dot(QLabel):
    def __init__(self):
        super().__init__("●")
        self.setFont(QFont("Arial", 13))
        self.set(C["muted"])

    def set(self, color: str):
        self.setStyleSheet(f"color:{color};")

class ButtonMap(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedSize(164, 164)
        g = QGridLayout(self)
        g.setSpacing(4)
        self.up    = self._mk("↑")
        self.left  = self._mk("P1")
        self.ctr   = self._mk("●")
        self.right = self._mk("P2")
        self.down  = self._mk("↓")
        g.addWidget(self.up,    0, 1)
        g.addWidget(self.left,  1, 0)
        g.addWidget(self.ctr,   1, 1)
        g.addWidget(self.right, 1, 2)
        g.addWidget(self.down,  2, 1)

    def _mk(self, t):
        w = QLabel(t)
        w.setAlignment(Qt.AlignmentFlag.AlignCenter)
        w.setFixedSize(46, 46)
        w.setStyleSheet(self._idle())
        return w

    @staticmethod
    def _idle():
        return (f"background:{C['surface2']}; border:1px solid {C['border']};"
                f"border-radius:4px; color:{C['muted']}; font-size:12px;")

    @staticmethod
    def _active(color):
        return (f"background:{color}; border:1px solid {color};"
                f"border-radius:4px; color:{C['bg']}; font-size:12px; font-weight:bold;")

    def highlight(self, player: int):
        cell  = self.left if player == 1 else self.right
        color = C["p1"]   if player == 1 else C["p2"]
        cell.setStyleSheet(self._active(color))
        QTimer.singleShot(900, lambda: cell.setStyleSheet(self._idle()))

    def buzz(self):
        self.ctr.setStyleSheet(self._active(C["warning"]))
        QTimer.singleShot(600, lambda: self.ctr.setStyleSheet(self._idle()))



# ─────────────────────────────────────────────
#  COUNTDOWN DISPLAY  (separate widget so it
#  keeps its own style separate from other nums)
# ─────────────────────────────────────────────
class CdDisplay(QLabel):
    _IDLE   = f"color:{C['warning']}; background:{C['surface2']}; border:1px solid {C['border']}; border-radius:4px; padding:5px 12px; font-size:30px; font-weight:bold;"
    _ACTIVE = f"color:{C['warning']}; background:{C['surface2']}; border:1px solid {C['warning']}; border-radius:4px; padding:5px 12px; font-size:30px; font-weight:bold;"
    _GO     = f"color:{C['success']}; background:{C['surface2']}; border:2px solid {C['success']}; border-radius:4px; padding:5px 12px; font-size:30px; font-weight:bold;"

    def __init__(self):
        super().__init__("--")
        self.setFont(QFont("Courier New", 30, QFont.Weight.Bold))
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(self._IDLE)

    def set_countdown(self, n: int):
        self.setText(str(n))
        self.setStyleSheet(self._ACTIVE)

    def set_go(self):
        self.setText("GO!")
        self.setStyleSheet(self._GO)

    def reset(self):
        self.setText("--")
        self.setStyleSheet(self._IDLE)

# ─────────────────────────────────────────────
#  STATISTICS TAB
# ─────────────────────────────────────────────
class StatsTab(QWidget):
    def __init__(self):
        super().__init__()
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        # Matchup selector
        ctrl = QHBoxLayout()
        ctrl.addWidget(lbl("Matchup:", 11, C["muted"]))
        self.m_cb = QComboBox(); self.m_cb.setMinimumWidth(200)
        ctrl.addWidget(self.m_cb)
        ctrl.addStretch()
        rb = QPushButton("REFRESH"); rb.clicked.connect(self.refresh)
        ctrl.addWidget(rb)
        root.addLayout(ctrl)

        # Persistent score display
        score_box = QGroupBox("Persistent scores  (winner +1 / loser −1, floor 0)")
        score_lay = QHBoxLayout(score_box)
        self.p1_score_name = lbl("P1", 13, C["p1"], bold=True)
        self.p1_score_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.p1_score_val  = BigNum("0", C["p1"], 32)
        self.p2_score_name = lbl("P2", 13, C["p2"], bold=True)
        self.p2_score_name.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.p2_score_val  = BigNum("0", C["p2"], 32)
        vs_lbl = lbl("VS", 13, C["muted"], bold=True)
        vs_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pv1 = QVBoxLayout(); pv1.addWidget(self.p1_score_name); pv1.addWidget(self.p1_score_val)
        pv2 = QVBoxLayout(); pv2.addWidget(self.p2_score_name); pv2.addWidget(self.p2_score_val)
        score_lay.addLayout(pv1)
        score_lay.addWidget(vs_lbl)
        score_lay.addLayout(pv2)
        root.addWidget(score_box)

        # Game history table
        hist_box = QGroupBox("Game history")
        hist_lay = QVBoxLayout(hist_box)

        # Table header
        hdr = QHBoxLayout()
        for text, width in [("Game", 60), ("Winner", 120),
                             ("P1 reaction", 120), ("P2 reaction", 120),
                             ("Date", 180)]:
            h = lbl(text, 10, C["muted"], bold=True)
            h.setFixedWidth(width)
            hdr.addWidget(h)
        hdr.addStretch()
        hist_lay.addLayout(hdr)

        # Divider
        line = QWidget(); line.setFixedHeight(1)
        line.setStyleSheet(f"background:{C['border']};")
        hist_lay.addWidget(line)

        # Scrollable rows area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMinimumHeight(200)
        self._rows_widget = QWidget()
        self._rows_layout = QVBoxLayout(self._rows_widget)
        self._rows_layout.setSpacing(2)
        self._rows_layout.addStretch()
        self._scroll.setWidget(self._rows_widget)
        hist_lay.addWidget(self._scroll)
        root.addWidget(hist_box)

        # Summary line
        self.summary = lbl("Select a matchup and press REFRESH.", 11, C["muted"])
        self.summary.setWordWrap(True)
        root.addWidget(self.summary)

        self.reload_matchups()

    def reload_matchups(self):
        cur = self.m_cb.currentText()
        self.m_cb.clear()
        for m in known_matchups():
            self.m_cb.addItem(m)
        idx = self.m_cb.findText(cur)
        if idx >= 0:
            self.m_cb.setCurrentIndex(idx)

    def add_matchup(self, a: str, b: str):
        label = f"{a.capitalize()} vs {b.capitalize()}"
        if self.m_cb.findText(label) < 0:
            self.m_cb.addItem(label)

    def refresh(self):
        self.reload_matchups()
        matchup = self.m_cb.currentText()
        if not matchup or " vs " not in matchup:
            return

        parts = matchup.split(" vs ")
        a, b  = parts[0].strip(), parts[1].strip()

        # ── Scores — calculated fresh from CSV, no JSON needed ───────────────
        a_score, b_score = calc_scores(a, b)
        self.p1_score_name.setText(a)
        self.p2_score_name.setText(b)
        self.p1_score_val.set_val(str(a_score))
        self.p2_score_val.set_val(str(b_score))

        # ── Game history rows ─────────────────────────────────────────────────
        games = load_matchup(a, b)

        # Clear existing rows
        while self._rows_layout.count() > 1:  # keep the stretch at end
            item = self._rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        p1_rts, p2_rts = [], []
        a_wins = b_wins = 0

        for i, g in enumerate(games, 1):
            winner  = g.get("winner", "?")
            p1rt_s  = g.get("p1_reaction_ms", "0")
            p2rt_s  = g.get("p2_reaction_ms", "0")
            ts      = g.get("timestamp", "")[:19]  # trim to seconds

            try: p1rt = int(p1rt_s)
            except ValueError: p1rt = 0
            try: p2rt = int(p2rt_s)
            except ValueError: p2rt = 0

            if p1rt > 0: p1_rts.append(p1rt)
            if p2rt > 0: p2_rts.append(p2rt)
            if winner.lower() == a.lower(): a_wins += 1
            elif winner.lower() == b.lower(): b_wins += 1

            # Colour the row by winner
            row_color = C["p1"] if winner.lower() == a.lower() else C["p2"]

            row = QHBoxLayout()
            for text, width in [
                (str(i),                         60),
                (winner,                        120),
                (f"{p1rt}ms" if p1rt else "—", 120),
                (f"{p2rt}ms" if p2rt else "—", 120),
                (ts,                            180),
            ]:
                cell = lbl(text, 11, row_color if text == winner else C["text"])
                cell.setFixedWidth(width)
                row.addWidget(cell)
            row.addStretch()

            container = QWidget()
            container.setLayout(row)
            container.setStyleSheet(
                f"background:{C['surface2']}; border-radius:4px; padding:2px;")
            self._rows_layout.insertWidget(self._rows_layout.count()-1, container)

        if not games:
            self._rows_layout.insertWidget(
                0, lbl("No games played yet.", 11, C["muted"]))

        # ── Summary ───────────────────────────────────────────────────────────
        total = len(games)
        avg1  = int(statistics.mean(p1_rts)) if p1_rts else 0
        avg2  = int(statistics.mean(p2_rts)) if p2_rts else 0
        self.summary.setText(
            f"  {a} vs {b}  ·  {total} games played  ·  "
            f"{a}: {a_wins} wins, avg {avg1}ms  ·  "
            f"{b}: {b_wins} wins, avg {avg2}ms"
        )

# ─────────────────────────────────────────────
#  GAME TAB
# ─────────────────────────────────────────────
class GameTab(QWidget):
    round_done = pyqtSignal(str, str)   # p1_name, p2_name

    def __init__(self):
        super().__init__()
        self._worker = None
        self._thread = None
        self.p1 = self.p2 = ""
        self.p1w = self.p2w = 0
        self.rnd = self.samples = 0
        self.session = ""
        self.active  = False
        self.last_p1rt = 0   # last valid reaction time in ms — saved at game over
        self.last_p2rt = 0
        self._build()

    # ── BUILD UI ─────────────────────────────────────────────────────────────
    def _build(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # Row 1: port / names / buttons
        r1 = QHBoxLayout()

        pb = QGroupBox("Serial port")
        pl = QHBoxLayout(pb)
        self.port_cb = QComboBox(); self._fill_ports()
        pl.addWidget(self.port_cb)
        self.conn_btn = QPushButton("CONNECT")
        self.conn_btn.clicked.connect(self._connect)
        pl.addWidget(self.conn_btn)
        self.conn_dot = Dot()
        pl.addWidget(self.conn_dot)
        r1.addWidget(pb)

        nb = QGroupBox("Players")
        ng = QGridLayout(nb)
        ng.addWidget(lbl("P1:", 11, C["p1"]), 0, 0)
        self.p1_in = QLineEdit("Alice"); self.p1_in.setMaximumWidth(120)
        ng.addWidget(self.p1_in, 0, 1)
        ng.addWidget(lbl("P2:", 11, C["p2"]), 0, 2)
        self.p2_in = QLineEdit("Bob"); self.p2_in.setMaximumWidth(120)
        ng.addWidget(self.p2_in, 0, 3)
        r1.addWidget(nb)

        self.start_btn = QPushButton("▶  START")
        self.start_btn.setMinimumHeight(44)
        self.start_btn.setEnabled(False)
        self.start_btn.clicked.connect(self._start)
        self.start_btn.setStyleSheet(
            f"QPushButton{{background:{C['accent']};color:{C['bg']};border:none;"
            f"border-radius:5px;font-size:13px;font-weight:bold;letter-spacing:2px;}}"
            f"QPushButton:hover{{background:{C['success']};}}"
            f"QPushButton:disabled{{background:{C['surface2']};color:{C['muted']};}}")
        r1.addWidget(self.start_btn)

        self.stop_btn = QPushButton("■  STOP")
        self.stop_btn.setMinimumHeight(44)
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self._stop)
        self.stop_btn.setStyleSheet(
            f"QPushButton{{background:{C['danger']};color:#fff;border:none;"
            f"border-radius:5px;font-size:13px;font-weight:bold;}}"
            f"QPushButton:hover{{background:{C['accent2']};}}"
            f"QPushButton:disabled{{background:{C['surface2']};color:{C['muted']};}}")
        r1.addWidget(self.stop_btn)
        root.addLayout(r1)

        # Row 2: state+cd | data | score+map
        r2 = QHBoxLayout()

        # LEFT col
        lc = QVBoxLayout()
        sb = QGroupBox("Game state")
        sl = QVBoxLayout(sb)
        self.state_lbl = lbl("WAITING", 18, C["muted"], bold=True)
        self.state_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(self.state_lbl)
        self.state_dot = Dot()
        self.state_dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.addWidget(self.state_dot)
        lc.addWidget(sb)

        cdb = QGroupBox("Countdown")
        cdl = QVBoxLayout(cdb)
        self.cd = CdDisplay()
        cdl.addWidget(self.cd)
        lc.addWidget(cdb)
        r2.addLayout(lc)

        # CENTRE: data
        db = QGroupBox("Data")
        dg = QGridLayout(db)
        dg.addWidget(lbl("P1 reaction", 10, C["p1"]), 0, 0)
        self.rt1 = BigNum("---", C["p1"])
        dg.addWidget(self.rt1, 1, 0)
        dg.addWidget(lbl("P2 reaction", 10, C["p2"]), 0, 1)
        self.rt2 = BigNum("---", C["p2"])
        dg.addWidget(self.rt2, 1, 1)
        dg.addWidget(lbl("Sample #", 10, C["muted"]), 2, 0)
        self.s_num = BigNum("0", C["muted"], 18)
        dg.addWidget(self.s_num, 3, 0)
        dg.addWidget(lbl("Round", 10, C["muted"]), 2, 1)
        self.r_num = BigNum("0", C["muted"], 18)
        dg.addWidget(self.r_num, 3, 1)
        r2.addWidget(db, stretch=2)

        # RIGHT col: score + button map
        rc = QVBoxLayout()
        scb = QGroupBox("Score  (first to 3)")
        scl = QHBoxLayout(scb)
        self.p1nl = lbl("P1", 11, C["p1"], bold=True)
        self.p1nl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sc1  = BigNum("0", C["p1"], 34)
        self.p2nl = lbl("P2", 11, C["p2"], bold=True)
        self.p2nl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.sc2  = BigNum("0", C["p2"], 34)
        vs = lbl("VS", 13, C["muted"], bold=True)
        vs.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pv1 = QVBoxLayout(); pv1.addWidget(self.p1nl); pv1.addWidget(self.sc1)
        pv2 = QVBoxLayout(); pv2.addWidget(self.p2nl); pv2.addWidget(self.sc2)
        scl.addLayout(pv1); scl.addWidget(vs); scl.addLayout(pv2)
        rc.addWidget(scb)

        bmpb = QGroupBox("Button mapping")
        bmpl = QVBoxLayout(bmpb)
        bmpl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bmap = ButtonMap()
        bmpl.addWidget(self.bmap)
        rc.addWidget(bmpb)
        r2.addLayout(rc)
        root.addLayout(r2)

        # Row 3: serial log
        logb = QGroupBox("Serial log")
        logl = QVBoxLayout(logb)
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setMaximumHeight(100)
        inner = QWidget()
        self._loglyt = QVBoxLayout(inner)
        self._loglyt.setSpacing(1)
        self._loglyt.addStretch()
        self._scroll.setWidget(inner)
        logl.addWidget(self._scroll)
        root.addWidget(logb)

    # ── SERIAL ───────────────────────────────────────────────────────────────
    def _fill_ports(self):
        self.port_cb.clear()
        ports = serial.tools.list_ports.comports()
        for p in ports:
            self.port_cb.addItem(p.device)
        if not ports:
            self.port_cb.addItem("No ports found")

    def _connect(self):
        port = self.port_cb.currentText()
        if "No ports" in port:
            return
        self._thread = QThread()
        self._worker = SerialWorker(port, BAUD_RATE)
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.message.connect(self._on_msg)
        self._worker.lost.connect(lambda: (
            self.conn_dot.set(C["danger"]),
            self._log("!! Disconnected")))
        self._thread.start()
        self.conn_dot.set(C["warning"])
        self.conn_btn.setEnabled(False)
        self._log(f"Connecting → {port}")

    def _send(self, msg: str):
        if self._worker:
            self._worker.send(msg)

    # ── HANDLE ARDUINO MESSAGES ───────────────────────────────────────────────
    def _on_msg(self, msg: str):
        self._log(f"← {msg}")

        # ── READY ────────────────────────────────────────────────────────────
        if msg == "READY":
            self.conn_dot.set(C["success"])
            self.start_btn.setEnabled(True)

        # ── ROUND_START ───────────────────────────────────────────────────────
        elif msg == "ROUND_START":
            self._set_state("COUNTDOWN", C["warning"])
            self.cd.reset()          # clear to "--" until first CD: arrives
            self.rt1.set_val("---")
            self.rt2.set_val("---")

        # ── CD:<n>  (countdown tick from Arduino) ─────────────────────────────
        elif msg.startswith("CD:"):
            try:
                n = int(msg[3:])
                self.cd.set_countdown(n)
            except ValueError:
                pass

        # ── BUZZ ──────────────────────────────────────────────────────────────
        elif msg == "BUZZ":
            self.cd.set_go()
            self._set_state("REACT!", C["danger"])
            self.bmap.buzz()
            self.samples += 1
            self.s_num.set_val(str(self.samples))

        # ── FALSE:<player> ────────────────────────────────────────────────────
        elif msg.startswith("FALSE:"):
            try:
                loser = int(msg.split(":")[1])
            except (ValueError, IndexError):
                loser = 0
            name = self.p1 if loser == 1 else self.p2
            self._set_state(f"FALSE – {name.upper()}", C["danger"])
            if loser in (1, 2):
                self.bmap.highlight(loser)
            self.cd.reset()

        # ── RESULT ────────────────────────────────────────────────────────────
        # Format: RESULT:<winner>,<p1ms>,<p2ms>,<p1wins>,<p2wins>,<NORMAL|FALSE>
        elif msg.startswith("RESULT:"):
            parts = msg[7:].split(",")
            if len(parts) == 6:
                winner, p1ms_s, p2ms_s, p1w_s, p2w_s, round_type = parts
            elif len(parts) == 5:
                # backwards compat with old firmware
                winner, p1ms_s, p2ms_s, p1w_s, p2w_s = parts
                round_type = "NORMAL"
            else:
                round_type = "NORMAL"

            if len(parts) >= 5:
                def _si(s):
                    try:
                        return int(s.strip().replace("−", "-"))
                    except ValueError:
                        return -1

                p1ms = _si(p1ms_s)
                p2ms = _si(p2ms_s)
                p1w  = _si(p1w_s)
                p2w  = _si(p2w_s)
                is_false_start = (round_type.strip() == "FALSE")

                # Always update score display — false starts DO change scores
                if p1w >= 0: self.p1w = p1w
                if p2w >= 0: self.p2w = p2w
                self.sc1.set_val(str(self.p1w))
                self.sc2.set_val(str(self.p2w))

                # Only increment round counter and save CSV for real rounds
                if not is_false_start:
                    self.rnd += 1
                    self.r_num.set_val(str(self.rnd))

                    if p1ms > 0:
                        self.rt1.set_val(f"{p1ms}ms")
                        self.rt1.flash()
                        self.last_p1rt = p1ms   # store as int for game-over save
                    if p2ms > 0:
                        self.rt2.set_val(f"{p2ms}ms")
                        self.rt2.flash()
                        self.last_p2rt = p2ms   # store as int for game-over save

                    # Button map flash for winner
                    if winner in ("1", "2"):
                        self.bmap.highlight(int(winner))

                    # CSV is saved per GAME at GAME_OVER, not per round
                    self.round_done.emit(self.p1, self.p2)

                    self._set_state("ROUND DONE", C["accent"])
                else:
                    # False start — score updated above, but state already
                    # set by FALSE: message handler. Just flash the winner side.
                    if winner in ("1", "2"):
                        self.bmap.highlight(int(winner))

                self.cd.reset()

        # ── GAME_OVER ─────────────────────────────────────────────────────────
        elif msg.startswith("GAME_OVER:"):
            wname = msg[10:]
            self._set_state(f"  {wname.upper()} WINS!", C["success"])
            self.state_dot.set(C["success"])
            self.start_btn.setEnabled(True)
            self.stop_btn.setEnabled(False)
            self.active = False

            # Save game record and update persistent scores
            # Use stored integer values — not label text which may be "---"
            save_game(self.p1, self.p2, wname,
                      self.last_p1rt, self.last_p2rt, self.session)
            a_score, b_score = calc_scores(self.p1, self.p2)
            p1_sc = a_score if _safe(self.p1) <= _safe(self.p2) else b_score
            p2_sc = b_score if _safe(self.p1) <= _safe(self.p2) else a_score

            self.round_done.emit(self.p1, self.p2)

            QMessageBox.information(
                self, "Game Over",
                f"  {wname} wins the game!\n\n"
                f"{self.p1}: {self.p1w} round wins\n"
                f"{self.p2}: {self.p2w} round wins\n\n"
                f"── Persistent scores ──\n"
                f"{self.p1}: {p1_sc}  |  {self.p2}: {p2_sc}"
            )

    # ── GAME CONTROL ─────────────────────────────────────────────────────────
    def _start(self):
        self.p1 = self.p1_in.text().strip() or "Player1"
        self.p2 = self.p2_in.text().strip() or "Player2"
        self.p1nl.setText(self.p1); self.p2nl.setText(self.p2)
        self.p1w = self.p2w = 0
        self.rnd = self.samples = 0
        self.last_p1rt = 0
        self.last_p2rt = 0
        self.session = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.sc1.set_val("0"); self.sc2.set_val("0")
        self.r_num.set_val("0"); self.s_num.set_val("0")
        self.rt1.set_val("---"); self.rt2.set_val("---")
        self.cd.reset()
        self.active = True
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self._set_state("STARTING…", C["warning"])
        self._send(f"START:{self.p1},{self.p2}")

    def _stop(self):
        self._send("RESET")
        self.active = False
        self.cd.reset()
        self._set_state("STOPPED", C["muted"])
        self.state_dot.set(C["muted"])
        self.start_btn.setEnabled(True)
        self.stop_btn.setEnabled(False)

    def _set_state(self, text: str, color: str):
        self.state_lbl.setText(text)
        self.state_lbl.setStyleSheet(f"color:{color};")
        self.state_dot.set(color)

    # ── LOG ──────────────────────────────────────────────────────────────────
    def _log(self, text: str):
        ts  = datetime.now().strftime("%H:%M:%S")
        row = lbl(f"[{ts}] {text}", 10, C["muted"])
        self._loglyt.insertWidget(self._loglyt.count()-1, row)
        QTimer.singleShot(40, lambda:
            self._scroll.verticalScrollBar().setValue(
                self._scroll.verticalScrollBar().maximum()))

# ─────────────────────────────────────────────
#  MAIN WINDOW
# ─────────────────────────────────────────────
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Reaction Lab  ·  ENCE 3608  Task 6")
        self.setMinimumSize(960, 680)

        cw = QWidget(); self.setCentralWidget(cw)
        vl = QVBoxLayout(cw); vl.setContentsMargins(0, 0, 0, 0)

        hdr = QWidget(); hdr.setFixedHeight(42)
        hdr.setStyleSheet(f"background:{C['surface2']}; border-bottom:1px solid {C['border']};")
        hl = QHBoxLayout(hdr); hl.setContentsMargins(16, 0, 16, 0)
        t = lbl("REACTION LAB", 13, C["accent"], bold=True)
        t.setStyleSheet(f"color:{C['accent']}; letter-spacing:3px;")
        hl.addWidget(t); hl.addStretch()
        hl.addWidget(lbl("ENCE 3608  ·  Task 6", 10, C["muted"]))
        vl.addWidget(hdr)

        self.tabs = QTabWidget()
        self.game = GameTab()
        self.stat = StatsTab()
        self.tabs.addTab(self.game, "GAME")
        self.tabs.addTab(self.stat, "STATISTICS")
        vl.addWidget(self.tabs)

        self.tabs.currentChanged.connect(
            lambda i: self.stat.reload_matchups() if i == 1 else None)
        self.game.round_done.connect(self._after_round)

    def _after_round(self, p1: str, p2: str):
        self.stat.add_matchup(p1, p2)

# ─────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())

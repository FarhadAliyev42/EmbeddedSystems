# ============================================================
#  Lab Task 7 — RFID Tag Logger GUI
#  Python 3  |  tkinter + pyserial
#  Install dependency:  pip install pyserial
# ============================================================
#  Usage:
#    1. Upload main.cpp to Arduino and keep it connected.
#    2. Run:  python app.py
#    3. Select the correct COM port and click Connect.
#    4. Scan RFID tags — they appear in the table live.
#    5. Database is saved to  rfid_tags.json  automatically.
# ============================================================

import tkinter as tk
from tkinter import ttk, messagebox
import serial
import serial.tools.list_ports
import threading
import json
import os
from datetime import datetime

# ── Config ───────────────────────────────────────────────────
DB_FILE   = "rfid_tags.json"
BAUD_RATE = 9600

# ── Database helpers ─────────────────────────────────────────
def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}   # { "UID_STRING": { "id": int, "uid": str,
                #                   "first_seen": str,
                #                   "last_seen": str,
                #                   "count": int } }

def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f, indent=2)

def next_id(db):
    if not db:
        return 1
    return max(entry["id"] for entry in db.values()) + 1

def record_tag(db, uid):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if uid in db:
        db[uid]["count"]    += 1
        db[uid]["last_seen"] = now
    else:
        db[uid] = {
            "id":         next_id(db),
            "uid":        uid,
            "first_seen": now,
            "last_seen":  now,
            "count":      1,
        }
    save_db(db)
    return db[uid]

# ── Main application ─────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("RFID Tag Logger — Lab Task 7")
        self.geometry("820x520")
        self.resizable(True, True)
        self.configure(bg="#f5f5f5")

        self.db      = load_db()
        self.serial  = None
        self.running = False

        self._build_ui()
        self._refresh_table()
        self._populate_ports()

    # ── UI construction ───────────────────────────────────────
    def _build_ui(self):
        # ── Top bar: port selector + connect button ──
        top = tk.Frame(self, bg="#f5f5f5", pady=8, padx=10)
        top.pack(fill="x")

        tk.Label(top, text="COM Port:", bg="#f5f5f5",
                 font=("Helvetica", 11)).pack(side="left")

        self.port_var = tk.StringVar()
        self.port_cb  = ttk.Combobox(top, textvariable=self.port_var,
                                     width=18, state="readonly")
        self.port_cb.pack(side="left", padx=(6, 12))

        self.btn_refresh = tk.Button(top, text="Refresh ports",
                                     command=self._populate_ports,
                                     bg="#e0e0e0", relief="flat",
                                     padx=8, pady=4)
        self.btn_refresh.pack(side="left", padx=(0, 12))

        self.btn_connect = tk.Button(top, text="Connect",
                                     command=self._toggle_connect,
                                     bg="#4CAF50", fg="white",
                                     relief="flat", padx=12, pady=4,
                                     font=("Helvetica", 11, "bold"))
        self.btn_connect.pack(side="left")

        self.status_lbl = tk.Label(top, text="Disconnected",
                                   bg="#f5f5f5", fg="#888",
                                   font=("Helvetica", 10))
        self.status_lbl.pack(side="left", padx=16)

        # ── Stats bar ──
        stats = tk.Frame(self, bg="#e8e8e8", pady=4, padx=10)
        stats.pack(fill="x")

        self.lbl_total  = tk.Label(stats, text="Total unique tags: 0",
                                   bg="#e8e8e8", font=("Helvetica", 10))
        self.lbl_total.pack(side="left", padx=(0, 24))

        self.lbl_scans  = tk.Label(stats, text="Total scans: 0",
                                   bg="#e8e8e8", font=("Helvetica", 10))
        self.lbl_scans.pack(side="left", padx=(0, 24))

        self.lbl_last   = tk.Label(stats, text="Last scan: —",
                                   bg="#e8e8e8", font=("Helvetica", 10))
        self.lbl_last.pack(side="left")

        # ── Table ──
        cols = ("id", "uid", "count", "first_seen", "last_seen")
        self.tree = ttk.Treeview(self, columns=cols,
                                 show="headings", height=18)

        self.tree.heading("id",         text="ID")
        self.tree.heading("uid",        text="Tag UID")
        self.tree.heading("count",      text="Scans")
        self.tree.heading("first_seen", text="First seen")
        self.tree.heading("last_seen",  text="Last seen")

        self.tree.column("id",         width=50,  anchor="center")
        self.tree.column("uid",        width=160, anchor="center")
        self.tree.column("count",      width=70,  anchor="center")
        self.tree.column("first_seen", width=160, anchor="center")
        self.tree.column("last_seen",  width=160, anchor="center")

        # Alternate row colours
        self.tree.tag_configure("odd",  background="#ffffff")
        self.tree.tag_configure("even", background="#f0f4ff")
        self.tree.tag_configure("new",  background="#d4edda")  # flash green

        scrollbar = ttk.Scrollbar(self, orient="vertical",
                                  command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side="left", fill="both", expand=True, padx=(10,0), pady=8)
        scrollbar.pack(side="left", fill="y", pady=8)

        # ── Bottom: log box ──
        log_frame = tk.Frame(self, bg="#f5f5f5")
        log_frame.pack(fill="x", padx=10, pady=(0, 8))

        tk.Label(log_frame, text="Serial log:",
                 bg="#f5f5f5", font=("Helvetica", 10)).pack(anchor="w")

        self.log_box = tk.Text(log_frame, height=5, state="disabled",
                               font=("Courier", 9), bg="#1e1e1e",
                               fg="#d4d4d4", relief="flat",
                               insertbackground="white")
        self.log_box.pack(fill="x")

        # ── Bottom buttons ──
        btn_bar = tk.Frame(self, bg="#f5f5f5", padx=10, pady=4)
        btn_bar.pack(fill="x")

        tk.Button(btn_bar, text="Clear database",
                  command=self._clear_db,
                  bg="#f44336", fg="white", relief="flat",
                  padx=8, pady=4).pack(side="right")

        tk.Button(btn_bar, text="Export CSV",
                  command=self._export_csv,
                  bg="#2196F3", fg="white", relief="flat",
                  padx=8, pady=4).pack(side="right", padx=(0, 8))

    # ── Port helpers ──────────────────────────────────────────
    def _populate_ports(self):
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self.port_cb["values"] = ports
        if ports:
            self.port_var.set(ports[0])

    def _toggle_connect(self):
        if self.running:
            self._disconnect()
        else:
            self._connect()

    def _connect(self):
        port = self.port_var.get()
        if not port:
            messagebox.showwarning("No port", "Please select a COM port.")
            return
        try:
            self.serial  = serial.Serial(port, BAUD_RATE, timeout=1)
            self.running = True
            self.btn_connect.config(text="Disconnect", bg="#f44336")
            self.status_lbl.config(text=f"Connected: {port}", fg="#2e7d32")
            t = threading.Thread(target=self._read_serial, daemon=True)
            t.start()
            self._log(f"Connected to {port} at {BAUD_RATE} baud.")
        except serial.SerialException as e:
            messagebox.showerror("Connection error", str(e))

    def _disconnect(self):
        self.running = False
        if self.serial and self.serial.is_open:
            self.serial.close()
        self.btn_connect.config(text="Connect", bg="#4CAF50")
        self.status_lbl.config(text="Disconnected", fg="#888")
        self._log("Disconnected.")

    # ── Serial reader (runs in background thread) ─────────────
    def _read_serial(self):
        while self.running:
            try:
                line = self.serial.readline().decode("utf-8").strip()
                if not line:
                    continue
                self._log(line)
                if line.startswith("TAG:"):
                    uid = line[4:].upper()
                    self.after(0, self._handle_tag, uid)
            except Exception:
                break

    # ── Tag handler (runs on main thread via after()) ─────────
    def _handle_tag(self, uid):
        entry = record_tag(self.db, uid)
        self._refresh_table(highlight_uid=uid)
        self._update_stats()

    # ── Table refresh ─────────────────────────────────────────
    def _refresh_table(self, highlight_uid=None):
        for row in self.tree.get_children():
            self.tree.delete(row)

        sorted_entries = sorted(self.db.values(), key=lambda x: x["id"])
        for i, e in enumerate(sorted_entries):
            tag = "even" if i % 2 == 0 else "odd"
            if highlight_uid and e["uid"] == highlight_uid:
                tag = "new"
            self.tree.insert("", "end", iid=e["uid"], tags=(tag,),
                             values=(e["id"], e["uid"], e["count"],
                                     e["first_seen"], e["last_seen"]))

        # Scroll to highlighted row
        if highlight_uid and highlight_uid in self.db:
            self.tree.see(highlight_uid)

        self._update_stats()

    # ── Stats bar update ──────────────────────────────────────
    def _update_stats(self):
        total_tags  = len(self.db)
        total_scans = sum(e["count"] for e in self.db.values())
        last = "—"
        if self.db:
            latest = max(self.db.values(), key=lambda x: x["last_seen"])
            last = f"{latest['uid']}  @  {latest['last_seen']}"

        self.lbl_total.config(text=f"Total unique tags: {total_tags}")
        self.lbl_scans.config(text=f"Total scans: {total_scans}")
        self.lbl_last.config( text=f"Last scan: {last}")

    # ── Serial log box ────────────────────────────────────────
    def _log(self, text):
        self.log_box.config(state="normal")
        self.log_box.insert("end", text + "\n")
        self.log_box.see("end")
        self.log_box.config(state="disabled")

    # ── Clear database ────────────────────────────────────────
    def _clear_db(self):
        if messagebox.askyesno("Clear database",
                               "Delete all tag records permanently?"):
            self.db = {}
            save_db(self.db)
            self._refresh_table()
            self._log("Database cleared.")

    # ── Export CSV ────────────────────────────────────────────
    def _export_csv(self):
        filename = f"rfid_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        with open(filename, "w") as f:
            f.write("ID,UID,Scans,First Seen,Last Seen\n")
            for e in sorted(self.db.values(), key=lambda x: x["id"]):
                f.write(f"{e['id']},{e['uid']},{e['count']},"
                        f"{e['first_seen']},{e['last_seen']}\n")
        self._log(f"Exported to {filename}")
        messagebox.showinfo("Exported", f"Saved as {filename}")

# ── Entry point ───────────────────────────────────────────────
if __name__ == "__main__":
    app = App()
    app.mainloop()

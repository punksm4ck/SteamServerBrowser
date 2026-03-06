import steam_locator
import sys, os, threading, requests, socket, time, subprocess
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, 
                             QTableWidgetItem, QVBoxLayout, QWidget, 
                             QPushButton, QHeaderView, QLineEdit, QComboBox, QHBoxLayout, 
                             QLabel, QCheckBox, QGridLayout, QTabWidget, QFrame, QTextEdit, QMenu)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QIcon, QAction
from dotenv import load_dotenv

load_dotenv('/home/tsann/Scripts/.env')

class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            t1, t2 = self.text(), other.text()
            # Latency Sort (e.g., "50ms")
            if 'ms' in t1 and 'ms' in t2:
                return float(t1.replace('ms', '')) < float(t2.replace('ms', ''))
            # Player Sort (e.g., "12/32")
            if '/' in t1 and '/' in t2:
                return int(t1.split('/')[0]) < int(t2.split('/')[0])
            # Pure Numeric Sort
            if t1.isdigit() and t2.isdigit():
                return int(t1) < int(t2)
        except: pass
        return super().__lt__(other)

class CSSBrowser(QMainWindow):
    log_signal = pyqtSignal(str)
    add_row_signal = pyqtSignal(str, str, str, str, str, str, str, str, str)
    btn_state_signal = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("punks CS:S Scanner")
        self.setGeometry(100, 100, 1100, 800)
        self.setStyleSheet("background-color: #4a4a4a; color: #e0e0e0; font-family: 'Arial';")
        self.icon_path = "/home/tsann/Pictures/Icons/CSSourceMonitor.png"
        
        main_layout = QVBoxLayout()
        container = QWidget(); container.setLayout(main_layout); self.setCentralWidget(container)

        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { background: #3a3a3a; color: white; padding: 6px 15px; } QTabBar::tab:selected { background: #5a5a5a; }")
        self.tab_internet = QWidget(); self.tabs.addTab(self.tab_internet, "Internet")
        for name in ["Favorites", "History", "Lan", "Friends"]: self.tabs.addTab(QWidget(), name)
        main_layout.addWidget(self.tabs)

        internet_layout = QVBoxLayout(); self.tab_internet.setLayout(internet_layout)
        self.table = QTableWidget(); self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels(["🔒", "🛡️", "Servers", "Game", "Players", "Bots", "Map", "Latency", "IP"])
        self.table.setColumnHidden(8, True)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self.show_context_menu)
        self.table.itemDoubleClicked.connect(self.join_server)
        
        # Enable dynamic sorting on header click
        self.table.setSortingEnabled(True)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setStyleSheet("QHeaderView::section { background-color: #333; color: white; } QTableWidget { background-color: #2b2b2b; gridline-color: #444; }")
        internet_layout.addWidget(self.table)

        ctrl_frame = QFrame(); grid = QGridLayout(); ctrl_frame.setLayout(grid)
        self.btn_launcher = QPushButton("Add Launcher"); self.btn_launcher.clicked.connect(self.toggle_launcher)
        self.btn_refresh = QPushButton("Refresh all"); self.btn_refresh.clicked.connect(self.start_scan)
        self.btn_connect = QPushButton("Connect"); self.btn_connect.clicked.connect(self.join_server)
        
        for i, b in enumerate([self.btn_launcher, self.btn_refresh, self.btn_connect]):
            b.setStyleSheet("background-color: #555; padding: 8px 20px; font-weight: bold;")
            grid.addWidget(b, 0, i)
        internet_layout.addWidget(ctrl_frame)

        self.log_window = QTextEdit(); self.log_window.setReadOnly(True); self.log_window.setFixedHeight(120)
        self.log_window.setStyleSheet("background-color: #1a1a1a; color: #00ff00; font-family: 'Monospace';")
        main_layout.addWidget(self.log_window)

        self.add_row_signal.connect(self.add_row); self.log_signal.connect(self.update_log)
        self.btn_state_signal.connect(self.btn_refresh.setEnabled)
        self.log_signal.emit("punks System Online. Sorting Engine Repaired.")

    def show_context_menu(self, pos):
        row = self.table.currentRow()
        if row == -1: return
        menu = QMenu(self); menu.setStyleSheet("background-color: #3a3a3a; color: white;")
        for act_text in ["Connect", "View Info", "Refresh", "Add Favorite"]:
            act = QAction(act_text, self)
            if "Connect" in act_text: act.triggered.connect(self.join_server)
            menu.addAction(act)
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def update_log(self, msg): 
        self.log_window.append(f"> {msg}")
        self.log_window.verticalScrollBar().setValue(self.log_window.verticalScrollBar().maximum())

    def join_server(self):
        row = self.table.currentRow()
        if row >= 0:
            ip = self.table.item(row, 8).text().strip()
            c_env = os.environ.copy()
            for k in list(c_env.keys()):
                if any(x in k for x in ["PYTHON", "QT", "LD_LIBRARY"]): del c_env[k]
            c_env["SDL_AUDIODRIVER"] = "pulseaudio"
            subprocess.Popen(["steam", "-no-sandbox", "-applaunch", "240", "+connect", ip], env=c_env)
            self.log_signal.emit(f"[*] Engine Boot -> {ip}")

    def start_scan(self):
        self.btn_refresh.setEnabled(False); self.table.setSortingEnabled(False)
        self.table.setRowCount(0); self.log_signal.emit("Scanning Global API...")
        threading.Thread(target=self.production_scan, daemon=True).start()

    def production_scan(self):
        key = os.getenv("STEAM_API_KEY")
        all_ips = []
        for limit in [5000, 10000]:
            try:
                r = requests.get(f"https://api.steampowered.com/IGameServersService/GetServerList/v1/?key={key}&limit={limit}&filter=\\appid\\240", timeout=12)
                all_ips.extend([s['addr'] for s in r.json().get('response', {}).get('servers', [])])
            except: continue
        
        unique_ips = list(set(all_ips))
        self.log_signal.emit(f"Pinging {len(unique_ips)} servers...")
        with ThreadPoolExecutor(max_workers=80) as ex: ex.map(self.ping_server, unique_ips)
        self.log_signal.emit("Scan Complete. Sorting Enabled."); self.btn_state_signal.emit(True)

    def ping_server(self, ip):
        try:
            h, p = ip.split(":"); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1.2)
            s.sendto(b"\xFF\xFF\xFF\xFFTSource Engine Query\x00", (h, int(p)))
            data, _ = s.recvfrom(4096)
            if data.startswith(b"\xFF\xFF\xFF\xFF\x49"):
                ptr = 6
                def r_s(d, p):
                    e = d.find(b"\x00", p)
                    return d[p:e].decode('utf-8', 'ignore'), e + 1
                name, ptr = r_s(data, ptr); map_n, ptr = r_s(data, ptr); _, ptr = r_s(data, ptr); game, ptr = r_s(data, ptr)
                ptr += 2; p_c = data[ptr]; max_p = data[ptr+1]; bots = data[ptr+2]
                self.add_row_signal.emit("", "🛡️", name, game, f"{p_c}/{max_p}", str(bots), map_n, "50ms", ip)
        except: pass

    def add_row(self, pw, vac, name, game, p, b, m, lat, ip):
        self.table.setSortingEnabled(False)
        r = self.table.rowCount(); self.table.insertRow(r)
        data = [pw, vac, name, game, p, b, m, lat, ip]
        for i, v in enumerate(data):
            self.table.setItem(r, i, NumericItem(v))
        self.table.setSortingEnabled(True)

    def toggle_launcher(self): pass
    def check_launcher_state(self): pass

if __name__ == "__main__":
    app = QApplication(sys.argv); window = CSSBrowser(); window.show(); sys.exit(app.exec())

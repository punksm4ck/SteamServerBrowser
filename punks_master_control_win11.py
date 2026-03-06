import sys, os, threading, requests, socket, time, subprocess, bz2, re, ctypes
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, QTableWidgetItem, 
                             QVBoxLayout, QWidget, QPushButton, QHeaderView, QLineEdit, 
                             QHBoxLayout, QLabel, QGridLayout, QTabWidget, QFrame, QTextEdit, QMenu, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QIcon
from dotenv import load_dotenv

load_dotenv('C:/Scripts/.env')

class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            t1, t2 = self.text(), other.text()
            if 'ms' in t1 and 'ms' in t2:
                return float(t1.replace('ms', '')) < float(t2.replace('ms', ''))
            if '/' in t1 and '/' in t2:
                return int(t1.split('/')[0]) < int(t2.split('/')[0])
            return int(t1) < int(t2)
        except: return super().__lt__(other)

class CSSBrowser(QMainWindow):
    log_signal = pyqtSignal(str)
    add_row_signal = pyqtSignal(str, str, str, str, str, str, str, str, str, str)
    btn_state_signal = pyqtSignal(bool)
    sort_toggle_signal = pyqtSignal(str, bool)

    def __init__(self):
        super().__init__()
        self.api_key = os.getenv("STEAM_API_KEY", "").strip()
        
        self.setWindowTitle("punks Master Control - OSIRIS 100% PARITY")
        self.setGeometry(100, 100, 1300, 850)
        self.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: 'Segoe UI';")
        self.stop_flag = False
        
        # GLOBAL VISUAL ASSET BINDING
        icon_path = r"C:\Users\tsann\Pictures\Icons\CSSourceMonitor.png"
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        main_layout = QVBoxLayout()
        container = QWidget(); container.setLayout(main_layout); self.setCentralWidget(container)

        self.tabs = QTabWidget()
        self.engines = [
            ("Counter-Strike: Source", "240"), ("Day of Defeat", "30"),
            ("Day of Defeat: Source", "300"), ("Half-Life 2: DM", "320"),
            ("No More Room in Hell", "224260"), ("Team Fortress Classic", "20"),
            ("Team Fortress 2", "440")
        ]
        
        self.game_paths = {
            "240": "Counter-Strike Source/cstrike", "30": "Half-Life/dod",
            "300": "Day of Defeat Source/dod", "320": "Half-Life 2 Deathmatch/hl2mp",
            "224260": "nmrih/nmrih", "20": "Half-Life/tfc", "440": "Team Fortress 2/tf"
        }
        
        self.tables = {}
        for name, appid in self.engines:
            tab = QWidget(); self.tabs.addTab(tab, name)
            table = self.create_table(); lay = QVBoxLayout(); lay.addWidget(table); tab.setLayout(lay)
            self.tables[appid] = table
            
        main_layout.addWidget(self.tabs)

        filter_frame = QFrame(); filter_grid = QGridLayout(); filter_frame.setLayout(filter_grid)
        self.txt_search = QLineEdit(); self.txt_search.setPlaceholderText("Filter map/name...")
        self.txt_search.textChanged.connect(self.apply_filters)
        self.cmb_latency = QComboBox(); self.cmb_latency.addItems(["All Latency", "< 50ms", "< 100ms", "< 150ms"])
        self.cmb_latency.currentIndexChanged.connect(self.apply_filters)
        
        filter_grid.addWidget(QLabel("Search:"), 0, 0); filter_grid.addWidget(self.txt_search, 0, 1)
        filter_grid.addWidget(QLabel("Ping Filter:"), 0, 2); filter_grid.addWidget(self.cmb_latency, 0, 3)
        main_layout.addWidget(filter_frame)

        btn_frame = QFrame(); btn_layout = QHBoxLayout(); btn_frame.setLayout(btn_layout)
        self.btn_refresh = QPushButton("Refresh List"); self.btn_refresh.clicked.connect(self.start_scan)
        self.btn_cancel = QPushButton("Cancel Scan"); self.btn_cancel.clicked.connect(self.cancel_scan)
        self.btn_launch = QPushButton("Launch Server (FastDL Sync)"); self.btn_launch.clicked.connect(self.launch_server)
        
        for b in [self.btn_refresh, self.btn_cancel, self.btn_launch]:
            b.setStyleSheet("background-color: #444; color: white; padding: 15px; font-weight: bold; border: 1px solid #111;")
            btn_layout.addWidget(b)
        main_layout.addWidget(btn_frame)

        self.log_window = QTextEdit(); self.log_window.setFixedHeight(120); self.log_window.setStyleSheet("background-color: #111; color: #0f0;")
        main_layout.addWidget(self.log_window)

        self.add_row_signal.connect(self.add_row_handler)
        self.log_signal.connect(self.log_window.append)
        self.btn_state_signal.connect(self.btn_refresh.setEnabled)
        self.sort_toggle_signal.connect(self.toggle_engine_sorting)

        if len(self.api_key) == 32:
            self.log_signal.emit("[SYS] Visuals Linked. Binary Handoff Armed.")
        else:
            self.log_signal.emit("[FATAL] KEY VERIFICATION FAILED. CHECK .ENV FILE.")

    def create_table(self):
        t = QTableWidget(); t.setColumnCount(9)
        t.setHorizontalHeaderLabels(["🔒", "🛡️", "Servers", "Game", "Players", "Bots", "Map", "Latency", "IP"])
        t.setColumnHidden(8, True); t.horizontalHeader().setStretchLastSection(True)
        t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        t.customContextMenuRequested.connect(self.show_context_menu)
        return t

    def show_context_menu(self, pos):
        table = self.sender(); row = table.currentRow()
        if row == -1: return
        menu = QMenu(self); menu.setStyleSheet("background-color: #3a3a3a; color: white;")
        acts = [("Connect (FastDL)", self.launch_server)]
        for text, func in acts:
            act = QAction(text, self)
            if func: act.triggered.connect(func)
            menu.addAction(act)
        menu.exec(table.viewport().mapToGlobal(pos))

    def toggle_engine_sorting(self, appid, state): 
        self.tables[appid].setSortingEnabled(state)

    def apply_filters(self):
        search = self.txt_search.text().lower()
        lat_filter = self.cmb_latency.currentText()
        max_lat = 9999
        if "< 50ms" in lat_filter: max_lat = 50
        elif "< 100ms" in lat_filter: max_lat = 100
        elif "< 150ms" in lat_filter: max_lat = 150

        for table in self.tables.values():
            for i in range(table.rowCount()):
                item_name = table.item(i, 2)
                item_map = table.item(i, 6)
                item_lat = table.item(i, 7)
                if item_name and item_map and item_lat:
                    matches_search = search in item_name.text().lower() or search in item_map.text().lower()
                    try:
                        ping_val = float(item_lat.text().replace('ms', ''))
                        matches_ping = ping_val <= max_lat
                    except: matches_ping = True
                    
                    table.setRowHidden(i, not (matches_search and matches_ping))

    def cancel_scan(self):
        self.stop_flag = True
        self.log_signal.emit("[SYS] Scan Abort Signal Sent. Threads halting...")
        self.btn_state_signal.emit(True)

    def launch_server(self):
        appid = self.engines[self.tabs.currentIndex()][1]
        table = self.tables[appid]
        if table.currentRow() >= 0:
            ip = table.item(table.currentRow(), 8).text().strip()
            steam_path = os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)') + "/Steam/steamapps/common/"
            target_path = steam_path + self.game_paths[appid]
            threading.Thread(target=self.auto_sync_and_launch, args=(ip, appid, target_path), daemon=True).start()

    def auto_sync_and_launch(self, ip, appid, path):
        self.log_signal.emit(f"[FastDL] Probing {ip}...")
        try:
            h, p = ip.split(":"); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1.5)
            s.sendto(b"\xFF\xFF\xFF\xFFV\xFF\xFF\xFF\xFF", (h, int(p)))
            data, _ = s.recvfrom(4096)
            if data.startswith(b"\xFF\xFF\xFF\xFF\x41"):
                s.sendto(b"\xFF\xFF\xFF\xFFV" + data[5:9], (h, int(p)))
                raw = b"".join([s.recvfrom(4096)[0] for _ in range(3)])
                match = re.search(b'sv_downloadurl\x00(http[^\x00]+)\x00', raw, re.IGNORECASE)
                if match:
                    url = match.group(1).decode('utf-8', 'ignore')
                    url = url if url.endswith('/') else url + '/'
                    self.log_signal.emit(f"[FastDL] Syncing: {url}")
                    self.run_fastdl_sweep(url, path)
        except: pass
        
        self.log_signal.emit(f"[SYS] Firing binary engine for {ip}...")
        steam_exe = os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)') + "/Steam/steam.exe"
        subprocess.Popen([steam_exe, "-applaunch", appid, "+connect", ip])

    def run_fastdl_sweep(self, base_url, target_dir):
        for folder in ["maps/", "materials/", "models/", "sound/"]:
            try:
                r = requests.get(base_url + folder, timeout=5)
                links = re.findall(r'href="([^"/]+\.?bz2|[^"/]+/?)"', r.text)
                with ThreadPoolExecutor(max_workers=50) as ex:
                    for l in links:
                        if not l.endswith('/'):
                            ex.submit(self.download_asset, base_url + folder + l, os.path.join(target_dir, folder, l))
            except: pass

    def download_asset(self, url, dest):
        final_dest = dest[:-4] if dest.endswith('.bz2') else dest
        if os.path.exists(final_dest): return
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            data = requests.get(url).content
            if url.endswith('.bz2'): data = bz2.decompress(data); dest = final_dest
            with open(dest, 'wb') as f: f.write(data)
            self.log_signal.emit(f"[+] Synced: {os.path.basename(dest)}")
        except: pass

    def start_scan(self):
        appid = self.engines[self.tabs.currentIndex()][1]
        self.btn_refresh.setEnabled(False); self.tables[appid].setRowCount(0); self.stop_flag = False
        self.sort_toggle_signal.emit(appid, False)
        threading.Thread(target=self.sweep, args=(appid,), daemon=True).start()

    def sweep(self, appid):
        self.log_signal.emit(f"[API] Initializing Uncapped Sweep for AppID {appid}...")
        url = f"https://api.steampowered.com/IGameServersService/GetServerList/v1/?key={self.api_key}&limit=25000&filter=\\appid\\{appid}"
        headers = {'User-Agent': 'Valve/Steam HTTP Client 1.0'}
        try:
            r = requests.get(url, headers=headers, timeout=15)
            if r.status_code == 200:
                servers = r.json().get('response', {}).get('servers', [])
                self.log_signal.emit(f"[API] 200 OK. Pinging {len(servers)} servers...")
                with ThreadPoolExecutor(max_workers=250) as ex:
                    for s in servers:
                        if self.stop_flag: break
                        ex.submit(self.ping, s['addr'], appid)
            else:
                self.log_signal.emit(f"[ERROR] API HTTP {r.status_code}. Handshake Rejected.")
        except Exception as e:
            self.log_signal.emit(f"[FATAL] Connection Break: {str(e)}")
        
        self.sort_toggle_signal.emit(appid, True)
        self.btn_state_signal.emit(True)
        if not self.stop_flag: self.log_signal.emit("[SYS] Sweep Complete. Sorting Engine Armed.")

    def ping(self, ip, appid):
        if self.stop_flag: return
        try:
            h, p = ip.split(":"); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(1.2)
            s.sendto(b"\xFF\xFF\xFF\xFFTSource Engine Query\x00", (h, int(p)))
            data, _ = s.recvfrom(4096)
            if data.startswith(b"\xFF\xFF\xFF\xFF\x41"):
                s.sendto(b"\xFF\xFF\xFF\xFFTSource Engine Query\x00" + data[5:9], (h, int(p)))
                data, _ = s.recvfrom(4096)
            if data.startswith(b"\xFF\xFF\xFF\xFF\x49"):
                ptr = 6
                def r_s(d, p): e = d.find(b"\x00", p); return d[p:e].decode('utf-8', 'ignore'), e + 1
                name, ptr = r_s(data, ptr); m_n, ptr = r_s(data, ptr); _, ptr = r_s(data, ptr); game, ptr = r_s(data, ptr)
                ptr += 2; p_c = data[ptr]; max_p = data[ptr+1]
                self.add_row_signal.emit(appid, "", "🛡️", name, game, f"{p_c}/{max_p}", "0", m_n, "50ms", ip)
        except: pass

    def add_row_handler(self, appid, pw, vac, name, game, p, b, m, lat, ip):
        table = self.tables[appid]; r = table.rowCount(); table.insertRow(r)
        for i, v in enumerate([pw, vac, name, game, p, b, m, lat, ip]): table.setItem(r, i, NumericItem(v))

if __name__ == "__main__":
    # OS-LEVEL APP ID OVERRIDE FOR TASKBAR BINDING
    try: ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("punks.mastercontrol.1")
    except: pass
    app = QApplication(sys.argv); window = CSSBrowser(); window.show(); sys.exit(app.exec())

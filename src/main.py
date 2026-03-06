import sys, os, threading, requests, socket, time, subprocess, bz2, re, asyncio
from concurrent.futures import ThreadPoolExecutor
from PyQt6.QtWidgets import (QApplication, QMainWindow, QTableWidget, 
                             QTableWidgetItem, QVBoxLayout, QWidget, 
                             QPushButton, QHeaderView, QLineEdit, QHBoxLayout, 
                             QLabel, QGridLayout, QTabWidget, QFrame, QTextEdit, QMenu, QComboBox)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QAction
from dotenv import load_dotenv
import a2s

load_dotenv('/home/tsann/Scripts/.env')

class NumericItem(QTableWidgetItem):
    def __lt__(self, other):
        try:
            t1, t2 = self.text(), other.text()
            if 'ms' in t1 and 'ms' in t2:
                return float(t1.replace('ms', '')) < float(t2.replace('ms', ''))
            if '/' in t1 and '/' in t2:
                return int(t1.split('/')[0]) < int(t2.split('/')[0])
            return int(t1) < int(t2)
        except ValueError:
            return super().__lt__(other)

class AsyncServerScanner(QThread):
    server_found = pyqtSignal(str, str, str, str, str, str, str, str, str, str)
    scan_complete = pyqtSignal(str)
    log_update = pyqtSignal(str)

    def __init__(self, appid, api_key):
        super().__init__()
        self.appid = appid
        self.api_key = api_key
        self.stop_flag = False

    async def query_server(self, ip, semaphore):
        if self.stop_flag:
            return
        async with semaphore:
            try:
                host, port = ip.split(":")
                address = (host, int(port))
                start_time = time.time()
                info = await a2s.ainfo(address, timeout=1.5)
                latency = int((time.time() - start_time) * 1000)
                
                pw = "🔒" if info.password_protected else ""
                vac = "🛡️" if info.vac_enabled else ""
                players = f"{info.player_count}/{info.max_players}"
                
                self.server_found.emit(
                    self.appid, pw, vac, info.server_name, 
                    info.folder, players, str(info.bot_count), 
                    info.map_name, f"{latency}ms", ip
                )
            except Exception:
                pass

    async def execute_scan(self, ips):
        semaphore = asyncio.Semaphore(150)
        tasks = [self.query_server(ip, semaphore) for ip in ips]
        await asyncio.gather(*tasks)

    def run(self):
        self.log_update.emit(f"[SCAN] Requesting master node list for AppID {self.appid}...")
        url = f"https://api.steampowered.com/IGameServersService/GetServerList/v1/?key={self.api_key}&limit=500&filter=\\appid\\{self.appid}"
        
        try:
            response = requests.get(url, timeout=10).json()
            servers = response.get('response', {}).get('servers', [])
            valid_ips = [s['addr'] for s in servers if not s['addr'].startswith(("169.254.", "10."))]
            self.log_update.emit(f"[SCAN] Discovered {len(valid_ips)} valid targets. Initiating A2S async sweep...")
            
            asyncio.run(self.execute_scan(valid_ips))
            self.log_update.emit(f"[SCAN] Sweep complete for AppID {self.appid}.")
        except Exception as e:
            self.log_update.emit(f"[ERROR] Master node query failed: {str(e)}")
        finally:
            self.scan_complete.emit(self.appid)

class CSSBrowser(QMainWindow):
    log_signal = pyqtSignal(str)
    add_row_signal = pyqtSignal(str, str, str, str, str, str, str, str, str, str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("punks Master Control - OSIRIS Locked-In [Enterprise Edition]")
        self.setGeometry(100, 100, 1300, 850)
        self.setStyleSheet("background-color: #2b2b2b; color: #e0e0e0; font-family: 'Arial';")
        self.active_scanner = None
        self.fastdl_stop = False
        
        main_layout = QVBoxLayout()
        container = QWidget()
        container.setLayout(main_layout)
        self.setCentralWidget(container)

        self.tabs = QTabWidget()
        self.tabs.setUsesScrollButtons(True)
        self.tabs.setStyleSheet("QTabBar::tab { background: #3a3a3a; padding: 8px 15px; } QTabBar::tab:selected { background: #555; font-weight: bold; }")
        
        self.engines = [
            ("Counter-Strike: Source", "240"),
            ("Day of Defeat", "30"),
            ("Day of Defeat: Source", "300"),
            ("Half-Life 2: DM", "320"),
            ("No More Room in Hell", "224260"),
            ("Team Fortress Classic", "20"),
            ("Team Fortress 2", "440")
        ]
        
        self.game_paths = {
            "240": "common/Counter-Strike Source/cstrike",
            "30": "common/Half-Life/dod",
            "300": "common/Day of Defeat Source/dod",
            "320": "common/Half-Life 2 Deathmatch/hl2mp",
            "224260": "common/nmrih/nmrih",
            "20": "common/Half-Life/tfc",
            "440": "common/Team Fortress 2/tf"
        }
        
        self.tables = {}
        for name, appid in self.engines:
            tab = QWidget()
            self.tabs.addTab(tab, name)
            table = self.create_table()
            lay = QVBoxLayout()
            lay.addWidget(table)
            tab.setLayout(lay)
            self.tables[appid] = table
            
        main_layout.addWidget(self.tabs)

        filter_frame = QFrame()
        filter_grid = QGridLayout()
        filter_frame.setLayout(filter_grid)
        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Filter map/name...")
        self.txt_search.textChanged.connect(self.apply_filters)
        self.cmb_latency = QComboBox()
        self.cmb_latency.addItems(["All Latency", "< 50ms", "< 100ms"])
        self.cmb_latency.currentIndexChanged.connect(self.apply_filters)
        
        filter_grid.addWidget(QLabel("Search:"), 0, 0)
        filter_grid.addWidget(self.txt_search, 0, 1)
        filter_grid.addWidget(QLabel("Ping:"), 0, 2)
        filter_grid.addWidget(self.cmb_latency, 0, 3)
        main_layout.addWidget(filter_frame)

        btn_frame = QFrame()
        btn_layout = QHBoxLayout()
        btn_frame.setLayout(btn_layout)
        
        self.btn_refresh = QPushButton("Refresh List")
        self.btn_refresh.clicked.connect(self.start_scan)
        self.btn_stop = QPushButton("Stop Scan")
        self.btn_stop.clicked.connect(self.trigger_stop)
        self.btn_recovery = QPushButton("System Rebuild")
        self.btn_recovery.clicked.connect(self.run_reinstall)
        self.btn_connect = QPushButton("Connect (FastDL)")
        self.btn_connect.clicked.connect(self.join_server)
        
        for b in [self.btn_refresh, self.btn_stop, self.btn_recovery, self.btn_connect]:
            b.setStyleSheet("background-color: #444; color: white; padding: 12px; font-weight: bold; border: 1px solid #111;")
            btn_layout.addWidget(b)
        main_layout.addWidget(btn_frame)

        self.log_window = QTextEdit()
        self.log_window.setFixedHeight(120)
        self.log_window.setStyleSheet("background-color: #111; color: #0f0;")
        self.log_window.setReadOnly(True)
        main_layout.addWidget(self.log_window)

        self.add_row_signal.connect(self.add_row_handler)
        self.log_signal.connect(self.log_window.append)
        
        self.log_signal.emit("[SYS] OSIRIS Master Control Online. Auto-FastDL Interceptor Engaged.")

    def create_table(self):
        t = QTableWidget()
        t.setColumnCount(9)
        t.setHorizontalHeaderLabels(["🔒", "🛡️", "Servers", "Game", "Players", "Bots", "Map", "Latency", "IP"])
        t.setColumnHidden(8, True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        t.horizontalHeader().setStretchLastSection(True)
        t.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        t.customContextMenuRequested.connect(self.show_context_menu)
        return t

    def show_context_menu(self, pos):
        table = self.sender()
        row = table.currentRow()
        if row == -1: return
        menu = QMenu(self)
        menu.setStyleSheet("background-color: #3a3a3a; color: white;")
        acts = [("Connect to server", self.join_server)]
        for text, func in acts:
            act = QAction(text, self)
            act.triggered.connect(func)
            menu.addAction(act)
        menu.exec(table.viewport().mapToGlobal(pos))

    def trigger_stop(self):
        if self.active_scanner and self.active_scanner.isRunning():
            self.active_scanner.stop_flag = True
        self.fastdl_stop = True
        self.log_signal.emit("[SYS] HALTING ALL NETWORK OPERATIONS.")
        self.btn_refresh.setEnabled(True)

    def run_reinstall(self):
        try:
            subprocess.Popen(["/home/tsann/Scripts/reinstall-steam.sh"], start_new_session=True)
            self.log_signal.emit("[SYS] System Rebuild process initiated.")
        except Exception as e:
            self.log_signal.emit(f"[ERROR] Failed to execute rebuild script: {e}")

    def join_server(self):
        appid = self.engines[self.tabs.currentIndex()][1]
        table = self.tables[appid]
        if table.currentRow() >= 0:
            ip = table.item(table.currentRow(), 8).text().strip()
            path = os.path.expanduser(f"~/.local/share/Steam/steamapps/{self.game_paths.get(appid, '')}")
            threading.Thread(target=self.auto_fastdl_and_launch, args=(ip, appid, path), daemon=True).start()

    def get_sv_downloadurl(self, ip):
        try:
            h, p = ip.split(":")
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(1.5)
            s.sendto(b"\xFF\xFF\xFF\xFFV\xFF\xFF\xFF\xFF", (h, int(p)))
            data, _ = s.recvfrom(4096)
            if data.startswith(b"\xFF\xFF\xFF\xFF\x41"):
                s.sendto(b"\xFF\xFF\xFF\xFFV" + data[5:9], (h, int(p)))
                raw = b"".join([s.recvfrom(4096)[0] for _ in range(2)])
                match = re.search(b'sv_downloadurl\x00(http[^\x00]+)\x00', raw, re.IGNORECASE)
                if match:
                    url = match.group(1).decode('utf-8', 'ignore')
                    return url if url.endswith('/') else url + '/'
        except Exception:
            pass
        return None

    def auto_fastdl_and_launch(self, ip, appid, target_path):
        self.log_signal.emit(f"[FastDL] Interrogating {ip} for HTTP Download URL...")
        dl_url = self.get_sv_downloadurl(ip)
        
        self.fastdl_stop = False
        if dl_url:
            self.log_signal.emit(f"[FastDL] Bypass Detected: {dl_url}")
            self.fastdl_sweep(dl_url, target_path)
        else:
            self.log_signal.emit("[FastDL] No valid FastDL endpoint detected. Proceeding to direct launch.")
            
        self.launch_steam_app(appid, ip)

    def fastdl_sweep(self, base_url, target_dir):
        for folder in ["maps/", "materials/", "models/", "sound/", "sprites/"]:
            if self.fastdl_stop: break
            self.sweep_directory(base_url, folder, target_dir)

    def sweep_directory(self, base_url, path, target_dir):
        if self.fastdl_stop: return
        try:
            r = requests.get(base_url + path, timeout=5)
            links = [l for l in re.findall(r'href="([^"/]+\.?bz2|[^"/]+/?)"', r.text) if l not in ['../', './']]
            files = []
            for link in links:
                if link.endswith('/'): 
                    self.sweep_directory(base_url, path + link, target_dir)
                else: 
                    files.append((base_url + path + link, os.path.join(target_dir, path, link)))
                    
            with ThreadPoolExecutor(max_workers=50) as ex:
                for u, d in files:
                    if self.fastdl_stop: break
                    ex.submit(self.inject_payload, u, d)
        except Exception:
            pass

    def inject_payload(self, url, dest):
        if self.fastdl_stop: return
        final_dest = dest[:-4] if dest.endswith('.bz2') else dest
        if os.path.exists(final_dest): return
        
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        try:
            r = requests.get(url, timeout=10)
            data = r.content
            if url.endswith('.bz2'): 
                data = bz2.decompress(data)
                dest = final_dest
            with open(dest, 'wb') as f: 
                f.write(data)
            self.log_signal.emit(f"[+] Payload Injected -> {os.path.basename(dest)}")
        except Exception:
            pass

    def launch_steam_app(self, appid, ip):
        c_env = os.environ.copy()
        for k in list(c_env.keys()):
            if any(x in k for x in ["PYTHON", "QT", "LD_LIBRARY"]): 
                del c_env[k]
        self.log_signal.emit(f"[SYS] Launching AppID {appid} connected to {ip}")
        subprocess.Popen(["steam", "-no-sandbox", "-applaunch", appid, "+connect", ip], env=c_env, start_new_session=True)

    def start_scan(self):
        appid = self.engines[self.tabs.currentIndex()][1]
        api_key = os.getenv("STEAM_API_KEY")
        
        if not api_key:
            self.log_signal.emit("[ERROR] STEAM_API_KEY not found in .env file.")
            return

        self.btn_refresh.setEnabled(False)
        self.tables[appid].setSortingEnabled(False)
        self.tables[appid].setRowCount(0)

        self.active_scanner = AsyncServerScanner(appid, api_key)
        self.active_scanner.server_found.connect(self.add_row_handler)
        self.active_scanner.log_update.connect(self.log_signal.emit)
        self.active_scanner.scan_complete.connect(self.scan_finished)
        self.active_scanner.start()

    def scan_finished(self, appid):
        self.tables[appid].setSortingEnabled(True)
        self.btn_refresh.setEnabled(True)

    def add_row_handler(self, appid, pw, vac, name, game, p, b, m, lat, ip):
        table = self.tables[appid]
        r = table.rowCount()
        table.insertRow(r)
        items = [pw, vac, name, game, p, b, m, lat, ip]
        for i, v in enumerate(items): 
            table.setItem(r, i, NumericItem(v))

    def apply_filters(self):
        search = self.txt_search.text().lower()
        lat_filter = self.cmb_latency.currentIndex()
        
        for table in self.tables.values():
            for i in range(table.rowCount()):
                match_text = search in table.item(i, 2).text().lower() or search in table.item(i, 6).text().lower()
                match_lat = True
                
                if lat_filter > 0:
                    try:
                        lat_val = float(table.item(i, 7).text().replace('ms', ''))
                        if lat_filter == 1 and lat_val >= 50: match_lat = False
                        if lat_filter == 2 and lat_val >= 100: match_lat = False
                    except ValueError:
                        pass
                        
                table.setRowHidden(i, not (match_text and match_lat))

def main():
    app = QApplication(sys.argv)
    window = CSSBrowser()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()

import os
import platform

def get_steam_path():
    if platform.system() == "Windows":
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            return winreg.QueryValueEx(key, "SteamPath")[0]
        except Exception:
            return "C:\\Program Files (x86)\\Steam"
    return os.path.expanduser("~/.steam/steam")

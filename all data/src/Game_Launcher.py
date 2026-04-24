import subprocess
import os
import common
import sys
import platform
import logging
def get_base_path():
    try:
        from paths import get_base_path as _get_base_path
        return _get_base_path()
    except ImportError:
        folder_path = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(folder_path) == 'src':
            return os.path.dirname(folder_path)
        return folder_path


BASE_PATH = get_base_path()
sys.path.append(BASE_PATH)
sys.path.append(os.path.join(BASE_PATH, 'src'))

logger = logging.getLogger(__name__)

def signal_handler(sig, frame):
    logger.warning(f"Termination signal received, shutting down...")
    sys.exit(0)

def get_steam_exe():
    if platform.system() == 'Windows':
        try:
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam")
            steam_path, _ = winreg.QueryValueEx(key, "SteamExe")
            winreg.CloseKey(key)
            if os.path.isfile(steam_path):
                return steam_path
        except Exception:
            pass
        # Fallback common Windows paths
        for candidate in [
            r"C:\Program Files (x86)\Steam\steam.exe",
            r"C:\Program Files\Steam\steam.exe",
        ]:
            if os.path.isfile(candidate):
                return candidate
        raise RuntimeError("Failed to locate Steam.exe")

    elif platform.system() == 'Darwin':
        candidate = os.path.expanduser("~/Library/Application Support/Steam/Steam.app/Contents/MacOS/steam_osx")
        if os.path.isfile(candidate):
            return candidate
        raise RuntimeError("Failed to locate Steam on macOS")

    else:  # Linux
        for candidate in [
            os.path.expanduser("~/.local/share/Steam/steam.sh"),
            "/usr/bin/steam",
            "/usr/games/steam",
            "/snap/bin/steam",
        ]:
            if os.path.isfile(candidate):
                return candidate
        # Try which
        try:
            result = subprocess.run(["which", "steam"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                return result.stdout.strip()
        except Exception:
            pass
        raise RuntimeError("Failed to locate Steam on Linux")

def launch_game(appid):
    steam_exe = get_steam_exe()
    subprocess.Popen([steam_exe, f"steam://rungameid/{appid}"])

def launch_limbus():
    launch_game("1973530")
    while not common.element_exist("pictures/CustomAdded1080p/launch/Clear_All_Caches.png"):
        common.sleep(1)
    while common.element_exist("pictures/CustomAdded1080p/launch/Clear_All_Caches.png"):
        common.mouse_move_click(*common.scale_coordinates_1080p(960, 540))
        common.click_matching("pictures/general/beeg_confirm.png", recursive=False)
        if common.element_exist("pictures/general/maint.png"):
            common.click_matching("pictures/general/close.png", recursive=False)
            return False
        common.sleep(2)
        
    while not common.element_exist("pictures/CustomAdded1080p/Mail/Mail.png"):
        common.click_matching("pictures/general/beeg_confirm.png", recursive=False)
        if common.element_exist("pictures/general/maint.png"):
            common.click_matching("pictures/general/close.png", recursive=False)
            return False
        common.sleep(2)
    common.sleep(2)
    return True
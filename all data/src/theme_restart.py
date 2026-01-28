import sys
import os
import subprocess
import time

def restart_app_with_theme():
    """Restart the main application with specified theme and tab"""
    BASE_PATH = os.path.dirname(os.path.abspath(__file__))
    main_script_path = os.path.join(BASE_PATH, "..", "gui_launcher.py")

    theme_name = sys.argv[1] if len(sys.argv) > 1 else "Dark"

    tab_name = sys.argv[2] if len(sys.argv) > 2 else ""

    cmd = ["python", main_script_path, theme_name]
    if tab_name:
        cmd.append(tab_name)

    if os.name == 'nt':
        subprocess.Popen(cmd, shell=True)
    else:
        subprocess.Popen(cmd)

if __name__ == "__main__":
    restart_app_with_theme()
"""Nuitka build script for WorkerBee (Windows onefile)."""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ENTRY = os.path.join(ROOT, "gui_launcher.py")
SRC = os.path.join(ROOT, "src")

# Bare-name modules that gui_launcher/common/etc import (same as PyInstaller hiddenimports)
BARE_MODULES = [
    "mirror", "mirror_1366", "mirror_utils", "mirror_utils_1366",
    "common", "shared_vars", "core", "compiled_runner", "exp_runner",
    "threads_runner", "luxcavation_functions", "battler", "battlepass_collector",
    "extractor", "function_runner", "headless_bridge", "audio_manager",
    "logger", "movement_detector", "mp_types", "profiles", "updater",
    "Game_Launcher", "theme_restart", "secret_store", "discord_integration",
    "paths",
]

SRC_GUI_MODULES = [
    "app_lifecycle", "chain_automation", "components", "constants",
    "dashboard_page", "exp_page", "help_page", "keyboard_handler",
    "loader", "log_handler", "logs_page", "mirror_page", "others_page",
    "process_handler", "schedule_page", "scheduler_handler", "settings_page",
    "statistics_page", "styles", "themes", "threads_page",
    "ui_updater", "utils", "discord_manager",
]


def build():
    cmd = [
        sys.executable, "-m", "nuitka",
        "--onefile",
        "--msvc=latest",
        "--assume-yes-for-downloads",
        # Exclude only genuinely unused packages. Release builds bundle
        # torch/easyocr/skimage/scipy/rapidfuzz so users get a single exe.
        "--nofollow-import-to=tensorflow",
        "--nofollow-import-to=tensorflow_lite",
        "--nofollow-import-to=pandas",
        "--nofollow-import-to=matplotlib",
        "--nofollow-import-to=sklearn",
        "--nofollow-import-to=IPython",
        "--nofollow-import-to=jupyter",
        "--nofollow-import-to=notebook",
        "--nofollow-import-to=pytest",
        "--windows-console-mode=disable",
        f"--output-filename=WorkerBee",
        f"--output-dir={os.path.join(ROOT, 'build_nuitka')}",
        f"--windows-icon-from-ico={os.path.join(ROOT, 'app_icon.ico')}",

        "--enable-plugin=tk-inter",
        "--module-parameter=torch-disable-jit=yes",

        f"--include-data-dir={os.path.join(ROOT, 'pictures')}=pictures",
        f"--include-data-dir={os.path.join(ROOT, 'audio')}=audio",
        f"--include-data-dir={os.path.join(ROOT, 'themes')}=themes",
        f"--include-data-dir={os.path.join(ROOT, 'config')}=config",
        f"--include-data-dir={os.path.join(ROOT, 'profiles')}=profiles",

        f"--include-data-files={os.path.join(ROOT, 'version.json')}=version.json",
        f"--include-data-files={os.path.join(ROOT, 'app_icon.ico')}=app_icon.ico",
        f"--include-data-files={os.path.join(ROOT, 'Help.txt')}=Help.txt",
        f"--include-data-files={os.path.join(ROOT, 'src', 'bridge', 'bridge.dll')}=src/bridge/bridge.dll",

        "--include-package=customtkinter",
        "--include-package=cv2",
        "--include-package=mss",
        "--include-package=PIL",
        "--include-package=pynput",
        "--nofollow-import-to=PyQt5",
        "--nofollow-import-to=PySide6",
        "--include-package=discord",
        "--include-package=aiohttp",
        "--include-package=requests",
        "--include-package=pathgenerator",
        # OCR stack, bundled for release
        "--include-package=easyocr",
        "--include-package=torch",
        "--include-package=torchvision",
        "--include-package=skimage",
        "--include-package=scipy",
        "--include-package=rapidfuzz",
    ]

    # Add each bare-name WorkerBee module explicitly so Nuitka finds them via SRC path
    for mod in BARE_MODULES:
        cmd.append(f"--include-module={mod}")
    for mod in SRC_GUI_MODULES:
        cmd.append(f"--include-module=src.gui.{mod}")
    cmd.append("--include-package=src")

    cmd.append(ENTRY)

    print("Running Nuitka build...")
    env = os.environ.copy()
    # Make Nuitka's import resolution see src/ as a top-level path
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = SRC + (os.pathsep + existing if existing else "")
    subprocess.run(cmd, check=True, cwd=ROOT, env=env)


if __name__ == "__main__":
    build()

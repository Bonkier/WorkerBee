import os
import sys
import shutil
import json
import time
import logging
import threading
import queue
import subprocess
import signal
import platform
import re
import webbrowser
from multiprocessing import Process, Value
from threading import Thread
from datetime import datetime

import customtkinter as ctk
import tkinter as tk
from tkinter import messagebox
import keyboard

# Import common FIRST to set up DirtyLogger before any logging setup
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
import common

#ez
# =====================================================================
# UI THEME & STYLE CONSTANTS
# =====================================================================
class UIStyle:
    """Centralized UI styling configuration"""
    FONT_FAMILY = "Segoe UI" if platform.system() == "Windows" else "Roboto"
    
    # Font configurations
    HEADER_FONT = (FONT_FAMILY, 24, "bold")
    SUBHEADER_FONT = (FONT_FAMILY, 18, "bold")
    SECTION_FONT = (FONT_FAMILY, 16, "bold")
    BODY_FONT = (FONT_FAMILY, 14)
    SMALL_FONT = (FONT_FAMILY, 12)
    
    # Layout
    PADDING_X = 20
    PADDING_Y = 10
    INNER_PADDING = 10
    SIDEBAR_WIDTH = 220
    
    # Dimensions
    BUTTON_HEIGHT = 36
    ENTRY_HEIGHT = 32
    CORNER_RADIUS = 8
    
    # Colors
    SIDEBAR_COLOR = "#212121"
    MAIN_BG_COLOR = "#1a1a1a"
    CARD_COLOR = "#2b2b2b"
    ACCENT_COLOR = "#3a7ebf"
    HOVER_COLOR = "#326599"
    TEXT_COLOR = "#ffffff"
    TEXT_SECONDARY_COLOR = "#a0a0a0"

DISCORD_INVITE = "https://discord.gg/vccsv4Q4ta"
def join_discord():
    """Open Discord invite link"""
    webbrowser.open(DISCORD_INVITE)

# Log display formatting functions

def get_timestamp():
    """Get current timestamp string"""
    return time.strftime('%d/%m/%Y %H:%M:%S')


def format_log_line_with_time_ago(line):
    """Format log line for display with proper timestamp and clean message"""
    try:
        # Expected format: DD/MM/YYYY HH:MM:SS | module | LEVEL | function:line | message
        parts = line.split(' | ', 4)
        if len(parts) >= 5:
            timestamp, module, level, func_line, message = parts
            
            # Clean message
            message = message.replace(" | DIRTY", "").strip()
            
            return f"[{timestamp.split()[1]}] {level[:1]} | {module}: {message}"
        return line.replace(" | DIRTY", "")
    except:
        return line


# =====================================================================
# Path handling
# =====================================================================

def get_correct_base_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    
    # Navigate to 'all data' if we are in 'src'
    if os.path.basename(base) == "src":
        base = os.path.dirname(base)
        
    # If we are in 'all data', that's our base
    if os.path.basename(base) == "all data":
        return os.path.dirname(base), base
        
    # Otherwise assume standard structure
    return base, os.path.join(base, "all data")

# Get correct paths
MAIN_DIR, ALL_DATA_DIR = get_correct_base_path()
BASE_PATH = ALL_DATA_DIR  # Set BASE_PATH to "all data" folder

# PID tracking using same temp directory as updater (at parent level)
TEMP_DIR = os.path.join(MAIN_DIR, "temp")  # Same level as "all data"
os.makedirs(TEMP_DIR, exist_ok=True)
PID_FILE = os.path.join(TEMP_DIR, "pid.txt")

# Write current PID immediately for batch file tracking
with open(PID_FILE, 'w') as f:
    f.write(str(os.getpid()))

# Add src to Python path for imports
sys.path.append(os.path.join(BASE_PATH, 'src'))

# Import common module for monitor functions will be done later to avoid circular imports

# Initialize logger early
logger = logging.getLogger("GUI")


class SidebarNavigation:
    """Manages sidebar navigation and page switching"""
    def __init__(self, on_change=None):
        self.pages = {}
        self.buttons = {}
        self.current_page = None
        self.on_change = on_change
        
    def add_page(self, name, frame, button):
        self.pages[name] = frame
        self.buttons[name] = button
        button.configure(command=lambda: self.show_page(name))
        
    def show_page(self, name):
        if self.current_page == name:
            return
            
        # Hide old page
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.buttons[self.current_page].configure(fg_color="transparent", text_color=UIStyle.TEXT_SECONDARY_COLOR)
            
        # Show new page
        self.pages[name].pack(fill="both", expand=True, padx=20, pady=20)
        self.buttons[name].configure(fg_color=UIStyle.ACCENT_COLOR, text_color=UIStyle.TEXT_COLOR)
        self.current_page = name
        
        if self.on_change:
            self.on_change(name)

class CardFrame(ctk.CTkFrame):
    """Standardized card container for grouping UI elements"""
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=UIStyle.CARD_COLOR, corner_radius=UIStyle.CORNER_RADIUS, **kwargs)

class ToolTip:
    """Creates a tooltip for a given widget"""
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.id = None
        self.widget.bind("<Enter>", self.schedule)
        self.widget.bind("<Leave>", self.hide)
        self.widget.bind("<ButtonPress>", self.hide)

    def schedule(self, event=None):
        self.unschedule()
        self.id = self.widget.after(500, self.show)

    def unschedule(self):
        if self.id:
            self.widget.after_cancel(self.id)
        self.id = None

    def show(self):
        x = self.widget.winfo_rootx() + 40
        y = self.widget.winfo_rooty() + 20
        
        self.tooltip_window = tk.Toplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        
        label = tk.Label(
            self.tooltip_window, 
            text=self.text, 
            justify='left',
            background="#1a1a1a", 
            fg="#ffffff",
            relief='solid', 
            borderwidth=1,
            font=(UIStyle.FONT_FAMILY, 10)
        )
        label.pack(ipadx=5, ipady=2)

    def hide(self, event=None):
        self.unschedule()
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

class SharedVars:
    """Shared variables for multiprocessing communication"""
    def __init__(self):
        self.x_offset = Value('i', 0)
        self.y_offset = Value('i', 0)
        self.game_monitor = Value('i', 1)
        self.skip_restshop = Value('b', False)
        self.skip_ego_check = Value('b', False)
        self.skip_ego_fusion = Value('b', False)
        self.skip_sinner_healing = Value('b', False)
        self.skip_ego_enhancing = Value('b', False)
        self.skip_ego_buying = Value('b', False)
        self.prioritize_list_over_status = Value('b', False)
        self.debug_image_matches = Value('b', False)
        self.hard_mode = Value('b', False)
        self.convert_images_to_grayscale = Value('b', True)
        self.reconnection_delay = Value('i', 6)
        self.reconnect_when_internet_reachable = Value('b', False)
        self.good_pc_mode = Value('b', True)
        self.click_delay = Value('f', 0.5)

# Define python interpreter path based on whether we're frozen or not
def get_python_command():
    if getattr(sys, 'frozen', False):
        # If running as exe, use the executable path to launch Python modules
        if platform.system() == "Windows":
            return os.path.join(MAIN_DIR, "gui_launcher.exe")
        else:
            return os.path.join(MAIN_DIR, "gui_launcher")
    else:
        # If running as script, use system's Python interpreter
        return sys.executable

PYTHON_CMD = get_python_command()

# Script paths
MIRROR_SCRIPT_PATH = os.path.join(BASE_PATH, "src", "compiled_runner.py")
EXP_SCRIPT_PATH = os.path.join(BASE_PATH, "src", "exp_runner.py")
THREADS_SCRIPT_PATH = os.path.join(BASE_PATH, "src", "threads_runner.py")
THEME_RESTART_PATH = os.path.join(BASE_PATH, "src", "theme_restart.py")
FUNCTION_RUNNER_PATH = os.path.join(BASE_PATH, "src", "function_runner.py")
BATTLER_SCRIPT_PATH = os.path.join(BASE_PATH, "src", "battler.py")

# Configuration file paths
CONFIG_DIR = os.path.join(BASE_PATH, "config")
JSON_PATH = os.path.join(CONFIG_DIR, "squad_order.json")
SLOW_JSON_PATH = os.path.join(CONFIG_DIR, "delayed_squad_order.json")
STATUS_SELECTION_PATH = os.path.join(CONFIG_DIR, "status_selection.json")
GUI_CONFIG_PATH = os.path.join(CONFIG_DIR, "gui_config.json")
HELP_TEXT_PATH = os.path.join(BASE_PATH, "Help.txt")
STATS_PATH = os.path.join(CONFIG_DIR, "stats.json")
SCHEDULE_PATH = os.path.join(CONFIG_DIR, "schedule.json")

# Profile configuration
PROFILES_DIR = os.path.join(BASE_PATH, "profiles")
os.makedirs(PROFILES_DIR, exist_ok=True)

PROFILE_FILES = [
    "gui_config.json",
    "squad_order.json",
    "status_selection.json",
    "pack_priority.json",
    "pack_exceptions.json",
    "grace_selection.json",
    "fusion_exceptions.json",
    "exp_team_selection.json",
    "threads_team_selection.json"
]

# Place these after the other config paths and before load_settings_tab
pack_priority_path = os.path.join(CONFIG_DIR, "pack_priority.json")
delayed_pack_priority_path = os.path.join(CONFIG_DIR, "delayed_pack_priority.json")

pack_priority_data = {}
delayed_pack_priority_data = {}

pack_dropdown_vars = {}
pack_expand_frames = {}

# Grace selection paths and data
grace_selection_path = os.path.join(CONFIG_DIR, "grace_selection.json")
grace_selection_data = {}
grace_dropdown_vars = []

# Pack exceptions paths
pack_exceptions_path = os.path.join(CONFIG_DIR, "pack_exceptions.json")
delayed_pack_exceptions_path = os.path.join(CONFIG_DIR, "delayed_pack_exceptions.json")

# Pack exceptions data
pack_exceptions_data = {}
delayed_pack_exceptions_data = {}
pack_exception_vars = {}

# Fuse exceptions paths and data
fusion_exceptions_path = os.path.join(CONFIG_DIR, "fusion_exceptions.json")
fusion_exceptions_data = []
fuse_exception_vars = {}
fuse_exception_expand_frame = None

# Pack data management functions
def load_json_data(path, default=None):
    """Generic JSON loader with error handling"""
    if default is None: default = {}
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {os.path.basename(path)}: {e}")
    return default

def save_json_data(path, data):
    """Generic JSON saver with error handling"""
    try:
        with open(path, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving {os.path.basename(path)}: {e}")

def load_pack_priority():
    global pack_priority_data
    pack_priority_data = load_json_data(pack_priority_path)
    return pack_priority_data

def save_pack_priority(data):
    save_json_data(pack_priority_path, data)

def save_delayed_pack_priority(data):
    save_json_data(delayed_pack_priority_path, data)

def delayed_pack_priority_sync():
    global delayed_pack_priority_data
    time.sleep(0.5)
    delayed_pack_priority_data.update(json.loads(json.dumps(pack_priority_data)))
    save_delayed_pack_priority(delayed_pack_priority_data)

# Grace selection management functions
def load_grace_selection():
    global grace_selection_data
    default_grace = {
            "order": {
                "Grace 1": 1,
                "Grace 2": 2,
                "Grace 3": 3,
                "Grace 4": 4,
                "Grace 5": 5
            }
        }
    grace_selection_data = load_json_data(grace_selection_path, default_grace)
    if not os.path.exists(grace_selection_path):
        save_grace_selection(grace_selection_data)
    return grace_selection_data

def save_grace_selection(data):
    save_json_data(grace_selection_path, data)

def update_grace_selection_from_dropdown(idx):
    entries = grace_dropdown_vars
    updated = {}
    for i, var in enumerate(entries):
        val = var.get()
        if val != "None":
            updated[val] = i + 1
    grace_selection_data["order"] = updated
    save_grace_selection(grace_selection_data)

def grace_dropdown_callback(index, *_):
    try:
        new_val = grace_dropdown_vars[index].get()
        if new_val == "None":
            update_grace_selection_from_dropdown(index)
            return
        for i, var in enumerate(grace_dropdown_vars):
            if i != index and var.get() == new_val:
                var.set("None")
                break
        update_grace_selection_from_dropdown(index)
    except Exception as e:
        error(f"Error in grace dropdown callback: {e}")

# Pack exceptions management functions
def load_pack_exceptions():
    global pack_exceptions_data
    pack_exceptions_data = load_json_data(pack_exceptions_path)
    return pack_exceptions_data

def save_pack_exceptions(data):
    save_json_data(pack_exceptions_path, data)

def save_delayed_pack_exceptions(data):
    save_json_data(delayed_pack_exceptions_path, data)

def delayed_pack_exceptions_sync():
    global delayed_pack_exceptions_data
    time.sleep(0.5)
    delayed_pack_exceptions_data.update(json.loads(json.dumps(pack_exceptions_data)))
    save_delayed_pack_exceptions(delayed_pack_exceptions_data)

def update_pack_exceptions_from_toggle(floor, pack):
    global pack_exceptions_data
    if floor not in pack_exceptions_data:
        pack_exceptions_data[floor] = []
    
    if pack in pack_exceptions_data[floor]:
        pack_exceptions_data[floor].remove(pack)
    else:
        pack_exceptions_data[floor].append(pack)
    
    save_pack_exceptions(pack_exceptions_data)
    threading.Thread(target=delayed_pack_exceptions_sync, daemon=True).start()

# Fuse exceptions management functions
def load_fuse_exception_images():
    """Scan pictures/CustomFuse directory and return all image files"""
    fuse_dir = os.path.join(BASE_PATH, "pictures", "CustomFuse")
    
    # Ensure CustomFuse directory exists
    if not os.path.exists(fuse_dir):
        try:
            os.makedirs(fuse_dir)
        except OSError:
            pass
            
    # Create CustomEgoGifts folder if it doesn't exist (User feature request)
    custom_gifts_dir = os.path.join(fuse_dir, "CustomEgoGifts")
    if not os.path.exists(custom_gifts_dir):
        try:
            os.makedirs(custom_gifts_dir)
        except OSError:
            pass
            
    image_extensions = ['.png', '.jpg', '.jpeg']
    fuse_items = []
    
    if os.path.exists(fuse_dir):
        for item in os.listdir(fuse_dir):
            full_path = os.path.join(fuse_dir, item)
            if os.path.isdir(full_path):
                # Use forward slashes for cross-platform compatibility
                fuse_items.append(f"pictures/CustomFuse/{item}")
            elif any(item.lower().endswith(ext) for ext in image_extensions):
                # Use forward slashes for cross-platform compatibility
                fuse_items.append(f"pictures/CustomFuse/{item}")
    
    return fuse_items

def load_fusion_exceptions():
    """Load fusion exceptions from JSON file"""
    global fusion_exceptions_data
    fusion_exceptions_data = load_json_data(fusion_exceptions_path, [])
    return fusion_exceptions_data

def save_fusion_exceptions():
    """Save currently toggled-on exceptions to fusion_exceptions.json"""
    enabled_exceptions = []
    
    for image_path, var in fuse_exception_vars.items():
        if var.get():  # If toggle is ON
            # Extract just the filename without path and extension
            # e.g., "pictures/CustomFuse/poise.png" -> "poise"
            # e.g., "pictures/CustomFuse/[keywordless]" -> "[keywordless]"
            filename = os.path.basename(image_path)
            full_path = os.path.join(BASE_PATH, image_path)
            if os.path.isdir(full_path):
                enabled_exceptions.append(filename)
            else:
                filename_without_ext = os.path.splitext(filename)[0]
                enabled_exceptions.append(filename_without_ext)
    
    # Save to JSON file
    save_json_data(fusion_exceptions_path, enabled_exceptions)
    
    # Update global data
    global fusion_exceptions_data
    fusion_exceptions_data = enabled_exceptions

def update_fuse_exception_from_toggle():
    """Called when any fuse exception toggle is changed"""
    save_fusion_exceptions()

def update_pack_priority_from_dropdown(floor, idx):
    entries = pack_dropdown_vars[floor]
    updated = {}
    for i, var in enumerate(entries):
        val = var.get()
        if val != "None":
            updated[val] = i + 1
    pack_priority_data[floor] = updated
    save_pack_priority(pack_priority_data)
    threading.Thread(target=delayed_pack_priority_sync, daemon=True).start()

def pack_dropdown_callback(floor, index, *_):
    try:
        new_val = pack_dropdown_vars[floor][index].get()
        if new_val == "None":
            update_pack_priority_from_dropdown(floor, index)
            return
        for i, var in enumerate(pack_dropdown_vars[floor]):
            if i != index and var.get() == new_val:
                old_key = next((k for k, v in delayed_pack_priority_data.get(floor, {}).items() if v == index + 1), None)
                if old_key:
                    var.set(old_key)
                break
        update_pack_priority_from_dropdown(floor, index)
    except Exception as e:
        error(f"Error in pack dropdown callback: {e}")

# Create config directory if it doesn't exist
os.makedirs(CONFIG_DIR, exist_ok=True)

LOG_FILENAME = os.path.join(BASE_PATH, "Logs.log")

# =====================================================================
# LOGGING HELPERS
# =====================================================================

# Convenience functions for different log levels
def debug(message):
    logger.debug(message)

def info(message):
    logger.info(message)

def warning(message):
    logger.warning(message)

def error(message):
    logger.error(message)

def critical(message):
    logger.critical(message)

# Module names for log filtering
LOG_MODULES = {
    "GUI": "GUI",
    "Mirror Dungeon": "compiled_runner",
    "Exp": "exp_runner",
    "Threads": "threads_runner",
    "Function": "function_runner",
    "Common": "common",
    "Core": "core",
    "Mirror": "mirror",
    "Mirror Utils": "mirror_utils",
    "Theme": "theme_restart",
    "Luxcavation": "luxcavation_functions",
    "Other": "other"
}


# =====================================================================
# GLOBAL CONSTANTS
# =====================================================================

def load_available_themes():
    """Load all theme JSON files from the themes directory"""
    themes_dir = os.path.join(BASE_PATH, "themes")
    themes = {
        "Dark": {"mode": "dark", "theme": "dark-blue"},
        "Blue Dark": {"mode": "dark", "theme": "blue"},
        "Green Dark": {"mode": "dark", "theme": "green"},
        "Light": {"mode": "light", "theme": "blue"}
    }
    
    try:
        if os.path.exists(themes_dir):
            for filename in os.listdir(themes_dir):
                if filename.endswith('.json'):
                    theme_name = os.path.splitext(filename)[0]
                    theme_path = os.path.join(themes_dir, filename)
                    
                    # Skip if it's already in our default themes
                    if theme_name in ["dark-blue", "blue", "green"]:
                        continue
                        
                    try:
                        # Validate it's a proper theme file by checking for CTk key
                        with open(theme_path, 'r') as f:
                            theme_data = json.load(f)
                            if 'CTk' in theme_data:
                                # Add custom theme with dark mode as default
                                themes[theme_name] = {"mode": "dark", "theme": theme_path}
                    except (json.JSONDecodeError, KeyError):
                        # Skip invalid theme files
                        continue
                        
    except Exception as e:
        error(f"Error loading themes: {e}")
    
    return themes

# Available themes for the UI
THEMES = load_available_themes()

# Game status columns layout
STATUS_COLUMNS = [
    ["sinking", "burn", "poise"],
    ["charge", "rupture", "slash", "blunt"],
    ["bleed", "tremor", "pierce"]
]

# Character list for the game
SINNER_LIST = [
    "Yi Sang", "Faust", "Don Quixote", "Ryōshū", "Meursault",
    "Hong Lu", "Heathcliff", "Ishmael", "Rodion", "Sinclair", "Gregor", "Outis"
]

# Team layout positioning in the grid
TEAM_ORDER = [
    ("sinking", 0, 0), ("charge", 0, 1), ("slash", 0, 2),
    ("blunt", 1, 0), ("burn", 1, 1), ("rupture", 1, 2),
    ("poise", 2, 0), ("bleed", 2, 1), ("tremor", 2, 2),
    ("pierce", 3, 0), ("None", 3, 1)
]


# =====================================================================
# GLOBAL VARIABLES
# =====================================================================


shared_vars = SharedVars()

# Global variables for data storage and state tracking
squad_data = {}
slow_squad_data = {}
checkbox_vars = {}  # For backwards compatibility (mirror team)
mirror_checkbox_vars = {}
exp_checkbox_vars = {}
threads_checkbox_vars = {}
dropdown_vars = {}
expand_frames = {}
process = None
exp_process = None
threads_process = None
function_process_list = []  # List to track multiple function processes
battle_process = None
filtered_messages_enabled = True
logging_enabled = True  # Do Not Log toggle
is_update_available = False  # Track if updates are available

# Chain automation variables
chain_running = False
chain_queue = []
current_chain_step = 0
battlepass_process = None
game_launcher_process = None

# Toggle process completion tracking
battlepass_completed = False

# Lazy loading flags
settings_tab_loaded = False
logs_tab_loaded = False

# =====================================================================
# HELPER FUNCTIONS
# =====================================================================

def load_checkbox_data():
    """Load checkbox variables at startup without creating UI elements"""
    global checkbox_vars, mirror_checkbox_vars, exp_checkbox_vars, threads_checkbox_vars
    
    # Only load if not already loaded
    if checkbox_vars and mirror_checkbox_vars and exp_checkbox_vars and threads_checkbox_vars:
        return
    
    # Load separate configurations for each tab
    mirror_prechecked = load_initial_selections("mirror")
    exp_prechecked = load_initial_selections("exp")  
    threads_prechecked = load_initial_selections("threads")
    
    # Create BooleanVar objects for each tab
    for name, row, col in TEAM_ORDER:
        # Mirror team
        mirror_var = ctk.BooleanVar(value=name in mirror_prechecked)
        mirror_checkbox_vars[name] = mirror_var
        
        # Exp team
        exp_var = ctk.BooleanVar(value=name in exp_prechecked)
        exp_checkbox_vars[name] = exp_var
        
        # Threads team
        threads_var = ctk.BooleanVar(value=name in threads_prechecked)
        threads_checkbox_vars[name] = threads_var
        
        # Backwards compatibility - use mirror for checkbox_vars
        checkbox_vars[name] = mirror_var
    

# Shared error handling decorator
def safe_execute(func):
    """Decorator for consistent error handling"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return None
    return wrapper

# Helper function for character name normalization
def sinner_key(name):
    """Convert a sinner name to a standardized key"""
    return name.lower().replace(" ", "").replace("ō", "o").replace("ū", "u")

# Functions for JSON data management
@safe_execute
def load_json():
    """Load squad data from JSON files"""
    global squad_data, slow_squad_data
    squad_data = load_json_data(JSON_PATH)
    # Copy squad to slow
    slow_squad_data = json.loads(json.dumps(squad_data))
    save_slow_json()

@safe_execute
def save_json():
    """Save squad data to JSON file"""
    save_json_data(JSON_PATH, squad_data)

@safe_execute
def save_slow_json():
    """Save slow squad data to JSON file"""
    save_json_data(SLOW_JSON_PATH, slow_squad_data)

def delayed_slow_sync():
    """Sync squad data to slow squad with delay"""
    try:
        time.sleep(0.5)
        slow_squad_data.update(json.loads(json.dumps(squad_data)))
        save_slow_json()
    except Exception as e:
        error(f"Error syncing slow squad data: {e}")

# Functions for status selection management
@safe_execute
def load_initial_selections(tab_type="mirror"):
    """Load previously selected checkboxes from JSON file for specific tab"""
    try:
        if tab_type == "mirror":
            file_path = STATUS_SELECTION_PATH
        elif tab_type == "exp":
            file_path = os.path.join(CONFIG_DIR, "exp_team_selection.json")
        elif tab_type == "threads":
            file_path = os.path.join(CONFIG_DIR, "threads_team_selection.json")
        else:
            file_path = STATUS_SELECTION_PATH
            
        data = load_json_data(file_path)
        # Extract values from numbered JSON and return as set
        return set(data.values())
    except FileNotFoundError:
        warning(f"{tab_type.title()} team selection file not found")
        return set()
    except json.JSONDecodeError:
        warning(f"{tab_type.title()} team selection file is corrupted")
        return set()

# Process state checking functions
def is_any_process_running():
    """Check if any automation is currently running"""
    return (process is not None or exp_process is not None or 
            threads_process is not None or chain_running or 
            game_launcher_process is not None)

def get_running_process_name():
    """Get the name of the currently running process"""
    if chain_running:
        return "Chain Automation"
    if process is not None:
        return "Mirror Dungeon"
    if exp_process is not None:
        return "Exp"
    if threads_process is not None:
        return "Threads"
    if game_launcher_process is not None:
        return "Game Launcher"
    return None

# Shared process conflict check
def check_process_conflict(process_name):
    """Check if another process is running and show warning"""
    if is_any_process_running():
        running_name = get_running_process_name()
        warning(f"Cannot start {process_name} while {running_name} is running")
        return True
    return False

# =====================================================================
# CONFIGURATION MANAGEMENT
# =====================================================================

# Initialize the main application window
root = ctk.CTk()
root.geometry("900x800")  # Increased default size for better spacing
root.title("WorkerBee | Bonk")
original_title = root.title()  # Store original title for later restoration

# Configuration management functions
def load_gui_config():
    """Load GUI configuration from file"""
    try:
        config_data = {}
        if os.path.exists(GUI_CONFIG_PATH):
            with open(GUI_CONFIG_PATH, 'r') as f:
                config_data = json.load(f)
    except Exception as e:
        error(f"Error loading GUI config: {e}")
        config_data = {}
    
    # Default values - only what's actually needed
    defaults = {
        'theme': 'Dark',
        'mirror_runs': 1,
        'exp_runs': 1,
        'exp_stage': 1,
        'threads_runs': 1,
        'threads_difficulty': 20,
        'window_width': 900,
        'window_height': 800,
        'clean_logs': True,
        'kill_processes_on_exit': True,
        'chain_threads_runs': 3,
        'chain_exp_runs': 2,    
        'chain_mirror_runs': 1,
        'x_offset': 0,
        'skip_restshop': False,
        'skip_ego_check': False,
        'skip_ego_fusion': False,
        'y_offset': 0,
        'game_monitor': 1,
        'debug_image_matches': False,
        'hard_mode': False,
        'convert_images_to_grayscale': True,
        'reconnection_delay': 6,
        'reconnect_when_internet_reachable': True,
        'click_delay': 0.5,
        'auto_update': False
    }
    
    # Default log filter values
    log_filter_defaults = {
        'debug': False,
        'info': False,
        'warning': True,
        'error': True,
        'critical': True
    }
    
    # Default module filter values
    module_filter_defaults = {}
    for module in LOG_MODULES:
        module_filter_defaults[module.lower().replace(' ', '_')] = True
    
    # Default keyboard shortcut values
    shortcut_defaults = {
        'mirror_dungeon': 'ctrl+q',
        'exp': 'ctrl+e',
        'threads': 'ctrl+r',
        'battle': 'ctrl+t',
        'call_function': 'ctrl+g',
        'terminate_functions': 'ctrl+shift+g',
        'chain_automation': 'ctrl+b'
    }
    
    # Ensure config structure exists
    config_needs_save = False
    
    sections = {
        'Settings': defaults,
        'LogFilters': log_filter_defaults,
        'ModuleFilters': module_filter_defaults,
        'Shortcuts': shortcut_defaults
    }
    
    for section, section_defaults in sections.items():
        if section not in config_data:
            config_data[section] = {}
            config_needs_save = True
        
        for key, value in section_defaults.items():
            if key not in config_data[section]:
                config_data[section][key] = value
                config_needs_save = True
    
    # Make sure saved theme is valid
    if config_data['Settings']['theme'] not in THEMES:
        config_data['Settings']['theme'] = 'Dark'
        config_needs_save = True
    
    if config_needs_save:
        save_gui_config(config_data)
    
    return config_data

def save_gui_config(config=None):
    """Save GUI configuration to file with error handling"""
    if config is None:
        # Create config from current state
        config = {
            'Settings': {},
            'LogFilters': {},
            'ModuleFilters': {},
            'Shortcuts': {}
        }
            
        # Add settings safely
        try:
            config['Settings'] = {
                'theme': theme_var.get() if 'theme_var' in globals() else 'Dark',
                'mirror_runs': int(entry.get()) if 'entry' in globals() and entry.get().isdigit() else 1,
                'exp_runs': int(exp_entry.get()) if 'exp_entry' in globals() and exp_entry.get().isdigit() else 1,
                'exp_stage': exp_stage_var.get() if 'exp_stage_var' in globals() and exp_stage_var.get() == "latest" else (int(exp_stage_var.get()) if 'exp_stage_var' in globals() else 1),
                'threads_runs': int(threads_entry.get()) if 'threads_entry' in globals() and threads_entry.get().isdigit() else 1,
                'threads_difficulty': threads_difficulty_var.get() if 'threads_difficulty_var' in globals() else 20,
                'window_width': root.winfo_width() if 'root' in globals() else 900,
                'window_height': root.winfo_height() if 'root' in globals() else 800,
                'clean_logs': bool(filtered_messages_enabled) if 'filtered_messages_enabled' in globals() else True,
                'logging_enabled': bool(logging_enabled) if 'logging_enabled' in globals() else True,
                'kill_processes_on_exit': True,
                'chain_threads_runs': int(chain_threads_entry.get()) if 'chain_threads_entry' in globals() and chain_threads_entry.get().isdigit() else 3,
                'chain_exp_runs': int(chain_exp_entry.get()) if 'chain_exp_entry' in globals() and chain_exp_entry.get().isdigit() else 2,
                'chain_mirror_runs': int(chain_mirror_entry.get()) if 'chain_mirror_entry' in globals() and chain_mirror_entry.get().isdigit() else 1,
                'collect_rewards_when_finished': bool(collect_rewards_var.get()) if 'collect_rewards_var' in globals() else False,
                'launch_game_before_runs': bool(launch_game_var.get()) if 'launch_game_var' in globals() else False,
                'x_offset': int(shared_vars.x_offset.value) if 'shared_vars' in globals() else 0,
                'y_offset': int(shared_vars.y_offset.value) if 'shared_vars' in globals() else 0,
                'skip_restshop': bool(shared_vars.skip_restshop.value) if 'shared_vars' in globals() else False,
                'skip_ego_check': bool(shared_vars.skip_ego_check.value) if 'shared_vars' in globals() else False,
                'skip_ego_fusion': bool(shared_vars.skip_ego_fusion.value) if 'shared_vars' in globals() else False,
                'skip_sinner_healing': bool(shared_vars.skip_sinner_healing.value) if 'shared_vars' in globals() else False,
                'skip_ego_enhancing': bool(shared_vars.skip_ego_enhancing.value) if 'shared_vars' in globals() else False,
                'skip_ego_buying': bool(shared_vars.skip_ego_buying.value) if 'shared_vars' in globals() else False,
                'prioritize_list_over_status': bool(shared_vars.prioritize_list_over_status.value) if 'shared_vars' in globals() else False,
                'game_monitor': int(shared_vars.game_monitor.value) if 'shared_vars' in globals() else 1,
                'debug_image_matches': bool(shared_vars.debug_image_matches.value) if 'shared_vars' in globals() else False,
                'hard_mode': bool(shared_vars.hard_mode.value) if 'shared_vars' in globals() else False,
                'convert_images_to_grayscale': bool(shared_vars.convert_images_to_grayscale.value) if 'shared_vars' in globals() else True,
                'reconnection_delay': int(shared_vars.reconnection_delay.value) if 'shared_vars' in globals() else 6,
                'reconnect_when_internet_reachable': bool(shared_vars.reconnect_when_internet_reachable.value) if 'shared_vars' in globals() else False,
                'good_pc_mode': bool(shared_vars.good_pc_mode.value) if 'shared_vars' in globals() else True,
                'click_delay': float(shared_vars.click_delay.value) if 'shared_vars' in globals() else 0.5,
                'auto_update': bool(auto_update_var.get()) if 'auto_update_var' in globals() else False,
            }
        except Exception as e:
            pass
        
        # Save log filter settings if they exist
        try:
            if 'log_filters' in globals():
                config['LogFilters'] = {
                    'debug': bool(log_filters['DEBUG'].get()),
                    'info': bool(log_filters['INFO'].get()),
                    'warning': bool(log_filters['WARNING'].get()),
                    'error': bool(log_filters['ERROR'].get()),
                    'critical': bool(log_filters['CRITICAL'].get())
                }
        except Exception as e:
            pass
        
        # Save module filter settings if they exist
        try:
            if 'module_filters' in globals() and 'LOG_MODULES' in globals():
                for module in LOG_MODULES:
                    config['ModuleFilters'][module.lower().replace(' ', '_')] = bool(module_filters[module].get())
        except Exception as e:
            pass
        
        # Save keyboard shortcuts if they exist
        try:
            if 'shortcut_vars' in globals():
                config['Shortcuts'] = {
                    key: var.get() for key, var in shortcut_vars.items()
                }
        except Exception as e:
            pass
    
    try:
        # Make sure the config directory exists
        os.makedirs(CONFIG_DIR, exist_ok=True)
        
        with open(GUI_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
    except Exception as e:
        error(f"Error saving GUI config: {e}")

# =====================================================================
# MONITOR CONFIGURATION FUNCTIONS
# =====================================================================

def get_available_monitors():
    try:
        monitors = common.list_available_monitors()
        monitor_options = []
        for i, monitor in enumerate(monitors, 1):
            resolution = f"{monitor['width']}x{monitor['height']}"
            monitor_options.append({
                'index': i,
                'text': f"Monitor {i} ({resolution})",
                'resolution': resolution,
                'monitor_data': monitor
            })
        return monitor_options
    except Exception as e:
        error(f"Error getting available monitors: {e}")
        return [{'index': 1, 'text': "Monitor 1 (Unknown)", 'resolution': "Unknown", 'monitor_data': {}}]


def save_monitor_config(monitor_index):
    try:
        # Use existing config loading function
        config = load_gui_config()
        
        # Ensure Settings section exists
        if 'Settings' not in config:
            config['Settings'] = {}
        
        # Update monitor setting
        config['Settings']['game_monitor'] = monitor_index
        
        with open(GUI_CONFIG_PATH, 'w') as f:
            json.dump(config, f, indent=2)
        
    except Exception as e:
        error(f"Error saving monitor config: {e}")

def update_monitor_selection(choice, shared_vars):
    try:
        monitor_index = int(choice.split()[1])
        
        shared_vars.game_monitor.value = monitor_index
        common.set_game_monitor(monitor_index)
        save_monitor_config(monitor_index)
        
        
    except Exception as e:
        error(f"Error updating monitor selection: {e}")

config = load_gui_config()
filtered_messages_enabled = config['Settings'].get('clean_logs', True)
logging_enabled = config['Settings'].get('logging_enabled', True)

def init_common_settings():
    """Initialize common module settings after import"""
    try:
        common.CLEAN_LOGS_ENABLED = filtered_messages_enabled
        # Initialize async logging safely
        common.initialize_async_logging()
        # Set logging enabled state
        if hasattr(common, 'set_logging_enabled'):
            common.set_logging_enabled(logging_enabled)
    except (ImportError, AttributeError):
        pass  # Will be set later when common is available

# Delay initialization to avoid circular imports

try:
    shared_vars.x_offset.value = config['Settings'].get('x_offset', 0)
    shared_vars.y_offset.value = config['Settings'].get('y_offset', 0)
    
    monitor_index = config['Settings'].get('game_monitor', 1)
    shared_vars.game_monitor.value = monitor_index
    
except Exception as e:
    error(f"Error loading offset values: {e}")
    shared_vars.x_offset.value = 0
    shared_vars.y_offset.value = 0
    shared_vars.game_monitor.value = 1

try:
    shared_vars.skip_restshop.value = config['Settings'].get('skip_restshop', False)
    shared_vars.skip_ego_check.value = config['Settings'].get('skip_ego_check', False)
    shared_vars.skip_ego_fusion.value = config['Settings'].get('skip_ego_fusion', False)
    shared_vars.skip_sinner_healing.value = config['Settings'].get('skip_sinner_healing', False)
    shared_vars.skip_ego_enhancing.value = config['Settings'].get('skip_ego_enhancing', False)
    shared_vars.skip_ego_buying.value = config['Settings'].get('skip_ego_buying', False)
    shared_vars.prioritize_list_over_status.value = config['Settings'].get('prioritize_list_over_status', False)
    shared_vars.debug_image_matches.value = config['Settings'].get('debug_image_matches', False)
    shared_vars.hard_mode.value = config['Settings'].get('hard_mode', False)
    shared_vars.convert_images_to_grayscale.value = config['Settings'].get('convert_images_to_grayscale', True)
    shared_vars.reconnection_delay.value = config['Settings'].get('reconnection_delay', 6)
    shared_vars.good_pc_mode.value = config['Settings'].get('good_pc_mode', True)
except Exception as e:
    error(f"Error loading automation settings: {e}")

# Create log filter UI variables from config
log_filters = {
    "DEBUG": ctk.BooleanVar(value=config['LogFilters'].get('debug', False)),
    "INFO": ctk.BooleanVar(value=config['LogFilters'].get('info', False)),
    "WARNING": ctk.BooleanVar(value=config['LogFilters'].get('warning', True)),
    "ERROR": ctk.BooleanVar(value=config['LogFilters'].get('error', True)),
    "CRITICAL": ctk.BooleanVar(value=config['LogFilters'].get('critical', True))
}

# Create module filter UI variables from config
module_filters = {}
for module in LOG_MODULES:
    key = module.lower().replace(' ', '_')
    module_filters[module] = ctk.BooleanVar(value=config['ModuleFilters'].get(key, True))

# Create keyboard shortcut variables from config
shortcut_vars = {
    'mirror_dungeon': ctk.StringVar(value=config['Shortcuts'].get('mirror_dungeon', 'ctrl+q')),
    'exp': ctk.StringVar(value=config['Shortcuts'].get('exp', 'ctrl+e')),
    'threads': ctk.StringVar(value=config['Shortcuts'].get('threads', 'ctrl+r')),
    'battle': ctk.StringVar(value=config['Shortcuts'].get('battle', 'ctrl+t')),
    'call_function': ctk.StringVar(value=config['Shortcuts'].get('call_function', 'ctrl+g')),
    'terminate_functions': ctk.StringVar(value=config['Shortcuts'].get('terminate_functions', 'ctrl+shift+g')),
    'chain_automation': ctk.StringVar(value=config['Shortcuts'].get('chain_automation', 'ctrl+b'))
}

# ==========================
# LOGGING DISPLAY HANDLER
# ==========================

class OptimizedLogHandler(logging.Handler):
    """Optimized log handler that combines file monitoring and text display"""
    
    def __init__(self, text_widget, level_filters, module_filters):
        super().__init__()
        self.text_widget = text_widget
        self.level_filters = level_filters
        self.module_filters = module_filters
        self.queue = queue.Queue()
        self.running = True
        self.update_thread = Thread(target=self._update_widget, daemon=True)
        self.update_thread.start()
        
        # Set formatter for the handler - use NoMillisecondsFormatter from common
        self.setFormatter(common.NoMillisecondsFormatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%d/%m/%Y %H:%M:%S'
        ))
        
        # File monitoring
        self.log_file_path = LOG_FILENAME
        self.last_position = 0
        
    def emit(self, record):
        """Put log message in queue for the update thread"""
        if self.running:
            self.queue.put(record)
    
    def _update_widget(self):
        """Thread that updates the text widget with new log messages"""
        while self.running:
            try:
                # Get log message from queue (with timeout to allow thread to exit)
                record = self.queue.get(block=True, timeout=0.2)
                
                # Check if we should display this level and module
                if self._should_show_record(record):
                    # Format the message and schedule GUI update
                    msg = self.format(record)
                    if self.running:  # Check again before scheduling
                        try:
                            root.after(0, self._append_log, msg)
                        except tk.TclError:
                            # Main window was destroyed, stop the handler
                            self.running = False
                            break
                
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception as e:
                # Silently ignore errors to avoid noise
                pass
    
    def _should_show_record(self, record):
        """Check if record should be displayed based on filters"""
        level_name = record.levelname
        module_name = self._get_module_name(record.name)
        
        # Check both level and module filters
        if level_name in self.level_filters and module_name in self.module_filters:
            show_level = self.level_filters[level_name].get()
            show_module = self.module_filters[module_name].get()
            
            # Check if this is a dirty log when clean logs is enabled
            if hasattr(record, 'dirty') and record.dirty and common.CLEAN_LOGS_ENABLED:
                return False
            
            return show_level and show_module and self._should_show_message(record.getMessage())
        return False
    
    def _get_module_name(self, logger_name):
        """Map logger name to module name for filtering"""
        # No need to handle __main__ conversion anymore since we use "GUI" directly
        for module, pattern in LOG_MODULES.items():
            if pattern == logger_name:
                return module
        
        return "Other"
    
    def _should_show_message(self, message):
        """Check if the message should be shown or filtered out as noise"""
        return True
    
    def _append_log(self, msg):
        """Append log message to the text widget"""
        try:
            if self.text_widget and self.running:
                # Remove DIRTY marker for display - users don't need to see it
                display_msg = msg.replace(" | DIRTY", "")
                self.text_widget.configure(state="normal")
                self.text_widget.insert("end", display_msg + "\n")
                self.text_widget.see("end")
                self.text_widget.configure(state="disabled")
        except Exception:
            pass  # Silently ignore errors during shutdown
    
    def close(self):
        """Clean up resources when handler is closed"""
        self.running = False
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            self.update_thread.join(timeout=0.1)  # Shorter timeout
        super().close()

    def filter(self, record):
        """Don't use standard filtering"""
        return True

# =====================================================================
# STATUS SELECTION MANAGEMENT
# =====================================================================

# Status selection management functions
def save_selected_statuses(tab_type="mirror"):
    """Save selected checkboxes to JSON file with numbered priorities for specific tab"""
    # Get the appropriate checkbox variables and file path
    if tab_type == "mirror":
        checkbox_vars_to_use = mirror_checkbox_vars if mirror_checkbox_vars else checkbox_vars
        file_path = STATUS_SELECTION_PATH
    elif tab_type == "exp":
        checkbox_vars_to_use = exp_checkbox_vars
        file_path = os.path.join(CONFIG_DIR, "exp_team_selection.json")
    elif tab_type == "threads":
        checkbox_vars_to_use = threads_checkbox_vars
        file_path = os.path.join(CONFIG_DIR, "threads_team_selection.json")
    else:
        checkbox_vars_to_use = checkbox_vars
        file_path = STATUS_SELECTION_PATH
    
    # Safety check
    if not checkbox_vars_to_use:
        warning(f"Attempted to save {tab_type} team before checkbox data was loaded")
        return
    
    selected = [name for name, var in checkbox_vars_to_use.items() if var.get()]
    
    # Try to read existing numbered selections
    try:
        with open(file_path, "r") as f:
            existing_data = json.load(f)
            # Convert numbered dict back to ordered list
            existing_selections = [existing_data[str(i)] for i in sorted([int(k) for k in existing_data.keys()])]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        existing_selections = []
    
    # Remove any selections that are no longer selected
    existing_selections = [s for s in existing_selections if s in selected]
    
    # Add only NEW selections to the end (keep existing order)
    for s in selected:
        if s not in existing_selections:
            # New selection, add at the end
            existing_selections.append(s)
        # If already exists, keep its current position
    
    # Convert to numbered dictionary (1-based indexing)
    numbered_data = {str(i + 1): status for i, status in enumerate(existing_selections)}
    
    # Save as JSON
    with open(file_path, "w") as f:
        json.dump(numbered_data, f, indent=4)
    
    # Reload the config cache so exp/threads functions pick up changes
    import src.shared_vars as sv
    if tab_type == "exp":
        sv.ConfigCache.reload_config("exp_team_selection")
        # Also reload the Mirror instance in exp_functions
        try:
            import exp_functions
            exp_functions.reload_exp_config()
        except ImportError:
            pass  # Module not loaded yet
    elif tab_type == "threads":
        sv.ConfigCache.reload_config("threads_team_selection")
        # Also reload the Mirror instance in threads_functions
        try:
            import threads_functions
            threads_functions.reload_threads_config()
        except ImportError:
            pass  # Module not loaded yet
    elif tab_type == "mirror":
        sv.ConfigCache.reload_config("status_selection")
    

def on_checkbox_toggle(changed_option):
    """Handle checkbox toggle events (backwards compatibility - mirror)"""
    save_selected_statuses()

# Checkbox toggle functions removed - now calling save_selected_statuses directly

# =====================================================================
# UI INTERACTION FUNCTIONS
# =====================================================================

# UI interaction functions
def populate_sinner_dropdowns(frame, status):
    """Populate the dropdown content for a specific status section (lazy loaded)"""
    # Check if already populated
    if len(frame.winfo_children()) > 0:
        return
    
    dropdown_vars[status] = []
    default_order = squad_data.get(status, {})
    reverse_map = {v: k for k, v in default_order.items()}

    for i in range(12):
        row = ctk.CTkFrame(master=frame, fg_color="transparent")
        row.pack(pady=1, anchor="w")

        label = ctk.CTkLabel(
            master=row,
            text=f"{i+1}.",
            anchor="e",
            font=UIStyle.BODY_FONT,
            text_color="#b0b0b0",
            width=30
        )
        label.pack(side="left", padx=(0, 10))

        var = ctk.StringVar()
        raw_name = reverse_map.get(i + 1)
        pretty = next((x for x in SINNER_LIST if sinner_key(x) == raw_name), "None") if raw_name else "None"
        var.set(pretty)

        def bind_callback(status=status, idx=i, v=var):
            v.trace_add("write", lambda *a: dropdown_callback(status, idx))

        dropdown = ctk.CTkOptionMenu(
            master=row,
            variable=var,
            values=SINNER_LIST + ["None"],
            width=180,
            height=UIStyle.ENTRY_HEIGHT,
            font=UIStyle.BODY_FONT,
            dropdown_font=UIStyle.BODY_FONT
        )
        dropdown.pack(side="left")
        bind_callback()
        dropdown_vars[status].append(var)

def toggle_expand(frame, arrow_var, status=None):
    """Toggle expansion of frames with lazy loading for sinner sections"""
    if frame.winfo_ismapped():
        frame.pack_forget()
        arrow_var.set("▶")
    else:
        # Lazy load content if this is a sinner assignment section
        if status and any(status in column for column in STATUS_COLUMNS):
            populate_sinner_dropdowns(frame, status)
        
        frame.pack(pady=(2, 8), fill="x")
        arrow_var.set("▼")

# Dropdown management functions
@safe_execute
def update_json_from_dropdown(status):
    """Update JSON data from dropdown selections"""
    entries = dropdown_vars[status]
    updated = {}
    for i, var in enumerate(entries):
        val = var.get()
        if val != "None":
            updated[sinner_key(val)] = i + 1
    squad_data[status] = updated
    save_json()
    threading.Thread(target=delayed_slow_sync, daemon=True).start()

def dropdown_callback(status, index, *_):
    """Handle dropdown selection changes"""
    try:
        new_val = dropdown_vars[status][index].get()
        if new_val == "None":
            update_json_from_dropdown(status)
            return

        # Check if duplicate exists
        for i, var in enumerate(dropdown_vars[status]):
            if i != index and var.get() == new_val:
                # Swap with old value from slow_squad
                old_key = next((k for k, v in slow_squad_data.get(status, {}).items() if v == index + 1), None)
                if old_key:
                    old_pretty = next((x for x in SINNER_LIST if sinner_key(x) == old_key), "None")
                    var.set(old_pretty)
                break

        update_json_from_dropdown(status)
    except Exception as e:
        error(f"Error in dropdown callback: {e}")

# ===============================
#  PROCESS MANAGEMENT FUNCTIONS
# ===============================
# Unified process termination function
def terminate_process(proc, name):
    """Unified process termination with error handling"""
    if proc:
        try:
            # Check if it's a multiprocessing.Process
            if hasattr(proc, 'terminate') and hasattr(proc, 'is_alive'):
                if proc.is_alive():
                    proc.terminate()
                    # Wait up to 3 seconds for graceful termination
                    proc.join(timeout=3)
                    # If still alive, force kill
                    if proc.is_alive():
                        proc.kill()
                        proc.join(timeout=1)
                return True
            # Handle subprocess.Popen objects
            elif hasattr(proc, 'poll'):
                if proc.poll() is None:  # Process is still running
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1)
                return True
            # Fallback to os.kill for other process types
            else:
                os.kill(proc.pid, signal.SIGTERM)
                time.sleep(1)
                try:
                    os.kill(proc.pid, 0)  # Check if process still exists
                    os.kill(proc.pid, signal.SIGKILL)  # Force kill if still running
                except ProcessLookupError:
                    pass  # Process already terminated
                return True
        except Exception as e:
            error(f"Failed to kill {name} process: {e}")
    return False

# Process management functions with unified error handling
def kill_bot():
    """Kill Mirror Dungeon subprocess"""
    global process
    if terminate_process(process, "Mirror Dungeon"):
        process = None
    if 'start_button' in globals():
        start_button.configure(text="Start")

def kill_exp_bot():
    """Kill Exp subprocess"""
    global exp_process
    if terminate_process(exp_process, "Exp"):
        exp_process = None
    if 'exp_start_button' in globals():
        exp_start_button.configure(text="Start")

def kill_threads_bot():
    """Kill Threads subprocess"""
    global threads_process
    if terminate_process(threads_process, "Threads"):
        threads_process = None
    if 'threads_start_button' in globals():
        threads_start_button.configure(text="Start")

def kill_game_launcher():
    """Kill Game Launcher subprocess"""
    global game_launcher_process
    if terminate_process(game_launcher_process, "Game Launcher"):
        game_launcher_process = None

def kill_function_runner():
    """Kill Function Runner subprocess"""
    global function_process_list
    
    # Terminate any processes in the list
    for proc in function_process_list[:]:  # Use a copy of the list for iteration
        if proc and proc.poll() is None:  # Check if process is still running
            if terminate_process(proc, "Function Runner"):
                function_process_list.remove(proc)
    
    # Update UI if buttons exist
    if 'function_terminate_button' in globals():
        function_terminate_button.configure(state="disabled")

def stop_running_process():
    """Stop whatever automation is currently running"""
    if chain_running:
        stop_chain_automation()
    elif process:
        kill_bot()
    elif exp_process:
        kill_exp_bot()
    elif threads_process:
        kill_threads_bot()
    elif game_launcher_process:
        kill_game_launcher()
    elif battle_process:
        # battle_process is a subprocess.Popen, handled differently
        try:
            os.kill(battle_process.pid, signal.SIGTERM)
        except:
            pass

def kill_battlepass():
    """Kill Battlepass Collector subprocess"""
    global battlepass_process
    if terminate_process(battlepass_process, "Battlepass Collector"):
        battlepass_process = None


def start_automation_process(process_type, button_ref, process_ref_name):
    """Unified function to start automation processes"""
    global process, exp_process, threads_process
    
    # Check for process conflicts
    if check_process_conflict(process_type):
        return
    
    # Check if this specific process is already running (toggle stop)
    current_process = globals().get(process_ref_name)
    if current_process and button_ref.cget("text") == "Stop":
        if process_type == "Mirror Dungeon":
            kill_bot()
        elif process_type == "Exp":
            kill_exp_bot()
        elif process_type == "Threads":
            kill_threads_bot()
        return
    
    try:
        if process_type == "Mirror Dungeon":
            from src import compiled_runner
            count = int(entry.get())
            new_process = Process(target=compiled_runner.main, args=(count, shared_vars), daemon=True)
        elif process_type == "Exp":
            from src import exp_runner
            runs = int(exp_entry.get())
            stage = exp_stage_var.get()
            if stage != "latest":
                stage = int(stage)
            new_process = Process(target=exp_runner.main, args=(runs, stage, shared_vars), daemon=True)
        elif process_type == "Threads":
            from src import threads_runner
            runs = int(threads_entry.get())
            difficulty = threads_difficulty_var.get()
            new_process = Process(target=threads_runner.main, args=(runs, difficulty, shared_vars), daemon=True)
        
        new_process.start()
        
        # Update global process reference
        globals()[process_ref_name] = new_process
        
        button_ref.configure(text="Stop")
        
        # Save the configuration
        save_gui_config()
        
    except Exception as e:
        error(f"Failed to start {process_type}: {e}")
        messagebox.showerror("Error", f"Failed to start {process_type}: {e}")

# Process start functions - now much simpler
def start_run():
    """Start Mirror Dungeon automation"""
    try:
        count = int(entry.get())
    except ValueError:
        messagebox.showerror("Invalid Input", "Enter a valid number of runs.")
        warning("Invalid number of runs entered for Mirror Dungeon")
        return
        
    save_selected_statuses()
    
    # Using multiprocessing instead of subprocess
    start_automation_process("Mirror Dungeon", start_button, "process")

def start_exp_run():
    """Start Exp automation"""
    try:
        runs = int(exp_entry.get())
        stage_value = exp_stage_var.get()
        
        # Handle numeric stages with validation
        if stage_value != "latest":
            stage = int(stage_value)
            if runs < 1 or stage < 1 or stage > 7:
                messagebox.showerror("Invalid Input", "Enter a valid number of runs and stage (1-7 or 'latest').")
                warning(f"Invalid input: runs={runs}, stage={stage_value}")
                return
        
        # Just validate runs for any stage value
        if runs < 1:
            messagebox.showerror("Invalid Input", "Enter a valid number of runs.")
            warning(f"Invalid input: runs={runs}")
            return
            
    except ValueError:
        messagebox.showerror("Invalid Input", "Enter valid numbers.")
        warning("Invalid numeric input for Exp automation")
        return

    # Using multiprocessing instead of subprocess
    start_automation_process("Exp", exp_start_button, "exp_process")

def start_threads_run():
    """Start Threads automation"""
    try:
        runs = int(threads_entry.get())
        difficulty_value = threads_difficulty_var.get()
        
        # Handle numeric difficulties with validation
        if difficulty_value != "latest":
            difficulty = int(difficulty_value)
            if runs < 1 or difficulty not in [20, 30, 40, 50]:
                messagebox.showerror("Invalid Input", "Enter a valid number of runs and difficulty (20, 30, 40, 50 or 'latest').")
                warning(f"Invalid input: runs={runs}, difficulty={difficulty_value}")
                return
        
        # Just validate runs for any difficulty value
        if runs < 1:
            messagebox.showerror("Invalid Input", "Enter a valid number of runs.")
            warning(f"Invalid input: runs={runs}")
            return
            
    except ValueError:
        messagebox.showerror("Invalid Input", "Enter valid numbers.")
        warning("Invalid numeric input for Threads automation")
        return
    
    # Using multiprocessing instead of subprocess
    start_automation_process("Threads", threads_start_button, "threads_process")

# =====================================================================
# CHAIN AUTOMATION FUNCTIONS
# =====================================================================

def start_chain_automation():
    """Start chain automation with Threads -> Exp -> Mirror sequence"""
    global chain_running, chain_queue, current_chain_step
    
    if chain_running:
        # Stop chain if already running
        stop_chain_automation()
        return
    
    # Check for process conflicts
    if check_process_conflict("Chain Automation"):
        return
    
    # Parse chain inputs
    try:
        threads_runs = int(chain_threads_entry.get()) if chain_threads_entry.get().strip() else 0
        exp_runs = int(chain_exp_entry.get()) if chain_exp_entry.get().strip() else 0
        mirror_runs = int(chain_mirror_entry.get()) if chain_mirror_entry.get().strip() else 0
    except ValueError:
        messagebox.showerror("Invalid Input", "Enter valid numbers for chain automation.")
        return
    
    # Build chain queue
    chain_queue = []
    if launch_game_var.get():
        chain_queue.append(("GameLauncher", 1))
    if threads_runs > 0:
        chain_queue.append(("Threads", threads_runs))
    if exp_runs > 0:
        chain_queue.append(("Exp", exp_runs))
    if mirror_runs > 0:
        chain_queue.append(("Mirror", mirror_runs))
    
    
    # Start chain
    chain_running = True
    current_chain_step = 0
    chain_start_button.configure(text="Stop Chain")
    
    # Reset toggle completion flags
    global battlepass_completed
    battlepass_completed = False
    
    chain_status_label.configure(text="Chain Status: Starting...")
    
    # Save current UI settings to config (like individual automations do)
    save_gui_config()
    
    run_next_chain_step()


def stop_chain_automation():
    """Stop chain automation"""
    global chain_running, battlepass_process, battlepass_completed
    
    chain_running = False
    
    # Reset completion flags when manually stopping
    battlepass_completed = False
    
    # Stop any currently running processes
    kill_bot()
    kill_exp_bot()
    kill_threads_bot()
    kill_game_launcher()
    
    # Stop battlepass and extractor processes if running
    if battlepass_process is not None and battlepass_process.is_alive():
        battlepass_process.terminate()
        battlepass_process.join(timeout=5)
        if battlepass_process.is_alive():
            battlepass_process.kill()
        battlepass_process = None
    
    chain_start_button.configure(text="Start Chain")
    chain_status_label.configure(text="Chain Status: Stopped")

def run_next_chain_step():
    """Run the next step in the chain automation"""
    global current_chain_step, chain_running
    
    if not chain_running or current_chain_step >= len(chain_queue):
        # Main chain completed or stopped, but keep chain_running=True if toggles will run
        if not (collect_rewards_var.get()):
            # No toggles enabled, safe to mark chain as not running
            chain_running = False
        
        # Start toggle processes sequentially to avoid race conditions
        start_next_toggle_process()
        
        # Toggle process handling is now done in start_next_toggle_process()
        return
    
    # Get current step
    automation_type, runs = chain_queue[current_chain_step]
    
    # Set appropriate status message
    if automation_type == "GameLauncher":
        status_text = f"Chain Status: Launching game - Step {current_chain_step + 1}/{len(chain_queue)}"
    else:
        status_text = f"Chain Status: Running {automation_type} ({runs} runs) - Step {current_chain_step + 1}/{len(chain_queue)}"
    chain_status_label.configure(text=status_text)
    
    # Save selected statuses for Mirror automation
    if automation_type == "Mirror":
        save_selected_statuses()
    
    try:
        if automation_type == "Threads":
            from src import threads_runner
            difficulty = threads_difficulty_var.get()
            global threads_process
            threads_process = Process(target=threads_runner.main, args=(runs, difficulty, shared_vars), daemon=True)
            threads_process.start()
            
        elif automation_type == "Exp":
            from src import exp_runner
            stage = exp_stage_var.get()
            global exp_process
            exp_process = Process(target=exp_runner.main, args=(runs, stage, shared_vars), daemon=True)
            exp_process.start()
            
        elif automation_type == "Mirror":
            from src import compiled_runner
            global process
            process = Process(target=compiled_runner.main, args=(runs, shared_vars), daemon=True)
            process.start()
            
        elif automation_type == "GameLauncher":
            from src import Game_Launcher
            global game_launcher_process
            game_launcher_process = Process(target=Game_Launcher.launch_limbus, daemon=True)
            game_launcher_process.start()
        
        # Move to next step
        current_chain_step += 1
        
        # Monitor this step completion
        monitor_chain_step()
        
    except Exception as e:
        error(f"Failed to start {automation_type} in chain: {e}")
        stop_chain_automation()

def monitor_chain_step():
    """Monitor the current chain step and proceed when done"""
    global chain_running, process, exp_process, threads_process, game_launcher_process
    
    if not chain_running:
        return
    
    # Get current step info
    if current_chain_step == 0 or current_chain_step > len(chain_queue):
        # No step started yet or chain completed
        return
    
    automation_type, runs = chain_queue[current_chain_step - 1]
    
    # Check if current process is done
    current_process = None
    process_finished = False
    
    if automation_type == "Threads":
        current_process = threads_process
        if threads_process is None or not threads_process.is_alive():
            process_finished = True
            if threads_process and not threads_process.is_alive():
                threads_process = None  # Clean up
    elif automation_type == "Exp":
        current_process = exp_process
        if exp_process is None or not exp_process.is_alive():
            process_finished = True
            if exp_process and not exp_process.is_alive():
                exp_process = None  # Clean up
    elif automation_type == "Mirror":
        current_process = process
        if process is None or not process.is_alive():
            process_finished = True
            if process and not process.is_alive():
                process = None  # Clean up
    elif automation_type == "GameLauncher":
        current_process = game_launcher_process
        if game_launcher_process is None or not game_launcher_process.is_alive():
            process_finished = True
            if game_launcher_process and not game_launcher_process.is_alive():
                game_launcher_process = None  # Clean up
    
    if process_finished:
        # Reset the button state for the completed automation
        if automation_type == "Threads" and 'threads_start_button' in globals():
            threads_start_button.configure(text="Start")
        elif automation_type == "Exp" and 'exp_start_button' in globals():
            exp_start_button.configure(text="Start")
        elif automation_type == "Mirror" and 'start_button' in globals():
            start_button.configure(text="Start")
        
        # Start next step after a small delay
        root.after(2000, run_next_chain_step)  # 2 second delay between steps
    else:
        # Still running, check again in 1 second
        root.after(1000, monitor_chain_step)

def start_next_toggle_process():
    """Start toggle processes sequentially to avoid race conditions"""
    global battlepass_process, battlepass_completed
    
    # Priority order: battlepass first, then extractor
    if collect_rewards_var.get() and not battlepass_completed and (battlepass_process is None or not battlepass_process.is_alive()):
        # Start battlepass collection
        chain_status_label.configure(text="Chain Status: Collecting rewards...")
        try:
            from src import battlepass_collector
            battlepass_process = Process(target=battlepass_collector.main, daemon=True)
            battlepass_process.start()
            # Start monitoring
            root.after(1000, monitor_toggle_processes)
            return
        except Exception as e:
            logging.error(f"Failed to collect rewards: {e}")
            chain_status_label.configure(text="Chain Status: Reward collection failed")
            battlepass_process = None
    
    
    # No toggle processes to start or all failed
    if not (collect_rewards_var.get()):
        # No toggles enabled
        chain_start_button.configure(text="Start Chain")
        chain_status_label.configure(text="Chain Status: Completed")
    else:
        # All toggles completed or failed
        global chain_running
        chain_running = False
        chain_start_button.configure(text="Start Chain")
        chain_status_label.configure(text="Chain Status: Completed")

def monitor_toggle_processes():
    """Monitor battlepass and extractor processes for completion"""
    global battlepass_process, battlepass_completed
    
    battlepass_running = battlepass_process and battlepass_process.is_alive()
    
    # Clean up finished processes and try to start next one
    process_finished = False
    
    if battlepass_process and not battlepass_process.is_alive():
        battlepass_process = None
        battlepass_completed = True
        chain_status_label.configure(text="Chain Status: Rewards collected")
        process_finished = True
    
    if process_finished:
        # A process finished, try to start the next one
        start_next_toggle_process()
        return
    
    # Still monitoring active processes
    if battlepass_running:
        root.after(1000, monitor_toggle_processes)

# =====================================================================
# FUNCTION RUNNER FUNCTIONS
# =====================================================================

def call_function():
    """Call a function using function_runner.py"""
    global function_process_list
    
    # Get the function to call
    function_name = function_entry.get().strip()
    if not function_name:
        messagebox.showerror("Invalid Input", "Please enter a function to call.")
        warning("Empty function name provided")
        return
    
    try:
        # Create an environment with the correct paths
        env = os.environ.copy()
        env['PYTHONPATH'] = BASE_PATH + os.pathsep + os.path.join(BASE_PATH, 'src')
        
        # Launch with the appropriate command
        if getattr(sys, 'frozen', False):
            command_args = [PYTHON_CMD, "-m", "src.function_runner", function_name, "--listen-stdin"]
        else:
            command_args = [sys.executable, FUNCTION_RUNNER_PATH, function_name, "--listen-stdin"]
        
        new_process = subprocess.Popen(command_args, env=env)
        
        # Add to the list of function processes
        function_process_list.append(new_process)
        function_terminate_button.configure(state="normal")
        
    except Exception as e:
        error(f"Failed to call function: {e}")
        messagebox.showerror("Error", f"Failed to call function: {e}")

def start_battle():
    """Start a battle directly using the dedicated battler.py script"""
    global battle_process
    
    # Check if there's already a battle process running
    if battle_process is not None and battle_process.poll() is None:
        # Process is still running, terminate it
        try:
            os.kill(battle_process.pid, signal.SIGTERM)
            battle_process = None
            return
        except Exception as e:
            error(f"Failed to kill battle process: {e}")
    
    # No battle process running or it's already completed, start a new battle
    try:
        # Create environment variables with correct paths
        env = os.environ.copy()
        env['PYTHONPATH'] = os.pathsep.join([BASE_PATH, os.path.join(BASE_PATH, 'src')])
        
        # Launch with the appropriate command
        if getattr(sys, 'frozen', False):
            # If frozen (exe), launch the script using the bundled Python
            new_battle_process = subprocess.Popen(
                [PYTHON_CMD, "-m", "src.battler"],
                env=env
            )
        else:
            # If script, use the regular Python command
            new_battle_process = subprocess.Popen(
                [sys.executable, BATTLER_SCRIPT_PATH],
                env=env
            )
        
        # Only track in battle_process, not in function_process_list
        battle_process = new_battle_process
        
    except Exception as e:
        error(f"Failed to start battle: {e}")
        messagebox.showerror("Error", f"Failed to start battle: {e}")

def toggle_chain_automation():
    """Toggle chain automation via keyboard shortcut"""
    if chain_running:
        stop_chain_automation()
    else:
        start_chain_automation()

def call_function_shortcut():
    """Trigger the call function button via keyboard shortcut"""
    call_function()
    
def terminate_functions_shortcut():
    """Terminate all function processes via keyboard shortcut"""
    kill_function_runner()

# Button toggle functions
def toggle_button():
    """Toggle Mirror Dungeon button state"""
    if start_button.cget("text") == "Start":
        start_run()
    else:
        kill_bot()

def toggle_exp_button():
    """Toggle Exp button state"""
    if exp_start_button.cget("text") == "Start":
        start_exp_run()
    else:
        kill_exp_bot()

def toggle_threads_button():
    """Toggle Threads button state"""
    if threads_start_button.cget("text") == "Start":
        start_threads_run()
    else:
        kill_threads_bot()

# =====================================================================
# THEME APPLICATION AND KEYBOARD SHORTCUTS
# =====================================================================

# Theme application function
def apply_theme():
    """Apply the selected theme by restarting with theme_restart.py"""
    theme_name = theme_var.get()
    if theme_name in THEMES:
        # Show feedback immediately
        theme_label = ctk.CTkLabel(
            master=root, 
            text=f"Applying {theme_name} theme...",
            font=ctk.CTkFont(size=14)
        )
        theme_label.place(relx=0.5, rely=0.5, anchor="center")
        root.update_idletasks()  # Force update to show message
        
        # Save the current configuration before restarting
        save_gui_config()
        
        
        try:
            # Start theme_restart.py with the theme name and specify "Settings" tab
            subprocess.Popen([sys.executable, THEME_RESTART_PATH, theme_name, "Settings"])
            
            # Exit immediately - no delay needed
            sys.exit(0)
        except Exception as e:
            error(f"Error applying theme: {e}")
            messagebox.showerror("Error", f"Failed to apply theme: {e}")

# Keyboard shortcut management
class KeyboardHandler:
    """Separate keyboard handler to avoid GUI blocking"""
    def __init__(self):
        self.command_queue = queue.Queue()
        self.running = False
        self.thread = None
        self.shortcuts = {}
        
    def start(self):
        """Start the keyboard handler thread"""
        if not self.running:
            self.running = True
            self.thread = threading.Thread(target=self._keyboard_worker, daemon=True)
            self.thread.start()
            
    def stop(self):
        """Stop the keyboard handler thread"""
        self.running = False
        keyboard.unhook_all()
        
    def update_shortcuts(self, shortcuts_dict):
        """Update keyboard shortcuts"""
        self.shortcuts = shortcuts_dict.copy()
        self.command_queue.put(('update_shortcuts', self.shortcuts))
        
    def _keyboard_worker(self):
        """Worker thread for keyboard handling"""
        while self.running:
            try:
                # Process commands from main thread
                try:
                    command, data = self.command_queue.get(timeout=0.1)
                    if command == 'update_shortcuts':
                        self._register_shortcuts(data)
                except queue.Empty:
                    pass
                    
            except Exception as e:
                logger.error(f"Error in keyboard worker: {e}")
                
    def _register_shortcuts(self, shortcuts_dict):
        """Register shortcuts in the keyboard thread"""
        try:
            keyboard.unhook_all()
            
            for shortcut_name, shortcut_key in shortcuts_dict.items():
                if shortcut_key and shortcut_key.strip():
                    # Queue the command instead of calling directly
                    keyboard.add_hotkey(shortcut_key, lambda name=shortcut_name: self._queue_command(name))
                    
        except Exception as e:
            logger.error(f"Error registering keyboard shortcuts: {e}")
            
    def _queue_command(self, command_name):
        """Queue command to be executed by main thread"""
        root.after(0, lambda: self._execute_command(command_name))
        
    def _execute_command(self, command_name):
        """Execute command on main thread"""
        try:
            if command_name == 'mirror_dungeon':
                toggle_button()
            elif command_name == 'exp':
                toggle_exp_button()
            elif command_name == 'threads':
                toggle_threads_button()
            elif command_name == 'battle':
                start_battle()
            elif command_name == 'call_function':
                call_function_shortcut()
            elif command_name == 'terminate_functions':
                terminate_functions_shortcut()
            elif command_name == 'chain_automation':
                toggle_chain_automation()
        except Exception as e:
            logger.error(f"Error executing keyboard command {command_name}: {e}")

# Global keyboard handler instance
keyboard_handler = KeyboardHandler()

def register_keyboard_shortcuts():
    """Register keyboard shortcuts using separate handler"""
    shortcuts_dict = {
        'mirror_dungeon': shortcut_vars['mirror_dungeon'].get(),
        'exp': shortcut_vars['exp'].get(),
        'threads': shortcut_vars['threads'].get(),
        'battle': shortcut_vars['battle'].get(),
        'call_function': shortcut_vars['call_function'].get(),
        'terminate_functions': shortcut_vars['terminate_functions'].get(),
        'chain_automation': shortcut_vars['chain_automation'].get()
    }
    
    keyboard_handler.update_shortcuts(shortcuts_dict)

# Initialize theme settings
theme_var = ctk.StringVar(value=config['Settings'].get('theme', 'Dark'))
auto_update_var = ctk.BooleanVar(value=config['Settings'].get('auto_update', False))

# Make sure theme is one of the valid ones
if theme_var.get() not in THEMES:
    theme_var.set("Dark")
    
ctk.set_appearance_mode(THEMES[theme_var.get()]["mode"])
ctk.set_default_color_theme(THEMES[theme_var.get()]["theme"])

# Set window size from config
window_width = config['Settings'].get('window_width', 433)
window_height = config['Settings'].get('window_height', 344)
root.geometry(f"{window_width}x{window_height}")

# Performance improvement: Disable complex logging at startup

# =====================================================================
# TAB LAYOUT AND UI SETUP
# =====================================================================

# Main container
main_container = ctk.CTkFrame(root, fg_color=UIStyle.MAIN_BG_COLOR)
main_container.pack(fill="both", expand=True)

# Sidebar
sidebar_frame = ctk.CTkFrame(main_container, width=UIStyle.SIDEBAR_WIDTH, fg_color=UIStyle.SIDEBAR_COLOR, corner_radius=0)
sidebar_frame.pack(side="left", fill="y")
sidebar_frame.pack_propagate(False)

# Content Area
content_area = ctk.CTkFrame(main_container, fg_color="transparent")
content_area.pack(side="right", fill="both", expand=True)

# App Title in Sidebar
app_title = ctk.CTkLabel(sidebar_frame, text="WorkerBee", font=UIStyle.HEADER_FONT, text_color=UIStyle.ACCENT_COLOR)
app_title.pack(pady=(30, 5), padx=20, anchor="w")
app_subtitle = ctk.CTkLabel(sidebar_frame, text="Macro for Limbus Company", font=UIStyle.SMALL_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
app_subtitle.pack(pady=(0, 30), padx=20, anchor="w")

# Navigation Buttons Container
nav_container = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
nav_container.pack(fill="x", padx=10)

def create_nav_btn(text, tooltip=None):
    btn = ctk.CTkButton(
        nav_container,
        text=text,
        height=40,
        anchor="w",
        fg_color="transparent",
        text_color=UIStyle.TEXT_SECONDARY_COLOR,
        hover_color=UIStyle.HOVER_COLOR,
        font=UIStyle.SECTION_FONT,
        corner_radius=UIStyle.CORNER_RADIUS
    )
    if tooltip:
        ToolTip(btn, tooltip)
    return btn

is_theme_restart = len(sys.argv) > 1 and sys.argv[1] in THEMES.keys()
load_settings_on_startup = is_theme_restart and len(sys.argv) > 2 and sys.argv[2] == "Settings"

# Add tab change event handler for lazy loading
def on_page_changed(current_page):
    """Handle tab changes and lazy load content"""
    if current_page == "Settings" and not settings_tab_loaded:
        load_settings_tab()
    elif current_page == "Logs" and not logs_tab_loaded:
        load_logs_tab()

sidebar = SidebarNavigation(on_change=on_page_changed)

# Create Pages
tab_dashboard = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Dashboard", tab_dashboard, create_nav_btn("Dashboard", "Overview and quick actions"))

tab_md = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Mirror Dungeon", tab_md, create_nav_btn("Mirror Dungeon", "Configure and run Mirror Dungeon"))

tab_exp = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Exp", tab_exp, create_nav_btn("Exp", "Configure and run Exp Luxcavation"))

tab_threads = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Threads", tab_threads, create_nav_btn("Threads", "Configure and run Thread Luxcavation"))

tab_others = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Others", tab_others, create_nav_btn("Others", "Chain automation and advanced tools"))

tab_settings = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Settings", tab_settings, create_nav_btn("Settings", "Application configuration"))

tab_stats = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Statistics", tab_stats, create_nav_btn("Statistics", "View run history and stats"))

tab_schedule = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Schedule", tab_schedule, create_nav_btn("Schedule", "Schedule automated tasks"))

tab_logs = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Logs", tab_logs, create_nav_btn("Logs", "View application logs"))

tab_help = ctk.CTkFrame(content_area, fg_color="transparent")
sidebar.add_page("Help", tab_help, create_nav_btn("Help", "Usage guide and information"))

sidebar.buttons["Dashboard"].pack(fill="x", pady=2)
sidebar.buttons["Mirror Dungeon"].pack(fill="x", pady=2)
sidebar.buttons["Exp"].pack(fill="x", pady=2)
sidebar.buttons["Threads"].pack(fill="x", pady=2)
sidebar.buttons["Others"].pack(fill="x", pady=2)
sidebar.buttons["Settings"].pack(fill="x", pady=2)
sidebar.buttons["Statistics"].pack(fill="x", pady=2)
sidebar.buttons["Schedule"].pack(fill="x", pady=2)
sidebar.buttons["Logs"].pack(fill="x", pady=2)
sidebar.buttons["Help"].pack(fill="x", pady=2)

# Sidebar Footer
sidebar_footer = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
sidebar_footer.pack(side="bottom", fill="x", padx=10, pady=20)

def get_display_version():
    try:
        v_path = os.path.join(ALL_DATA_DIR, "version.json")
        if os.path.exists(v_path):
            with open(v_path, "r") as f:
                v = f.read().strip()
                if v:
                    return f"v{v}" if v[0].isdigit() else v
    except:
        pass
    return "version not found"

version_label = ctk.CTkLabel(sidebar_footer, text=get_display_version(), font=UIStyle.SMALL_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
version_label.pack(anchor="w", padx=10)

compact_btn = ctk.CTkButton(
    sidebar_footer,
    text="Compact Mode",
    command=lambda: toggle_compact_mode(),
    height=30,
    fg_color="transparent",
    border_width=1,
    border_color=UIStyle.TEXT_SECONDARY_COLOR,
    text_color=UIStyle.TEXT_SECONDARY_COLOR,
    font=UIStyle.SMALL_FONT,
    hover_color=UIStyle.HOVER_COLOR
)
compact_btn.pack(fill="x", pady=(10, 0))

# =====================================================================
# DASHBOARD TAB
# =====================================================================
dash_scroll = ctk.CTkScrollableFrame(master=tab_dashboard, corner_radius=UIStyle.CORNER_RADIUS)
dash_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

# Welcome Card
welcome_card = CardFrame(dash_scroll)
welcome_card.pack(fill="x", padx=10, pady=10)
ctk.CTkLabel(welcome_card, text="Welcome to WorkerBee", font=UIStyle.HEADER_FONT).pack(pady=(20, 5), padx=20, anchor="w")
ctk.CTkLabel(welcome_card, text="Your automated assistant for Limbus Company.", font=UIStyle.BODY_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR).pack(pady=(0, 20), padx=20, anchor="w")

# Quick Actions Card
actions_card = CardFrame(dash_scroll)
actions_card.pack(fill="x", padx=10, pady=10)
ctk.CTkLabel(actions_card, text="Quick Actions", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10), padx=20, anchor="w")

actions_grid = ctk.CTkFrame(actions_card, fg_color="transparent")
actions_grid.pack(fill="x", padx=20, pady=(0, 20))

ctk.CTkButton(actions_grid, text="Go to Mirror Dungeon", command=lambda: sidebar.show_page("Mirror Dungeon"), height=40, font=UIStyle.BODY_FONT).pack(side="left", expand=True, fill="x", padx=5)
ctk.CTkButton(actions_grid, text="Go to Exp Luxcavation", command=lambda: sidebar.show_page("Exp"), height=40, font=UIStyle.BODY_FONT).pack(side="left", expand=True, fill="x", padx=5)
ctk.CTkButton(actions_grid, text="Go to Thread Luxcavation", command=lambda: sidebar.show_page("Threads"), height=40, font=UIStyle.BODY_FONT).pack(side="left", expand=True, fill="x", padx=5)

# Status Card
status_card = CardFrame(dash_scroll)
status_card.pack(fill="x", padx=10, pady=10)
ctk.CTkLabel(status_card, text="System Status", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10), padx=20, anchor="w")
status_label = ctk.CTkLabel(status_card, text="Idle", font=UIStyle.BODY_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
status_label.pack(pady=(0, 20), padx=20, anchor="w")
        
# Setting up the Mirror Dungeon tab
scroll = ctk.CTkScrollableFrame(master=tab_md, corner_radius=UIStyle.CORNER_RADIUS)
scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

# Run Configuration Card
run_card = CardFrame(scroll)
run_card.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(run_card, text="Run Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

# Input row
input_row = ctk.CTkFrame(run_card, fg_color="transparent")
input_row.pack(pady=(0, 10))

ctk.CTkLabel(input_row, text="Number of Runs:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
entry = ctk.CTkEntry(input_row, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT, width=80)
entry.pack(side="left")
entry.insert(0, config['Settings'].get('mirror_runs', '1'))  # Set from config

def update_mirror_runs():
    try:
        new_value = int(entry.get())
        if new_value < 1:
            raise ValueError("Must be at least 1 run")
        save_gui_config()
    except ValueError as e:
        messagebox.showerror("Invalid Input", f"Number of runs must be a valid number (minimum 1): {e}")
        entry.delete(0, 'end')
        entry.insert(0, config['Settings'].get('mirror_runs', '1'))

entry.bind('<Return>', lambda e: update_mirror_runs())

start_button = ctk.CTkButton(run_card, text="Start", command=toggle_button, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
start_button.pack(pady=(0, 20))

# Settings Card
settings_card = CardFrame(scroll)
settings_card.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(settings_card, text="Advanced Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))

master_settings_container = ctk.CTkFrame(settings_card, fg_color="transparent")
master_settings_container.pack(anchor="center", pady=(0, 15), fill="x")

# Create wrapper for the master expandable section
master_wrapper = ctk.CTkFrame(master=master_settings_container, fg_color="transparent")
master_wrapper.pack(fill="x", padx=10, pady=10)

# Create button container to keep button centered
button_container = ctk.CTkFrame(master=master_wrapper, fg_color="transparent")
button_container.pack(anchor="center")

# Create master expandable button
master_arrow_var = ctk.StringVar(value="▶")
master_settings_loaded = False

def make_master_toggle(button_ref=None):
    global master_expand_frame, master_settings_loaded
    def toggle():
        global master_settings_loaded
        toggle_expand(master_expand_frame, master_arrow_var)
        if button_ref:
            button_ref.configure(text=f"{master_arrow_var.get()} Settings")
        
        # Lazy load mirror settings only when first expanded
        if master_arrow_var.get() == "▼" and not master_settings_loaded:
            load_mirror_settings()
            master_settings_loaded = True
    return toggle

master_btn = ctk.CTkButton(
    master=button_container,
    text="▶ Settings",
    command=None,
    width=200,
    height=UIStyle.BUTTON_HEIGHT,
    font=UIStyle.SUBHEADER_FONT,
    anchor="w"
)
master_btn.configure(command=make_master_toggle(master_btn))
master_btn.pack(pady=(0, 6))

# Create the master expandable frame (hidden by default)
master_expand_frame = ctk.CTkFrame(master=master_wrapper, fg_color="transparent", corner_radius=0)
master_expand_frame.pack_forget()

def load_floor_packs():
    """Dynamically load pack names from image files in floor directories"""
    floor_packs = {}
    packs_base_dir = os.path.join(BASE_PATH, "pictures", "mirror", "packs")
    
    # Map floor keys (floor1) to folder names (f1)
    floor_mapping = {
        "floor1": "f1",
        "floor2": "f2",
        "floor3": "f3",
        "floor4": "f4",
        "floor5": "f5"
    }
    
    for floor_key, folder_name in floor_mapping.items():
        floor_dir = os.path.join(packs_base_dir, folder_name)
        packs = []
        
        if os.path.exists(floor_dir):
            for filename in os.listdir(floor_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    # Remove extension to get pack name
                    pack_name = os.path.splitext(filename)[0]
                    packs.append(pack_name)
        
        # Sort alphabetically for consistent UI
        packs.sort()
        floor_packs[floor_key] = packs
        
    return floor_packs

def load_mirror_settings():
    """Lazy load all mirror settings sections"""
    global grace_expand_frame, fuse_exception_expand_frame, pack_dropdown_vars
    load_grace_selection()
    
    # Your Team section for Mirror (at the top)
    ctk.CTkLabel(master_expand_frame, text="Your Team", font=UIStyle.SUBHEADER_FONT).pack(pady=(8, 0))
    mirror_team_frame = ctk.CTkFrame(master_expand_frame)
    mirror_team_frame.pack(pady=(0, 15))

    # Use mirror-specific checkbox variables
    if not mirror_checkbox_vars:
        load_checkbox_data()

    # Create UI elements using mirror checkbox variables
    for name, row, col in TEAM_ORDER:
        var = mirror_checkbox_vars[name]
        chk = ctk.CTkCheckBox(
            master=mirror_team_frame,
            text=name.capitalize(),
            variable=var,
            command=lambda: save_selected_statuses("mirror"),
            font=UIStyle.BODY_FONT
        )
        chk.grid(row=row, column=col, padx=5, pady=2, sticky="w")
    
    # Basic Settings section
    ctk.CTkLabel(master_expand_frame, text="Basic Settings", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(8, 0))
    
    basic_settings_container = ctk.CTkFrame(master_expand_frame)
    basic_settings_container.pack(anchor="center", pady=(0, 15))
    
    # Hard Mode checkbox
    hard_mode_var = ctk.BooleanVar(value=shared_vars.hard_mode.value)
    def update_hard_mode():
        shared_vars.hard_mode.value = hard_mode_var.get()
        save_gui_config()
    hard_mode_checkbox = ctk.CTkCheckBox(
        basic_settings_container, 
        text="Hard Mode", 
        variable=hard_mode_var,
        command=update_hard_mode,
        font=UIStyle.BODY_FONT
    )
    hard_mode_checkbox.pack(anchor="w", padx=10, pady=5)
    
    # Skip Rest Shop checkbox
    skip_restshop_var = ctk.BooleanVar(value=shared_vars.skip_restshop.value)
    def update_skip_restshop():
        shared_vars.skip_restshop.value = skip_restshop_var.get()
        save_gui_config()
    skip_restshop_cb = ctk.CTkCheckBox(
        basic_settings_container, 
        text="Skip Rest Shop in Mirror Dungeon", 
        variable=skip_restshop_var,
        command=update_skip_restshop,
        font=UIStyle.BODY_FONT
    )
    skip_restshop_cb.pack(anchor="w", padx=10, pady=5)
    
    # Skip EGO Gift Fusion checkbox
    skip_ego_fusion_var = ctk.BooleanVar(value=shared_vars.skip_ego_fusion.value)
    def update_skip_ego_fusion():
        shared_vars.skip_ego_fusion.value = skip_ego_fusion_var.get()
        save_gui_config()
    skip_ego_fusion_cb = ctk.CTkCheckBox(
        basic_settings_container,
        text="Skip EGO gift fusion",
        variable=skip_ego_fusion_var,
        command=update_skip_ego_fusion,
        font=UIStyle.BODY_FONT
    )
    skip_ego_fusion_cb.pack(anchor="w", padx=10, pady=5)
    
    # Skip EGO Healing checkbox
    skip_sinner_healing_var = ctk.BooleanVar(value=shared_vars.skip_sinner_healing.value)
    def update_skip_sinner_healing():
        shared_vars.skip_sinner_healing.value = skip_sinner_healing_var.get()
        save_gui_config()
    skip_sinner_healing_cb = ctk.CTkCheckBox(
        basic_settings_container,
        text="Skip sinner healing",
        variable=skip_sinner_healing_var,
        command=update_skip_sinner_healing,
        font=UIStyle.BODY_FONT
    )
    skip_sinner_healing_cb.pack(anchor="w", padx=10, pady=5)
    
    # Skip EGO Enhancing checkbox
    skip_ego_enhancing_var = ctk.BooleanVar(value=shared_vars.skip_ego_enhancing.value)
    def update_skip_ego_enhancing():
        shared_vars.skip_ego_enhancing.value = skip_ego_enhancing_var.get()
        save_gui_config()
    skip_ego_enhancing_cb = ctk.CTkCheckBox(
        basic_settings_container,
        text="Skip EGO gift enhancing",
        variable=skip_ego_enhancing_var,
        command=update_skip_ego_enhancing,
        font=UIStyle.BODY_FONT
    )
    skip_ego_enhancing_cb.pack(anchor="w", padx=10, pady=5)
    
    # Skip EGO Buying checkbox
    skip_ego_buying_var = ctk.BooleanVar(value=shared_vars.skip_ego_buying.value)
    def update_skip_ego_buying():
        shared_vars.skip_ego_buying.value = skip_ego_buying_var.get()
        save_gui_config()
    skip_ego_buying_cb = ctk.CTkCheckBox(
        basic_settings_container,
        text="Skip EGO gift buying",
        variable=skip_ego_buying_var,
        command=update_skip_ego_buying,
        font=UIStyle.BODY_FONT
    )
    skip_ego_buying_cb.pack(anchor="w", padx=10, pady=5)
    
    # Prioritize Pack List checkbox
    prioritize_list_var = ctk.BooleanVar(value=shared_vars.prioritize_list_over_status.value)
    def update_prioritize_list():
        shared_vars.prioritize_list_over_status.value = prioritize_list_var.get()
        save_gui_config()
    prioritize_list_cb = ctk.CTkCheckBox(
        basic_settings_container, 
        text="Prioritize Pack List Over Status Gifts", 
        variable=prioritize_list_var,
        command=update_prioritize_list,
        font=UIStyle.BODY_FONT
    )
    prioritize_list_cb.pack(anchor="w", padx=10, pady=5)
    
    # Grace Selection section
    ctk.CTkLabel(master_expand_frame, text="Grace Selection", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(8, 0))

    # Define grace names and coordinates
    GRACE_NAMES = ["star of the beniggening", "cumulating starcloud", "interstellar travel", "star shower", "binary star shop", "moon star shop", "favor of the nebula", "starlight guidance", "chance comet", "perfected possibility"]

    grace_container = ctk.CTkFrame(master_expand_frame)
    grace_container.pack(anchor="center", pady=(0, 15))

    # Create wrapper for the expandable section
    wrapper = ctk.CTkFrame(master=grace_container, fg_color="transparent")
    wrapper.pack(fill="x", padx=10, pady=10)

    # Create expandable button
    arrow_var = ctk.StringVar(value="▶")

    def make_grace_toggle(button_ref=None):
        global grace_expand_frame
        def toggle():
            toggle_expand(grace_expand_frame, arrow_var)
            if button_ref:
                button_ref.configure(text=f"{arrow_var.get()} Grace Selection")
        return toggle

    btn = ctk.CTkButton(
        master=wrapper,
        text="▶ Grace Selection",
        command=None,
        width=200,
        height=UIStyle.BUTTON_HEIGHT,
        font=UIStyle.SUBHEADER_FONT,
        anchor="w"
    )
    btn.configure(command=make_grace_toggle(btn))
    btn.pack(anchor="w", pady=(0, 6))

    # Create the expandable frame (hidden by default)
    grace_expand_frame = ctk.CTkFrame(master=wrapper, fg_color="transparent", corner_radius=0)
    grace_expand_frame.pack_forget()

    default_order = grace_selection_data.get("order", {})
    reverse_map = {v: k for k, v in default_order.items()}

    for i in range(10):
        rowf = ctk.CTkFrame(master=grace_expand_frame, fg_color="transparent")
        rowf.pack(pady=1, anchor="w")

        label = ctk.CTkLabel(
            master=rowf,
            text=f"{i+1}.",
            anchor="e",
            font=UIStyle.BODY_FONT,
            text_color="#b0b0b0",
            width=30
        )
        label.pack(side="left", padx=(0, 10))

        var = ctk.StringVar()
        raw_name = reverse_map.get(i + 1)
        pretty = raw_name if raw_name else "None"
        var.set(pretty)

        def bind_callback(idx=i, v=var):
            v.trace_add("write", lambda *a: grace_dropdown_callback(idx))

        dropdown = ctk.CTkOptionMenu(
            master=rowf,
            variable=var,
            values=GRACE_NAMES + ["None"],
            width=160,
            height=UIStyle.ENTRY_HEIGHT,
            font=UIStyle.BODY_FONT,
            dropdown_font=UIStyle.BODY_FONT,
            dynamic_resizing=False
        )
        dropdown.pack(side="left")
        bind_callback()
        grace_dropdown_vars.append(var)

    # Initialize required variables and data for mirror settings
    load_pack_priority()
    load_pack_exceptions()
    load_fusion_exceptions()

    delayed_pack_priority_data = json.loads(json.dumps(pack_priority_data))
    delayed_pack_exceptions_data = json.loads(json.dumps(pack_exceptions_data))
    save_delayed_pack_priority(delayed_pack_priority_data)
    save_delayed_pack_exceptions(delayed_pack_exceptions_data)

    pack_dropdown_vars = {}
    pack_expand_frames = {}
    pack_exception_expand_frames = {}

    # Pack Priority section
    ctk.CTkLabel(master_expand_frame, text="Pack Priority", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(8, 0))

    # Define floors and floor labels
    FLOORS = [f"floor{i}" for i in range(1, 6)]
    floor_labels = [f"Floor {i}" for i in range(1, 6)]
    PACK_COLUMNS = [["floor1", "floor2"], ["floor3", "floor4"], ["floor5"]]

    # Define packs for each floor
    FLOOR_PACKS = load_floor_packs()

    pack_container = ctk.CTkFrame(master_expand_frame)
    pack_container.pack(anchor="center", pady=(0, 15))

    for col_idx, group in enumerate(PACK_COLUMNS):
        col = ctk.CTkFrame(pack_container, fg_color="transparent")
        col.grid(row=0, column=col_idx, padx=15, pady=10, sticky="n")

        for row_idx, floor in enumerate(group):
            wrapper = ctk.CTkFrame(master=col, fg_color="transparent")
            wrapper.grid(row=row_idx, column=0, sticky="nw")

            idx = FLOORS.index(floor)
            arrow_var = ctk.StringVar(value="▶")

            def make_toggle(f=floor, arrow=arrow_var, button_ref=None, floor_idx=idx):
                def toggle():
                    toggle_expand(pack_expand_frames[f], arrow)
                    if button_ref:
                        button_ref.configure(text=f"{arrow.get()} {floor_labels[floor_idx]}")
                return toggle

            btn = ctk.CTkButton(
                master=wrapper,
                text=f"▶ {floor_labels[idx]}",
                command=None,
                width=200,
                height=UIStyle.BUTTON_HEIGHT,
                font=UIStyle.SUBHEADER_FONT,
                anchor="w"
            )
            btn.configure(command=make_toggle(floor, arrow_var, btn))
            btn.pack(anchor="w", pady=(0, 6))

            frame = ctk.CTkFrame(master=wrapper, fg_color="transparent", corner_radius=0)
            pack_expand_frames[floor] = frame
            frame.pack_forget()

            pack_dropdown_vars[floor] = []
            default_order = pack_priority_data.get(floor, {})
            reverse_map = {v: k for k, v in default_order.items()}
            pack_names = FLOOR_PACKS[floor]
            max_packs = len(pack_names)

            for i in range(max_packs):
                rowf = ctk.CTkFrame(master=frame, fg_color="transparent")
                rowf.pack(pady=1, anchor="w")

                label = ctk.CTkLabel(
                    master=rowf,
                    text=f"{i+1}.",
                    anchor="e",
                    font=UIStyle.BODY_FONT,
                    text_color="#b0b0b0",
                    width=30
                )
                label.pack(side="left", padx=(0, 10))

                var = ctk.StringVar()
                raw_name = reverse_map.get(i + 1)
                pretty = raw_name if raw_name else "None"
                var.set(pretty)

                def bind_callback(floor=floor, idx=i, v=var):
                    v.trace_add("write", lambda *a: pack_dropdown_callback(floor, idx))

                dropdown = ctk.CTkOptionMenu(
                    master=rowf,
                    variable=var,
                    values=pack_names + ["None"],
                    width=160,
                    height=UIStyle.ENTRY_HEIGHT,
                    font=UIStyle.BODY_FONT,
                    dropdown_font=UIStyle.BODY_FONT
                )
                dropdown.pack(side="left")
                bind_callback()
                pack_dropdown_vars[floor].append(var)

    # Pack Exceptions section
    ctk.CTkLabel(master_expand_frame, text="Pack Exceptions", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(8, 0))

    pack_exceptions_container = ctk.CTkFrame(master_expand_frame)
    pack_exceptions_container.pack(anchor="center", pady=(0, 15))

    for col_idx, group in enumerate(PACK_COLUMNS):
        col = ctk.CTkFrame(pack_exceptions_container, fg_color="transparent")
        col.grid(row=0, column=col_idx, padx=15, pady=10, sticky="n")

        for row_idx, floor in enumerate(group):
            wrapper = ctk.CTkFrame(master=col, fg_color="transparent")
            wrapper.grid(row=row_idx, column=0, sticky="nw")

            idx = FLOORS.index(floor)
            arrow_var = ctk.StringVar(value="▶")

            def make_toggle(f=floor, arrow=arrow_var, button_ref=None, floor_idx=idx):
                def toggle():
                    toggle_expand(pack_exception_expand_frames[f], arrow)
                    if button_ref:
                        button_ref.configure(text=f"{arrow.get()} {floor_labels[floor_idx]}")
                return toggle

            btn = ctk.CTkButton(
                master=wrapper,
                text=f"▶ {floor_labels[idx]}",
                command=None,
                width=200,
                height=UIStyle.BUTTON_HEIGHT,
                font=UIStyle.SUBHEADER_FONT,
                anchor="w"
            )
            btn.configure(command=make_toggle(floor, arrow_var, btn))
            btn.pack(anchor="w", pady=(0, 6))

            frame = ctk.CTkFrame(master=wrapper, fg_color="transparent", corner_radius=0)
            pack_exception_expand_frames[floor] = frame
            frame.pack_forget()

            # Initialize exception vars for this floor
            if floor not in pack_exception_vars:
                pack_exception_vars[floor] = {}
            if floor not in pack_exceptions_data:
                pack_exceptions_data[floor] = []
            
            # Create exceptions container with single column
            exceptions_container = ctk.CTkFrame(frame, fg_color="transparent")
            exceptions_container.pack(anchor="w", padx=20, fill="x")
            
            # Create checkboxes in single column - sync with pack_exceptions.json
            packs = FLOOR_PACKS[floor]
            for pack in packs:
                var = ctk.BooleanVar(value=pack in pack_exceptions_data.get(floor, []))
                def make_toggle_callback(floor=floor, pack=pack, var=var):
                    return lambda: update_pack_exceptions_from_toggle(floor, pack)
                cb = ctk.CTkCheckBox(
                    exceptions_container,
                    text=pack,
                    variable=var,
                    command=make_toggle_callback(),
                    font=UIStyle.SMALL_FONT
                )
                cb.pack(anchor="w", pady=1)
                pack_exception_vars[floor][pack] = var

    # Fuse Exceptions section
    ctk.CTkLabel(master_expand_frame, text="Fuse Exceptions", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(8, 0))

    # Create fuse exceptions container
    fuse_exceptions_container = ctk.CTkFrame(master_expand_frame)
    fuse_exceptions_container.pack(anchor="center", pady=(0, 15))

    # Create fuse exceptions expandable section
    fuse_images = load_fuse_exception_images()

    if fuse_images:
        # Create wrapper for the expandable section
        wrapper = ctk.CTkFrame(master=fuse_exceptions_container, fg_color="transparent")
        wrapper.pack(fill="x", padx=10, pady=10)
        
        # Create expandable button
        arrow_var = ctk.StringVar(value="▶")
        
        def make_fuse_toggle(button_ref=None):
            global fuse_exception_expand_frame
            def toggle():
                toggle_expand(fuse_exception_expand_frame, arrow_var)
                if button_ref:
                    button_ref.configure(text=f"{arrow_var.get()} Fuse Exceptions")
            return toggle
        
        btn = ctk.CTkButton(
            master=wrapper,
            text="▶ Fuse Exceptions",
            command=None,
            width=200,
            height=UIStyle.BUTTON_HEIGHT,
            font=UIStyle.SUBHEADER_FONT,
            anchor="w"
        )
        btn.configure(command=make_fuse_toggle(btn))
        btn.pack(pady=(0, 6))
        
        # Create the expandable frame (hidden by default)
        fuse_exception_expand_frame = ctk.CTkFrame(master=wrapper, fg_color="transparent", corner_radius=0)
        fuse_exception_expand_frame.pack_forget()
        
        # Create checkboxes container
        exceptions_container = ctk.CTkFrame(fuse_exception_expand_frame, fg_color="transparent")
        exceptions_container.pack(anchor="w", padx=20, fill="x")
        
        # Helper to create checkbox
        def add_exception_checkbox(path, parent):
            filename = os.path.basename(path)
            full_path = os.path.join(BASE_PATH, path)
            if os.path.isdir(full_path):
                display_name = filename
            else:
                display_name = os.path.splitext(filename)[0]
            
            var = ctk.BooleanVar(value=display_name in fusion_exceptions_data)
            fuse_exception_vars[path] = var
            
            checkbox = ctk.CTkCheckBox(
                parent,
                text=display_name,
                variable=var,
                command=update_fuse_exception_from_toggle,
                font=UIStyle.SMALL_FONT
            )
            checkbox.pack(anchor="w", pady=1)

        # Separate CustomEgoGifts from other items
        custom_gifts_path = None
        other_items = []
        
        for item in fuse_images:
            if os.path.basename(item) == "CustomEgoGifts":
                custom_gifts_path = item
            else:
                other_items.append(item)

        # Add CustomEgoGifts first if it exists
        if custom_gifts_path:
            add_exception_checkbox(custom_gifts_path, exceptions_container)
            # Add separator if there are other items
            if other_items:
                separator = ctk.CTkFrame(exceptions_container, height=2, fg_color="#404040")
                separator.pack(fill="x", pady=5)
        
        # Add other items
        for image_path in other_items:
            add_exception_checkbox(image_path, exceptions_container)
    else:
        # Show message if no images found
        no_images_label = ctk.CTkLabel(
            fuse_exceptions_container, 
            text="No images found in pictures/CustomFuse directory", 
            font=UIStyle.SMALL_FONT
        )
        no_images_label.pack(pady=10)

# Setting up the Exp tab
exp_scroll = ctk.CTkScrollableFrame(master=tab_exp, corner_radius=UIStyle.CORNER_RADIUS)
exp_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

# Run Configuration Card
exp_run_card = CardFrame(exp_scroll)
exp_run_card.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(exp_run_card, text="Run Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

exp_input_row = ctk.CTkFrame(exp_run_card, fg_color="transparent")
exp_input_row.pack(pady=(0, 10))

ctk.CTkLabel(exp_input_row, text="Number of Runs:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
exp_entry = ctk.CTkEntry(exp_input_row, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT, width=80)
exp_entry.pack(side="left")
exp_entry.insert(0, config['Settings'].get('exp_runs', '1'))  # Set from config

def update_exp_runs():
    """Update exp runs from entry field"""
    try:
        new_value = int(exp_entry.get())
        if new_value < 1:
            raise ValueError("Must be at least 1 run")
        save_gui_config()
    except ValueError as e:
        messagebox.showerror("Invalid Input", f"Number of runs must be a valid number (minimum 1): {e}")
        exp_entry.delete(0, 'end')
        exp_entry.insert(0, config['Settings'].get('exp_runs', '1'))

exp_entry.bind('<Return>', lambda e: update_exp_runs())

ctk.CTkLabel(exp_run_card, text="Choose Stage:", font=UIStyle.BODY_FONT).pack(pady=(10, 5))
exp_stage_var = ctk.StringVar(value=config['Settings'].get('exp_stage', '1'))  # Set from config
exp_stage_dropdown = ctk.CTkOptionMenu(
    master=exp_run_card,
    variable=exp_stage_var,
    values=["1", "2", "3", "4", "5", "6", "7", "latest"],
    width=200,
    height=UIStyle.ENTRY_HEIGHT,
    font=UIStyle.BODY_FONT,
    dropdown_font=UIStyle.BODY_FONT
)
exp_stage_dropdown.pack(pady=(0, 10))

exp_start_button = ctk.CTkButton(exp_run_card, text="Start", command=toggle_exp_button, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
exp_start_button.pack(pady=(10, 20))

# Settings Card
exp_settings_card = CardFrame(exp_scroll)
exp_settings_card.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(exp_settings_card, text="Advanced Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))

# Exp Settings Container
exp_settings_container = ctk.CTkFrame(exp_settings_card, fg_color="transparent")
exp_settings_container.pack(anchor="center", pady=(0, 15), fill="x")

# Create wrapper for the exp expandable section
exp_wrapper = ctk.CTkFrame(master=exp_settings_container, fg_color="transparent")
exp_wrapper.pack(fill="x", padx=10, pady=10)

# Create button container to keep button centered
exp_button_container = ctk.CTkFrame(master=exp_wrapper, fg_color="transparent")
exp_button_container.pack(anchor="center")

# Create exp expandable button
exp_arrow_var = ctk.StringVar(value="▶")
exp_settings_loaded = False

def make_exp_toggle(button_ref=None):
    global exp_expand_frame, exp_settings_loaded
    def toggle():
        global exp_settings_loaded
        toggle_expand(exp_expand_frame, exp_arrow_var)
        if button_ref:
            button_ref.configure(text=f"{exp_arrow_var.get()} Settings")
        
        # Lazy load exp settings only when first expanded
        if exp_arrow_var.get() == "▼" and not exp_settings_loaded:
            load_exp_settings()
            exp_settings_loaded = True
    return toggle

exp_btn = ctk.CTkButton(
    master=exp_button_container,
    text="▶ Settings",
    command=None,
    width=200,
    height=UIStyle.BUTTON_HEIGHT,
    font=UIStyle.SUBHEADER_FONT,
    anchor="w"
)
exp_btn.configure(command=make_exp_toggle(exp_btn))
exp_btn.pack(pady=(0, 6))

# Create the exp expandable frame (hidden by default)
exp_expand_frame = ctk.CTkFrame(master=exp_wrapper, fg_color="transparent", corner_radius=0)
exp_expand_frame.pack_forget()

def load_exp_settings():
    """Lazy load all exp settings sections"""
    
    # Your Team section for Exp
    ctk.CTkLabel(exp_expand_frame, text="Your Team", font=UIStyle.SUBHEADER_FONT).pack(pady=(8, 0))
    exp_team_frame = ctk.CTkFrame(exp_expand_frame)
    exp_team_frame.pack(pady=(0, 15))

    # Use exp-specific checkbox variables
    if not exp_checkbox_vars:
        load_checkbox_data()

    # Create UI elements using exp checkbox variables
    for name, row, col in TEAM_ORDER:
        var = exp_checkbox_vars[name]
        chk = ctk.CTkCheckBox(
            master=exp_team_frame,
            text=name.capitalize(),
            variable=var,
            command=lambda: save_selected_statuses("exp"),
            font=UIStyle.BODY_FONT
        )
        chk.grid(row=row, column=col, padx=5, pady=2, sticky="w")

# Setting up the Threads tab
threads_scroll = ctk.CTkScrollableFrame(master=tab_threads, corner_radius=UIStyle.CORNER_RADIUS)
threads_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

# Run Configuration Card
threads_run_card = CardFrame(threads_scroll)
threads_run_card.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(threads_run_card, text="Run Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

threads_input_row = ctk.CTkFrame(threads_run_card, fg_color="transparent")
threads_input_row.pack(pady=(0, 10))

ctk.CTkLabel(threads_input_row, text="Number of Runs:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
threads_entry = ctk.CTkEntry(threads_input_row, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT, width=80)
threads_entry.pack(side="left")
threads_entry.insert(0, config['Settings'].get('threads_runs', '1'))  # Set from config

def update_threads_runs():
    """Update threads runs from entry field"""
    try:
        new_value = int(threads_entry.get())
        if new_value < 1:
            raise ValueError("Must be at least 1 run")
        save_gui_config()
    except ValueError as e:
        messagebox.showerror("Invalid Input", f"Number of runs must be a valid number (minimum 1): {e}")
        threads_entry.delete(0, 'end')
        threads_entry.insert(0, config['Settings'].get('threads_runs', '1'))

threads_entry.bind('<Return>', lambda e: update_threads_runs())

ctk.CTkLabel(threads_run_card, text="Choose Difficulty:", font=UIStyle.BODY_FONT).pack(pady=(10, 5))
threads_difficulty_var = ctk.StringVar(value=config['Settings'].get('threads_difficulty', '20'))  # Set from config
threads_difficulty_dropdown = ctk.CTkOptionMenu(
    master=threads_run_card,
    variable=threads_difficulty_var,
    values=["20", "30", "40", "50", "latest"],
    width=200,
    height=UIStyle.ENTRY_HEIGHT,
    font=UIStyle.BODY_FONT,
    dropdown_font=UIStyle.BODY_FONT
)
threads_difficulty_dropdown.pack(pady=(0, 10))

threads_start_button = ctk.CTkButton(threads_run_card, text="Start", command=toggle_threads_button, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
threads_start_button.pack(pady=(10, 20))

# Settings Card
threads_settings_card = CardFrame(threads_scroll)
threads_settings_card.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(threads_settings_card, text="Advanced Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))

# Threads Settings Container
threads_settings_container = ctk.CTkFrame(threads_settings_card, fg_color="transparent")
threads_settings_container.pack(anchor="center", pady=(0, 15), fill="x")

# Create wrapper for the threads expandable section
threads_wrapper = ctk.CTkFrame(master=threads_settings_container, fg_color="transparent")
threads_wrapper.pack(fill="x", padx=10, pady=10)

# Create button container to keep button centered
threads_button_container = ctk.CTkFrame(master=threads_wrapper, fg_color="transparent")
threads_button_container.pack(anchor="center")

# Create threads expandable button
threads_arrow_var = ctk.StringVar(value="▶")
threads_settings_loaded = False

def make_threads_toggle(button_ref=None):
    global threads_expand_frame, threads_settings_loaded
    def toggle():
        global threads_settings_loaded
        toggle_expand(threads_expand_frame, threads_arrow_var)
        if button_ref:
            button_ref.configure(text=f"{threads_arrow_var.get()} Settings")
        
        # Lazy load threads settings only when first expanded
        if threads_arrow_var.get() == "▼" and not threads_settings_loaded:
            load_threads_settings()
            threads_settings_loaded = True
    return toggle

threads_btn = ctk.CTkButton(
    master=threads_button_container,
    text="▶ Settings",
    command=None,
    width=200,
    height=UIStyle.BUTTON_HEIGHT,
    font=UIStyle.SUBHEADER_FONT,
    anchor="w"
)
threads_btn.configure(command=make_threads_toggle(threads_btn))
threads_btn.pack(pady=(0, 6))

# Create the threads expandable frame (hidden by default)
threads_expand_frame = ctk.CTkFrame(master=threads_wrapper, fg_color="transparent", corner_radius=0)
threads_expand_frame.pack_forget()

def load_threads_settings():
    """Lazy load all threads settings sections"""
    
    # Your Team section for Threads
    ctk.CTkLabel(threads_expand_frame, text="Your Team", font=UIStyle.SUBHEADER_FONT).pack(pady=(8, 0))
    threads_team_frame = ctk.CTkFrame(threads_expand_frame)
    threads_team_frame.pack(pady=(0, 15))

    # Use threads-specific checkbox variables
    if not threads_checkbox_vars:
        load_checkbox_data()

    # Create UI elements using threads checkbox variables
    for name, row, col in TEAM_ORDER:
        var = threads_checkbox_vars[name]
        chk = ctk.CTkCheckBox(
            master=threads_team_frame,
            text=name.capitalize(),
            variable=var,
            command=lambda: save_selected_statuses("threads"),
            font=UIStyle.BODY_FONT
        )
        chk.grid(row=row, column=col, padx=5, pady=2, sticky="w")

# =====================================================================
# OTHERS TAB
# =====================================================================

# Setting up the Others tab
others_scroll = ctk.CTkScrollableFrame(master=tab_others, corner_radius=UIStyle.CORNER_RADIUS)
others_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

# Chain Functions Card
chain_card = CardFrame(others_scroll)
chain_card.pack(fill="x", padx=10, pady=10)

# Chain Functions section
ctk.CTkLabel(chain_card, text="Chain Functions", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))

chain_help = ctk.CTkLabel(
    chain_card, 
    text="Run automations in sequence: Threads → Exp → Mirror. Enter 0 to skip.",
    font=UIStyle.SMALL_FONT,
    text_color="gray"
)
chain_help.pack(pady=(0, 10))

# Chain input frame
chain_frame = ctk.CTkFrame(chain_card, fg_color="transparent")
chain_frame.pack(pady=(0, 10), padx=20, fill="x")

# Launch game toggle
launch_game_frame = ctk.CTkFrame(chain_frame, fg_color="transparent")
launch_game_frame.pack(pady=2)
launch_game_var = ctk.BooleanVar(value=config['Settings'].get('launch_game_before_runs', False))
launch_game_checkbox = ctk.CTkCheckBox(launch_game_frame, text="Launch Game before runs", variable=launch_game_var, command=save_gui_config, font=UIStyle.BODY_FONT)
launch_game_checkbox.pack(side="left", padx=(10, 10))
# Threads input
threads_chain_frame = ctk.CTkFrame(chain_frame, fg_color="transparent")
threads_chain_frame.pack(pady=2)
ctk.CTkLabel(threads_chain_frame, text="Threads Runs:", width=100, anchor="w", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 5))
chain_threads_entry = ctk.CTkEntry(threads_chain_frame, width=80, font=UIStyle.BODY_FONT)
chain_threads_entry.pack(side="left", anchor="w", padx=(0, 10))
chain_threads_entry.insert(0, config['Settings'].get('chain_threads_runs', '3'))

def update_chain_threads_runs():
    """Update chain threads runs from entry field"""
    try:
        new_value = int(chain_threads_entry.get())
        if new_value < 0:
            raise ValueError("Must be 0 or greater")
        save_gui_config()
    except ValueError as e:
        messagebox.showerror("Invalid Input", f"Chain threads runs must be a valid number (minimum 0): {e}")
        chain_threads_entry.delete(0, 'end')
        chain_threads_entry.insert(0, config['Settings'].get('chain_threads_runs', '3'))

chain_threads_entry.bind('<Return>', lambda e: update_chain_threads_runs())

# Exp input
exp_chain_frame = ctk.CTkFrame(chain_frame, fg_color="transparent")
exp_chain_frame.pack(pady=2)
ctk.CTkLabel(exp_chain_frame, text="Exp Runs:", width=100, anchor="w", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 5))
chain_exp_entry = ctk.CTkEntry(exp_chain_frame, width=80, font=UIStyle.BODY_FONT)
chain_exp_entry.pack(side="left", anchor="w", padx=(0, 10))
chain_exp_entry.insert(0, config['Settings'].get('chain_exp_runs', '2'))

def update_chain_exp_runs():
    """Update chain exp runs from entry field"""
    try:
        new_value = int(chain_exp_entry.get())
        if new_value < 0:
            raise ValueError("Must be 0 or greater")
        save_gui_config()
    except ValueError as e:
        messagebox.showerror("Invalid Input", f"Chain exp runs must be a valid number (minimum 0): {e}")
        chain_exp_entry.delete(0, 'end')
        chain_exp_entry.insert(0, config['Settings'].get('chain_exp_runs', '2'))

chain_exp_entry.bind('<Return>', lambda e: update_chain_exp_runs())

# Mirror input
mirror_chain_frame = ctk.CTkFrame(chain_frame, fg_color="transparent")
mirror_chain_frame.pack(pady=2)
ctk.CTkLabel(mirror_chain_frame, text="Mirror Runs:", width=100, anchor="w", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 5))
chain_mirror_entry = ctk.CTkEntry(mirror_chain_frame, width=80, font=UIStyle.BODY_FONT)
chain_mirror_entry.pack(side="left", anchor="w", padx=(0, 10))
chain_mirror_entry.insert(0, config['Settings'].get('chain_mirror_runs', '1'))

def update_chain_mirror_runs():
    """Update chain mirror runs from entry field"""
    try:
        new_value = int(chain_mirror_entry.get())
        if new_value < 0:
            raise ValueError("Must be 0 or greater")
        save_gui_config()
    except ValueError as e:
        messagebox.showerror("Invalid Input", f"Chain mirror runs must be a valid number (minimum 0): {e}")
        chain_mirror_entry.delete(0, 'end')
        chain_mirror_entry.insert(0, config['Settings'].get('chain_mirror_runs', '1'))

chain_mirror_entry.bind('<Return>', lambda e: update_chain_mirror_runs())

# Collect rewards toggle
collect_rewards_frame = ctk.CTkFrame(chain_frame, fg_color="transparent")
collect_rewards_frame.pack(pady=2)
collect_rewards_var = ctk.BooleanVar(value=config['Settings'].get('collect_rewards_when_finished', False))
collect_rewards_checkbox = ctk.CTkCheckBox(collect_rewards_frame, text="Collect XP and mission rewards when finished", variable=collect_rewards_var, command=save_gui_config, font=UIStyle.BODY_FONT)
collect_rewards_checkbox.pack(side="left", padx=(10, 10))


# Chain control buttons
chain_control_frame = ctk.CTkFrame(chain_card, fg_color="transparent")
chain_control_frame.pack(pady=(0, 20))

chain_start_button = ctk.CTkButton(chain_control_frame, text="Start Chain", command=start_chain_automation, width=150, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
chain_start_button.pack(side="left", padx=5)

# Chain status
chain_status_label = ctk.CTkLabel(
    chain_card,
    text="Chain Status: Ready",
    font=UIStyle.SMALL_FONT,
    text_color=UIStyle.TEXT_SECONDARY_COLOR
)
chain_status_label.pack(pady=(0, 20))

# Function Call Card
function_card = CardFrame(others_scroll)
function_card.pack(fill="x", padx=10, pady=10)

# Function call section
ctk.CTkLabel(function_card, text="Call a function:", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))
function_entry = ctk.CTkEntry(function_card, width=300, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT)
function_entry.pack(pady=(0, 5))

# Help text for function call
function_help = ctk.CTkLabel(
    function_card, 
    text="Type any function from any module, e.g., core.battle or time.sleep(1)", 
    font=UIStyle.SMALL_FONT,
    text_color="gray"
)
function_help.pack(pady=(0, 10))

# Buttons for function control
function_call_button = ctk.CTkButton(function_card, text="Call", command=call_function, width=150, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
function_call_button.pack(pady=(0, 5))

function_terminate_button = ctk.CTkButton(
    function_card, 
    text="Terminate All", 
    command=kill_function_runner, 
    width=150,
    height=UIStyle.BUTTON_HEIGHT,
    font=UIStyle.BODY_FONT,
    state="disabled"  # Initially disabled until a function is called
)
function_terminate_button.pack(pady=(0, 20))

# =====================================================================
# LAZY-LOADED SETTINGS TAB
# =====================================================================

def _setup_profiles(parent):
    """Setup Profiles management section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Configuration Profiles", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    # Profile list
    profiles_frame = ctk.CTkScrollableFrame(card, height=150, fg_color="transparent")
    profiles_frame.pack(fill="x", padx=10, pady=(0, 10))
    
    # Selected profile var
    selected_profile = ctk.StringVar()
    
    def refresh_profiles():
        for widget in profiles_frame.winfo_children():
            widget.destroy()
            
        if not os.path.exists(PROFILES_DIR):
            os.makedirs(PROFILES_DIR)
            
        profiles = [d for d in os.listdir(PROFILES_DIR) if os.path.isdir(os.path.join(PROFILES_DIR, d))]
        
        if not profiles:
            ctk.CTkLabel(profiles_frame, text="No profiles found", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=10)
            return
            
        for prof in profiles:
            rb = ctk.CTkRadioButton(
                profiles_frame, 
                text=prof, 
                variable=selected_profile, 
                value=prof,
                font=UIStyle.BODY_FONT
            )
            rb.pack(anchor="w", pady=2, padx=5)
    
    refresh_profiles()
    
    # Actions area
    actions_frame = ctk.CTkFrame(card, fg_color="transparent")
    actions_frame.pack(fill="x", padx=10, pady=(0, 15))
    
    # New profile
    new_profile_entry = ctk.CTkEntry(actions_frame, placeholder_text="New Profile Name", height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT)
    new_profile_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    def save_profile():
        name = new_profile_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a profile name")
            return
            
        # Sanitize name
        name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not name:
            messagebox.showerror("Error", "Invalid profile name")
            return
            
        target_dir = os.path.join(PROFILES_DIR, name)
        os.makedirs(target_dir, exist_ok=True)
        
        # Save current config first to ensure disk is up to date
        save_gui_config()
        save_selected_statuses("mirror")
        save_selected_statuses("exp")
        save_selected_statuses("threads")
        
        # Copy files
        count = 0
        for filename in PROFILE_FILES:
            src = os.path.join(CONFIG_DIR, filename)
            dst = os.path.join(target_dir, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                count += 1
        
        messagebox.showinfo("Success", f"Profile '{name}' saved with {count} configuration files.")
        new_profile_entry.delete(0, 'end')
        refresh_profiles()
        
    def load_profile():
        name = selected_profile.get()
        if not name:
            messagebox.showerror("Error", "Please select a profile to load")
            return
            
        target_dir = os.path.join(PROFILES_DIR, name)
        if not os.path.exists(target_dir):
            messagebox.showerror("Error", "Profile directory not found")
            refresh_profiles()
            return
            
        if not messagebox.askyesno("Confirm Load", f"Load profile '{name}'?\nCurrent settings will be overwritten."):
            return
            
        # Copy files back
        count = 0
        for filename in PROFILE_FILES:
            src = os.path.join(target_dir, filename)
            dst = os.path.join(CONFIG_DIR, filename)
            if os.path.exists(src):
                shutil.copy2(src, dst)
                count += 1
        
        messagebox.showinfo("Success", f"Profile '{name}' loaded.\nPlease restart the application to apply all changes.")
        
    def delete_profile():
        name = selected_profile.get()
        if not name:
            return
            
        if not messagebox.askyesno("Confirm Delete", f"Delete profile '{name}'?"):
            return
            
        target_dir = os.path.join(PROFILES_DIR, name)
        try:
            shutil.rmtree(target_dir)
            refresh_profiles()
            selected_profile.set("")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to delete profile: {e}")

    ctk.CTkButton(actions_frame, text="Save", command=save_profile, width=80, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="left", padx=5)
    ctk.CTkButton(actions_frame, text="Load", command=load_profile, width=80, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="left", padx=5)
    ctk.CTkButton(actions_frame, text="Delete", command=delete_profile, width=80, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT, fg_color="#c42b1c", hover_color="#8f1f14").pack(side="left", padx=5)

    def open_config_folder():
        try:
            if platform.system() == "Windows":
                os.startfile(CONFIG_DIR)
            elif platform.system() == "Darwin":
                subprocess.run(["open", CONFIG_DIR])
            else:
                subprocess.run(["xdg-open", CONFIG_DIR])
        except Exception as e:
            error(f"Error opening folder: {e}")

    ctk.CTkButton(card, text="Open Config Folder", command=open_config_folder, height=30, fg_color="transparent", border_width=1, text_color=UIStyle.TEXT_SECONDARY_COLOR).pack(pady=(0, 15))

def _setup_danger_zone(parent):
    """Setup Reset Defaults section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Reset Defaults", font=UIStyle.SUBHEADER_FONT, text_color="#ff5555").pack(pady=(15, 10))
    
    def reset_to_defaults():
        if messagebox.askyesno("Reset Configuration", "Are you sure you want to reset all settings to default?\nThis will backup your current config folder and restart.\n\nProceed?"):
            try:
                # Rename config folder to backup
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                backup_path = f"{CONFIG_DIR}_backup_{timestamp}"
                
                if os.path.exists(CONFIG_DIR):
                    os.makedirs(backup_path, exist_ok=True)
                    for filename in os.listdir(CONFIG_DIR):
                        src = os.path.join(CONFIG_DIR, filename)
                        dst = os.path.join(backup_path, filename)
                        try:
                            shutil.move(src, dst)
                        except Exception as e:
                            error(f"Failed to move {filename}: {e}")
                
                # Restart application
                python = sys.executable
                os.execl(python, python, *sys.argv)
                
            except Exception as e:
                error(f"Error resetting config: {e}")
                messagebox.showerror("Error", f"Failed to reset: {e}")

    ctk.CTkButton(
        card, 
        text="Reset to Defaults", 
        command=reset_to_defaults, 
        fg_color="#c42b1c", 
        hover_color="#8f1f14",
        height=UIStyle.BUTTON_HEIGHT,
        font=UIStyle.BODY_FONT
    ).pack(pady=(0, 15))

def _setup_sinner_assignment(parent):
    """Setup Sinner Assignment section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Assign Sinners to Team", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(15, 10))

    container = ctk.CTkFrame(card, fg_color="transparent")
    container.pack(pady=(0, 15))

    load_json()

    for col_idx, group in enumerate(STATUS_COLUMNS):
        col = ctk.CTkFrame(container, fg_color="transparent")
        col.grid(row=0, column=col_idx, padx=15, sticky="n")

        for row_idx, status in enumerate(group):
            wrapper = ctk.CTkFrame(master=col, fg_color="transparent")
            wrapper.grid(row=row_idx, column=0, sticky="nw")

            arrow_var = ctk.StringVar(value="▶")

            def make_toggle(stat=status, arrow=arrow_var, button_ref=None):
                def toggle():
                    toggle_expand(expand_frames[stat], arrow, stat)
                    if button_ref:
                        button_ref.configure(text=f"{arrow.get()} {stat.capitalize()}")
                return toggle

            btn = ctk.CTkButton(
                master=wrapper,
                text=f"▶ {status.capitalize()}",
                command=None,
                width=200,
                height=UIStyle.BUTTON_HEIGHT,
                font=UIStyle.SUBHEADER_FONT,
                anchor="w"
            )
            btn.configure(command=make_toggle(status, arrow_var, btn))
            btn.pack(anchor="w", pady=(0, 6))

            frame = ctk.CTkFrame(master=wrapper, fg_color="transparent", corner_radius=0)
            expand_frames[status] = frame
            frame.pack_forget()

            # Initialize empty dropdown_vars for this status (will be populated on first expand)
            dropdown_vars[status] = []


def _setup_display_settings(parent):
    """Setup Display Settings section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Display Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    monitor_frame = ctk.CTkFrame(card, fg_color="transparent")
    monitor_frame.pack(pady=(0, 15))
    
    ctk.CTkLabel(monitor_frame, text="Game Monitor:", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
    try:
        available_monitors = get_available_monitors()
        monitor_options = [monitor['text'] for monitor in available_monitors]
        
        current_monitor = shared_vars.game_monitor.value
        if current_monitor <= len(monitor_options):
            default_monitor = monitor_options[current_monitor - 1]
        else:
            default_monitor = monitor_options[0] if monitor_options else "Monitor 1 (Unknown)"
            
    except Exception as e:
        error(f"Error getting monitor options: {e}")
        monitor_options = ["Monitor 1 (Unknown)"]
        default_monitor = monitor_options[0]
    
    monitor_var = ctk.StringVar(value=default_monitor)
    monitor_dropdown = ctk.CTkOptionMenu(
        monitor_frame,
        variable=monitor_var,
        values=monitor_options,
        width=200,
        height=UIStyle.ENTRY_HEIGHT,
        font=UIStyle.BODY_FONT,
        dropdown_font=UIStyle.BODY_FONT,
        command=lambda choice: update_monitor_selection(choice, shared_vars)
    )
    monitor_dropdown.pack(side="left", padx=(0, 10))

def _setup_mouse_offsets(parent):
    """Setup Mouse Offsets section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Mouse Offsets", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    mouse_offsets_frame = ctk.CTkFrame(card, fg_color="transparent")
    mouse_offsets_frame.pack(padx=20, pady=(0, 15))
    
    # X Offset
    x_offset_row = ctk.CTkFrame(mouse_offsets_frame)
    x_offset_row.pack(pady=5)
    ctk.CTkLabel(x_offset_row, text="X Offset:", width=100, anchor="e", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
    x_offset_entry = ctk.CTkEntry(x_offset_row, width=100, font=UIStyle.BODY_FONT, fg_color="transparent")
    x_offset_entry.pack(side="left", padx=(0, 10))
    x_offset_entry.insert(0, str(shared_vars.x_offset.value))
    
    # Y Offset
    y_offset_row = ctk.CTkFrame(mouse_offsets_frame)
    y_offset_row.pack(pady=5)
    ctk.CTkLabel(y_offset_row, text="Y Offset:", width=100, anchor="e", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
    y_offset_entry = ctk.CTkEntry(y_offset_row, width=100, font=UIStyle.BODY_FONT, fg_color="transparent")
    y_offset_entry.pack(side="left", padx=(0, 10))
    y_offset_entry.insert(0, str(shared_vars.y_offset.value))
    
    # Auto-save timers for offsets
    offset_timers = {}
    
    def auto_save_offset(offset_type, entry_widget, shared_var):
        """Auto-save offset after 1 second delay"""
        def save_it():
            try:
                new_value = int(entry_widget.get())
                shared_var.value = new_value
                save_gui_config()
            except ValueError:
                messagebox.showerror("Invalid Input", f"{offset_type} Offset must be a valid number.")
                entry_widget.delete(0, 'end')
                entry_widget.insert(0, str(shared_var.value))
        
        # Cancel existing timer for this offset
        if offset_type in offset_timers:
            root.after_cancel(offset_timers[offset_type])
        
        # Schedule save for 1 second from now
        offset_timers[offset_type] = root.after(1000, save_it)
    
    def setup_offset_auto_save(entry, offset_type, shared_var):
        """Setup auto-save for an offset entry"""
        def on_key_release(event):
            auto_save_offset(offset_type, entry, shared_var)
        entry.bind('<KeyRelease>', on_key_release)
    
    # Setup auto-save for offset entries
    setup_offset_auto_save(x_offset_entry, "X", shared_vars.x_offset)
    setup_offset_auto_save(y_offset_entry, "Y", shared_vars.y_offset)
    
    
    # Help text for offsets
    offset_help = ctk.CTkLabel(
        mouse_offsets_frame, 
        text="Adjust mouse click coordinates. Positive values move right/down, negative values move left/up.",
        font=UIStyle.SMALL_FONT, 
        text_color="gray"
    )
    offset_help.pack(pady=(5, 10))

def _setup_misc_settings(parent):
    """Setup Misc Settings section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Misc:", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    misc_frame = ctk.CTkFrame(card, fg_color="transparent")
    misc_frame.pack(pady=(0, 15))
    
    debug_image_var = ctk.BooleanVar(value=shared_vars.debug_image_matches.value)
    def update_debug_image_matches():
        shared_vars.debug_image_matches.value = debug_image_var.get()
        save_gui_config()
    debug_image_checkbox = ctk.CTkCheckBox(
        misc_frame, 
        text="Debug Image Matches", 
        variable=debug_image_var,
        command=update_debug_image_matches,
        font=UIStyle.BODY_FONT
    )
    debug_image_checkbox.pack(anchor="w", padx=10, pady=5)
    
    convert_images_to_grayscale_var = ctk.BooleanVar(value=shared_vars.convert_images_to_grayscale.value)
    def update_convert_images_to_grayscale():
        shared_vars.convert_images_to_grayscale.value = convert_images_to_grayscale_var.get()
        save_gui_config()
    convert_images_to_grayscale_checkbox = ctk.CTkCheckBox(
        misc_frame, 
        text="Convert images to grayscale (30%~ speed boost)", 
        variable=convert_images_to_grayscale_var,
        command=update_convert_images_to_grayscale,
        font=UIStyle.BODY_FONT
    )
    convert_images_to_grayscale_checkbox.pack(anchor="w", padx=10, pady=5)

    # Reconnection delay
    reconnection_delay_row = ctk.CTkFrame(misc_frame)
    reconnection_delay_row.pack(pady=5, fill="x")
    
    ctk.CTkLabel(reconnection_delay_row, text="Delay Between Reconnection Attempts:", width=200, anchor="w", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
    reconnection_delay_entry = ctk.CTkEntry(reconnection_delay_row, width=80, font=UIStyle.BODY_FONT)
    reconnection_delay_entry.pack(side="left", padx=(0, 10))
    reconnection_delay_entry.insert(0, str(shared_vars.reconnection_delay.value))
    
    # Auto-save for reconnection delay
    reconnection_timer = None
    
    def auto_save_reconnection_delay():
        """Auto-save reconnection delay after 1 second delay"""
        def save_it():
            try:
                new_value = int(reconnection_delay_entry.get())
                if new_value < 1:
                    raise ValueError("Must be at least 1 second")
                shared_vars.reconnection_delay.value = new_value
                save_gui_config()
            except ValueError as e:
                messagebox.showerror("Invalid Input", f"Reconnection delay must be a valid number (minimum 1): {e}")
                reconnection_delay_entry.delete(0, 'end')
                reconnection_delay_entry.insert(0, str(shared_vars.reconnection_delay.value))
        
        nonlocal reconnection_timer
        # Cancel existing timer
        if reconnection_timer:
            root.after_cancel(reconnection_timer)
        
        # Schedule save for 1 second from now
        reconnection_timer = root.after(1000, save_it)
    
    def on_reconnection_key_release(event):
        auto_save_reconnection_delay()
    
    reconnection_delay_entry.bind('<KeyRelease>', on_reconnection_key_release)

    # Reconnect only when internet is reachable toggle
    reconnect_internet_var = ctk.BooleanVar(value=shared_vars.reconnect_when_internet_reachable.value)
    def update_reconnect_internet():
        shared_vars.reconnect_when_internet_reachable.value = reconnect_internet_var.get()
        save_gui_config()
    reconnect_internet_checkbox = ctk.CTkCheckBox(
        misc_frame, 
        text="Reconnect only When Internet Is Reachable", 
        variable=reconnect_internet_var,
        command=update_reconnect_internet,
        font=UIStyle.BODY_FONT
    )
    reconnect_internet_checkbox.pack(anchor="w", padx=10, pady=5)

    # Auto Update toggle
    def update_auto_update():
        save_gui_config()
        
    auto_update_checkbox = ctk.CTkCheckBox(
        misc_frame, 
        text="Auto Update on Startup", 
        variable=auto_update_var,
        command=update_auto_update,
        font=UIStyle.BODY_FONT
    )
    auto_update_checkbox.pack(anchor="w", padx=10, pady=5)

    # Click delay setting
    click_delay_row = ctk.CTkFrame(misc_frame)
    click_delay_row.pack(pady=5, fill="x")
    
    ctk.CTkLabel(click_delay_row, text="Delay Between Operations:", width=200, anchor="w", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
    click_delay_entry = ctk.CTkEntry(click_delay_row, width=80, font=UIStyle.BODY_FONT)
    click_delay_entry.pack(side="left", padx=(0, 10))
    click_delay_entry.insert(0, str(shared_vars.click_delay.value))
    
    # Auto-save for click delay
    click_delay_timer = None
    
    def auto_save_click_delay():
        """Auto-save click delay after 1 second delay"""
        def save_it():
            try:
                new_value = float(click_delay_entry.get())
                if new_value < 0:
                    raise ValueError("Must be 0 or greater")
                shared_vars.click_delay.value = new_value
                save_gui_config()
            except ValueError as e:
                messagebox.showerror("Invalid Input", f"Click delay must be a valid number (0 or greater): {e}")
                click_delay_entry.delete(0, 'end')
                click_delay_entry.insert(0, str(shared_vars.click_delay.value))
        
        nonlocal click_delay_timer
        # Cancel existing timer
        if click_delay_timer:
            root.after_cancel(click_delay_timer)
        
        # Schedule save for 1 second from now
        click_delay_timer = root.after(1000, save_it)
    
    def on_click_delay_key_release(event):
        auto_save_click_delay()
    
    click_delay_entry.bind('<KeyRelease>', on_click_delay_key_release)

    # Image Threshold Configuration
    threshold_config_frame = ctk.CTkFrame(card, fg_color="transparent")
    threshold_config_frame.pack(pady=(8, 15), fill="x")
    
    ctk.CTkLabel(threshold_config_frame, text="Image Threshold Configuration:", font=UIStyle.SUBHEADER_FONT).pack(pady=(5, 0))
    
    # Global threshold adjustment
    global_threshold_row = ctk.CTkFrame(threshold_config_frame)
    global_threshold_row.pack(pady=5, fill="x", padx=10)
    
    ctk.CTkLabel(global_threshold_row, text="Global Threshold Adjustment:", width=200, anchor="w", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
    global_threshold_entry = ctk.CTkEntry(global_threshold_row, width=80, font=UIStyle.BODY_FONT)
    global_threshold_entry.pack(side="left", padx=(0, 10))
    
    # Toggle for applying global to modified
    apply_global_var = ctk.BooleanVar()
    apply_global_toggle = ctk.CTkSwitch(global_threshold_row, text="Don't apply to modified thresholds", variable=apply_global_var, font=UIStyle.BODY_FONT)
    apply_global_toggle.pack(side="left", padx=(10, 0))
    
    # Load initial values
    try:
        import src.shared_vars as sv
        threshold_config = sv.image_threshold_config
        global_threshold_entry.insert(0, str(threshold_config.get("global_adjustment", 0.0)))
        apply_global_var.set(not threshold_config.get("apply_global_to_modified", True))
    except:
        global_threshold_entry.insert(0, "0.0")
        apply_global_var.set(False)
    
    # Create collapsible tree for image-specific adjustments
    image_threshold_tree_frame = ctk.CTkFrame(threshold_config_frame)
    image_threshold_tree_frame.pack(pady=5, fill="both", expand=True, padx=10)
    
    ctk.CTkLabel(image_threshold_tree_frame, text="Image-Specific Adjustments:", font=UIStyle.BODY_FONT).pack(pady=(5, 0))
    
    # Collapsible tree structure like other parts of the GUI
    tree_frame = ctk.CTkFrame(image_threshold_tree_frame)
    tree_frame.pack(pady=5, fill="both", expand=True, padx=10)
    
    # Dictionary to store image threshold entries
    image_threshold_entries = {}
    
    def folder_has_images_recursive(folder_path):
        """Check if a folder contains image files (recursively, including subfolders)"""
        full_path = os.path.join(BASE_PATH, folder_path)
        if not os.path.exists(full_path):
            return False
        
        try:
            for root, dirs, files in os.walk(full_path):
                if any(f.lower().endswith(('.png', '.jpg', '.jpeg')) for f in files):
                    return True
            return False
        except:
            return False
    
    def folder_has_direct_images(folder_path):
        """Check if a folder contains image files (directly, not in subfolders)"""
        full_path = os.path.join(BASE_PATH, folder_path)
        if not os.path.exists(full_path):
            return False
        
        try:
            files = os.listdir(full_path)
            return any(f.lower().endswith(('.png', '.jpg', '.jpeg')) for f in files if os.path.isfile(os.path.join(full_path, f)))
        except:
            return False
    
    def create_collapsible_folder(parent, folder_name, folder_path, level=0):
        """Create a collapsible folder section like other GUI sections"""
        # Main container for this folder
        folder_container = ctk.CTkFrame(parent)
        folder_container.pack(fill="x", pady=2, padx=level*20)
        
        # Header with expand/collapse button
        header_frame = ctk.CTkFrame(folder_container)
        header_frame.pack(fill="x", pady=2)
        
        # Expand/collapse state
        is_expanded = ctk.BooleanVar(value=False)
        
        # Content frame (hidden by default)
        content_frame = ctk.CTkFrame(folder_container)
        
        def toggle_folder():
            if is_expanded.get():
                content_frame.pack_forget()
                expand_btn.configure(text="▶")
                is_expanded.set(False)
            else:
                content_frame.pack(fill="x", pady=2)
                expand_btn.configure(text="▼")
                is_expanded.set(True)
                # Load content if not already loaded
                if len(content_frame.winfo_children()) == 0:
                    load_folder_content(content_frame, folder_path, level + 1)
        
        # Expand button
        expand_btn = ctk.CTkButton(header_frame, text="▶", width=30, height=25, command=toggle_folder)
        expand_btn.pack(side="left", padx=5)
        
        # Folder name label
        folder_label = ctk.CTkLabel(header_frame, text=f"📁 {folder_name}", font=UIStyle.SMALL_FONT, cursor="hand2")
        folder_label.pack(side="left", padx=5)
        
        # Double-click to open folder
        def open_folder(event):
            try:
                full_path = os.path.join(BASE_PATH, folder_path)
                if platform.system() == "Windows":
                    os.startfile(full_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", full_path])
                else:  # Linux and others
                    subprocess.run(["xdg-open", full_path])
            except Exception as e:
                print(f"Failed to open folder: {e}")
        
        folder_label.bind("<Double-Button-1>", open_folder)
        
        # Only show folder threshold entry if folder contains direct images (not just in subfolders)
        if folder_has_direct_images(folder_path):
            # Folder threshold entry
            folder_threshold_entry = ctk.CTkEntry(header_frame, width=80, placeholder_text="0.0", font=(UIStyle.FONT_FAMILY, 10))
            folder_threshold_entry.pack(side="left", padx=5)
            
            # Load existing folder threshold
            try:
                import src.shared_vars as sv
                folder_adjustments = sv.image_threshold_config.get("folder_adjustments", {})
                current_value = folder_adjustments.get(folder_path, 0.0)
                if current_value != 0.0:
                    folder_threshold_entry.delete(0, 'end')
                    folder_threshold_entry.insert(0, str(current_value))
            except:
                pass
            
            # Auto-save folder threshold on change
            def save_folder_threshold(*args):
                try:
                    import src.shared_vars as sv
                    import json
                    
                    value = float(folder_threshold_entry.get()) if folder_threshold_entry.get() else 0.0
                    
                    # Get current config and preserve existing adjustments
                    config = {
                        "global_adjustment": sv.image_threshold_config.get("global_adjustment", 0.0),
                        "apply_global_to_modified": sv.image_threshold_config.get("apply_global_to_modified", True),
                        "folder_adjustments": sv.image_threshold_config.get("folder_adjustments", {}),
                        "image_adjustments": sv.image_threshold_config.get("image_adjustments", {})
                    }
                    
                    # Update folder adjustment
                    if value != 0.0:
                        config["folder_adjustments"][folder_path] = value
                    elif folder_path in config["folder_adjustments"]:
                        del config["folder_adjustments"][folder_path]
                    
                    # Save to file
                    config_path = os.path.join(BASE_PATH, "config", "image_thresholds.json")
                    with open(config_path, 'w') as f:
                        json.dump(config, f, indent=2)
                    
                    # Reload in shared_vars
                    sv.ConfigCache.reload_config("image_thresholds")
                    sv.image_threshold_config = sv.ConfigCache.get_config("image_thresholds")
                    
                except ValueError:
                    pass  # Invalid number, ignore
                except Exception as e:
                    pass  # Ignore other errors for now
            
            folder_threshold_entry.bind('<FocusOut>', save_folder_threshold)
            folder_threshold_entry.bind('<Return>', save_folder_threshold)
        
        return folder_container, content_frame
    
    def create_image_entry(parent, image_name, image_path, level=0):
        """Create an image threshold entry"""
        image_frame = ctk.CTkFrame(parent)
        image_frame.pack(fill="x", pady=2, padx=level*20)
        
        # Simple icon display
        image_label = ctk.CTkLabel(image_frame, text=f"🖼️ {image_name}", font=(UIStyle.FONT_FAMILY, 11), cursor="hand2")
        image_label.pack(side="left", padx=10)
        
        # Double-click to open image
        def open_image(event):
            try:
                full_path = os.path.join(BASE_PATH, image_path)
                if platform.system() == "Windows":
                    os.startfile(full_path)
                elif platform.system() == "Darwin":  # macOS
                    subprocess.run(["open", full_path])
                else:  # Linux and others
                    subprocess.run(["xdg-open", full_path])
            except Exception as e:
                print(f"Failed to open image: {e}")
        
        image_label.bind("<Double-Button-1>", open_image)
        
        # Threshold entry
        threshold_entry = ctk.CTkEntry(image_frame, width=80, placeholder_text="0.0")
        threshold_entry.pack(side="right", padx=10)
        
        # Load existing value
        try:
            import src.shared_vars as sv
            existing_value = sv.image_threshold_config.get("image_adjustments", {}).get(image_path, 0.0)
            threshold_entry.insert(0, str(existing_value))
        except:
            threshold_entry.insert(0, "0.0")
        
        # Store reference for saving
        image_threshold_entries[image_path] = threshold_entry
        
        # Auto-save on change
        def save_threshold(*args):
            try:
                value = float(threshold_entry.get())
                # Update config and save
                import src.shared_vars as sv
                import json
                
                config = {
                    "global_adjustment": float(global_threshold_entry.get()),
                    "apply_global_to_modified": not apply_global_var.get(),
                    "folder_adjustments": sv.image_threshold_config.get("folder_adjustments", {}),
                    "image_adjustments": sv.image_threshold_config.get("image_adjustments", {})
                }
                
                if value != 0.0:
                    config["image_adjustments"][image_path] = value
                elif image_path in config["image_adjustments"]:
                    del config["image_adjustments"][image_path]
                
                # Save to file
                config_path = os.path.join(BASE_PATH, "config", "image_thresholds.json")
                with open(config_path, 'w') as f:
                    json.dump(config, f, indent=2)
                
                # Reload in shared_vars
                sv.ConfigCache.reload_config("image_thresholds")
                sv.image_threshold_config = sv.ConfigCache.get_config("image_thresholds")
                
            except ValueError:
                pass  # Invalid number, ignore
        
        threshold_entry.bind('<FocusOut>', save_threshold)
        threshold_entry.bind('<Return>', save_threshold)
    
    def load_folder_content(parent, folder_path, level):
        """Load folder contents - subfolders and images"""
        full_path = os.path.join(BASE_PATH, folder_path)
        if not os.path.exists(full_path):
            return
        
        try:
            items = os.listdir(full_path)
            folders = []
            images = []
            
            for item in items:
                item_path = os.path.join(full_path, item)
                if os.path.isdir(item_path):
                    # Use the recursive function to decide which folders to show
                    subfolder_path = f"{folder_path}/{item}" if folder_path != "pictures" else f"pictures/{item}"
                    if folder_has_images_recursive(subfolder_path):
                        folders.append(item)
                elif item.lower().endswith(('.png', '.jpg', '.jpeg')):
                    images.append(item)
            
            # Create subfolders first
            for folder in sorted(folders):
                subfolder_path = f"{folder_path}/{folder}" if folder_path != "pictures" else f"pictures/{folder}"
                create_collapsible_folder(parent, folder, subfolder_path, level)
            
            # Create image entries
            for image in sorted(images):
                image_path = f"{folder_path}/{image}"
                create_image_entry(parent, image, image_path, level)
                
        except Exception as e:
            error_label = ctk.CTkLabel(parent, text=f"Error loading {folder_path}: {e}", text_color="red")
            error_label.pack(pady=5)
    
    # Initialize with pictures folder
    if os.path.exists(os.path.join(BASE_PATH, "pictures")):
        create_collapsible_folder(tree_frame, "pictures", "pictures")
    
    
    
    # Load existing global settings
    def load_global_settings():
        try:
            import src.shared_vars as sv
            threshold_config = sv.image_threshold_config
            global_threshold_entry.delete(0, 'end')
            global_threshold_entry.insert(0, str(threshold_config.get("global_adjustment", 0.0)))
            apply_global_var.set(not threshold_config.get("apply_global_to_modified", True))
        except:
            pass
    
    load_global_settings()
    
    def save_global_threshold_settings():
        """Save only global threshold settings"""
        try:
            import src.shared_vars as sv
            import json
            
            # Preserve existing adjustments
            config = {
                "global_adjustment": float(global_threshold_entry.get()),
                "apply_global_to_modified": not apply_global_var.get(),
                "folder_adjustments": sv.image_threshold_config.get("folder_adjustments", {}),
                "image_adjustments": sv.image_threshold_config.get("image_adjustments", {})
            }
            
            # Save to file
            config_path = os.path.join(BASE_PATH, "config", "image_thresholds.json")
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Reload in shared_vars
            sv.ConfigCache.reload_config("image_thresholds")
            sv.image_threshold_config = sv.ConfigCache.get_config("image_thresholds")
            
        except Exception as e:
            error(f"Failed to save global threshold settings: {e}")
    
    # Auto-save for global settings
    def on_global_change(*args):
        save_global_threshold_settings()
    
    global_threshold_entry.bind('<KeyRelease>', on_global_change)
    global_threshold_entry.bind('<FocusOut>', on_global_change)
    apply_global_var.trace("w", on_global_change)

def _setup_automation_settings(parent):
    """Setup Automation Settings section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Automation Settings:", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    automation_frame = ctk.CTkFrame(card, fg_color="transparent")
    automation_frame.pack(pady=(0, 15))


    skip_ego_check_var = ctk.BooleanVar(value=shared_vars.skip_ego_check.value)
    def update_skip_ego_check():
        shared_vars.skip_ego_check.value = skip_ego_check_var.get()
        save_gui_config()
    skip_ego_check_cb = ctk.CTkCheckBox(
        automation_frame, 
        text="Skip using EGO in Battle", 
        variable=skip_ego_check_var,
        command=update_skip_ego_check,
        font=UIStyle.BODY_FONT
    )
    skip_ego_check_cb.pack(anchor="w", padx=10, pady=5)


    good_pc_mode_var = ctk.BooleanVar(value=shared_vars.good_pc_mode.value)
    def update_good_pc_mode():
        shared_vars.good_pc_mode.value = good_pc_mode_var.get()
        save_gui_config()
    good_pc_mode_cb = ctk.CTkCheckBox(
        automation_frame, 
        text="I have a good pc", 
        variable=good_pc_mode_var,
        command=update_good_pc_mode,
        font=UIStyle.BODY_FONT
    )
    good_pc_mode_cb.pack(anchor="w", padx=10, pady=5)

def _setup_shortcuts(parent):
    """Setup Keyboard Shortcuts section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Keyboard Shortcuts", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    shortcuts_frame = ctk.CTkFrame(card, fg_color="transparent")
    shortcuts_frame.pack(pady=(0, 15))

    # Auto-save timers for shortcuts
    shortcut_timers = {}
    shortcut_entries = {}
    
    def auto_save_shortcut(shortcut_type):
        """Auto-save shortcut after 1 second delay"""
        def save_it():
            try:
                # Get text from the entry widget and update the StringVar
                shortcut_text = shortcut_entries[shortcut_type].get()
                if not shortcut_text or shortcut_text.strip() == "":
                    return
                
                # Update the StringVar to keep it in sync
                shortcut_vars[shortcut_type].set(shortcut_text)
                
                # Save configuration
                save_gui_config()
                # Re-register all shortcuts (with throttling)
                register_keyboard_shortcuts()
                
            except Exception as e:
                error(f"Invalid shortcut format: {e}")
                # Reset to previous value
                old_value = config['Shortcuts'].get(shortcut_type)
                shortcut_vars[shortcut_type].set(old_value)
                shortcut_entries[shortcut_type].delete(0, 'end')
                shortcut_entries[shortcut_type].insert(0, old_value)
                messagebox.showerror("Invalid Shortcut", f"Invalid shortcut format: {shortcut_text}\n\nValid examples: ctrl+q, alt+s, shift+x")
        
        # Cancel existing timer for this shortcut
        if shortcut_type in shortcut_timers:
            root.after_cancel(shortcut_timers[shortcut_type])
        
        # Schedule save for 1 second from now
        shortcut_timers[shortcut_type] = root.after(1000, save_it)
    
    def setup_auto_save(entry, shortcut_type):
        """Setup auto-save for a shortcut entry"""
        shortcut_entries[shortcut_type] = entry
        def on_key_release(event):
            auto_save_shortcut(shortcut_type)
        entry.bind('<KeyRelease>', on_key_release)

    # Helper for shortcut rows
    def create_shortcut_row(label_text, shortcut_key):
        row = ctk.CTkFrame(shortcuts_frame)
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=label_text, width=120, anchor="e", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
        entry = ctk.CTkEntry(row, width=100, font=UIStyle.BODY_FONT)
        entry.pack(side="left", padx=(0, 10))
        entry.insert(0, shortcut_vars[shortcut_key].get())
        setup_auto_save(entry, shortcut_key)

    create_shortcut_row("Mirror Dungeon:", 'mirror_dungeon')
    create_shortcut_row("Exp:", 'exp')
    create_shortcut_row("Threads:", 'threads')
    create_shortcut_row("Start Battle:", 'battle')
    create_shortcut_row("Chain Automation:", 'chain_automation')
    create_shortcut_row("Call Function:", 'call_function')
    create_shortcut_row("Terminate Functions:", 'terminate_functions')

    # Help text for keyboard shortcuts
    shortcut_help = ctk.CTkLabel(shortcuts_frame, text="Format examples: ctrl+q, alt+s, shift+x", 
                                font=UIStyle.SMALL_FONT, text_color="gray")
    shortcut_help.pack(pady=(5, 10))

def _setup_theme(parent):
    """Setup Theme section"""
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Theme", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    # Refresh themes to pick up any new theme files
    global THEMES
    THEMES = load_available_themes()
    
    theme_dropdown = ctk.CTkOptionMenu(
        master=card,
        variable=theme_var,
        values=list(THEMES.keys()),
        width=200,
        height=UIStyle.ENTRY_HEIGHT,
        font=UIStyle.BODY_FONT,
        dropdown_font=UIStyle.BODY_FONT,
        command=lambda _: apply_theme()
    )
    theme_dropdown.pack(pady=(0, 15))

def load_settings_tab():
    """Lazy load the Settings tab content"""
    global settings_tab_loaded
    if settings_tab_loaded:
        return
    
    # Setting up the Settings tab
    settings_scroll = ctk.CTkScrollableFrame(master=tab_settings, corner_radius=UIStyle.CORNER_RADIUS)
    settings_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

    _setup_profiles(settings_scroll)
    _setup_sinner_assignment(settings_scroll)
    _setup_display_settings(settings_scroll)
    _setup_mouse_offsets(settings_scroll)
    _setup_misc_settings(settings_scroll)
    _setup_automation_settings(settings_scroll)
    _setup_shortcuts(settings_scroll)
    _setup_theme(settings_scroll)
    _setup_danger_zone(settings_scroll)

    settings_tab_loaded = True

# =====================================================================
# STATISTICS TAB
# =====================================================================

stats_scroll = ctk.CTkScrollableFrame(master=tab_stats, corner_radius=UIStyle.CORNER_RADIUS)
stats_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

def load_stats():
    try:
        if os.path.exists(STATS_PATH):
            with open(STATS_PATH, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return {"mirror": {"runs": 0, "wins": 0, "losses": 0}, "exp": {"runs": 0}, "threads": {"runs": 0}}

def refresh_statistics():
    for widget in stats_scroll.winfo_children():
        widget.destroy()
        
    stats = load_stats()
    
    # Mirror Dungeon Stats
    md_card = CardFrame(stats_scroll)
    md_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(md_card, text="Mirror Dungeon", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    md_grid = ctk.CTkFrame(md_card, fg_color="transparent")
    md_grid.pack(pady=(0, 15), padx=20, fill="x")
    
    md_runs = stats.get("mirror", {}).get("runs", 0)
    md_wins = stats.get("mirror", {}).get("wins", 0)
    md_losses = stats.get("mirror", {}).get("losses", 0)
    win_rate = (md_wins / md_runs * 100) if md_runs > 0 else 0
    
    ctk.CTkLabel(md_grid, text=f"Total Runs: {md_runs}", font=UIStyle.BODY_FONT).pack(side="left", expand=True)
    ctk.CTkLabel(md_grid, text=f"Wins: {md_wins}", font=UIStyle.BODY_FONT, text_color="#4caf50").pack(side="left", expand=True)
    ctk.CTkLabel(md_grid, text=f"Losses: {md_losses}", font=UIStyle.BODY_FONT, text_color="#f44336").pack(side="left", expand=True)
    ctk.CTkLabel(md_grid, text=f"Win Rate: {win_rate:.1f}%", font=UIStyle.BODY_FONT).pack(side="left", expand=True)
    
    # Other Stats
    other_card = CardFrame(stats_scroll)
    other_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(other_card, text="Luxcavations", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    other_grid = ctk.CTkFrame(other_card, fg_color="transparent")
    other_grid.pack(pady=(0, 15), padx=20, fill="x")
    
    exp_runs = stats.get("exp", {}).get("runs", 0)
    threads_runs = stats.get("threads", {}).get("runs", 0)
    
    ctk.CTkLabel(other_grid, text=f"Exp Runs: {exp_runs}", font=UIStyle.BODY_FONT).pack(side="left", expand=True)
    ctk.CTkLabel(other_grid, text=f"Thread Runs: {threads_runs}", font=UIStyle.BODY_FONT).pack(side="left", expand=True)
    
    ctk.CTkButton(stats_scroll, text="Refresh Stats", command=refresh_statistics, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(pady=20)

# Initial load
refresh_statistics()

# =====================================================================
# SCHEDULE TAB
# =====================================================================

schedule_scroll = ctk.CTkScrollableFrame(master=tab_schedule, corner_radius=UIStyle.CORNER_RADIUS)
schedule_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

def load_schedule():
    try:
        if os.path.exists(SCHEDULE_PATH):
            with open(SCHEDULE_PATH, 'r') as f:
                return json.load(f)
    except Exception:
        pass
    return []

def save_schedule(data):
    try:
        with open(SCHEDULE_PATH, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        error(f"Error saving schedule: {e}")

def refresh_schedule_ui():
    for widget in schedule_list_frame.winfo_children():
        widget.destroy()
        
    schedules = load_schedule()
    
    if not schedules:
        ctk.CTkLabel(schedule_list_frame, text="No scheduled tasks", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=10)
        return
        
    for idx, task in enumerate(schedules):
        row = ctk.CTkFrame(schedule_list_frame, fg_color="transparent")
        row.pack(fill="x", pady=5)
        
        info_text = f"{task['time']} - {task['type']} ({task.get('runs', 1)} runs)"
        ctk.CTkLabel(row, text=info_text, font=UIStyle.BODY_FONT).pack(side="left", padx=10)
        
        def delete_task(i=idx):
            schedules.pop(i)
            save_schedule(schedules)
            refresh_schedule_ui()
            
        ctk.CTkButton(row, text="Delete", command=delete_task, width=60, height=24, fg_color="#c42b1c", hover_color="#8f1f14", font=UIStyle.SMALL_FONT).pack(side="right", padx=10)

# Add Task Card
add_task_card = CardFrame(schedule_scroll)
add_task_card.pack(fill="x", padx=10, pady=10)
ctk.CTkLabel(add_task_card, text="Add Scheduled Task", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

input_frame = ctk.CTkFrame(add_task_card, fg_color="transparent")
input_frame.pack(pady=(0, 15), padx=20)

# Time Input
ctk.CTkLabel(input_frame, text="Time (HH:MM):", font=UIStyle.BODY_FONT).grid(row=0, column=0, padx=5, pady=5)
sched_time_entry = ctk.CTkEntry(input_frame, width=100, font=UIStyle.BODY_FONT)
sched_time_entry.grid(row=0, column=1, padx=5, pady=5)
sched_time_entry.insert(0, "12:00")

# Type Input
ctk.CTkLabel(input_frame, text="Action:", font=UIStyle.BODY_FONT).grid(row=0, column=2, padx=5, pady=5)
sched_type_var = ctk.StringVar(value="Mirror Dungeon")
sched_type_dropdown = ctk.CTkOptionMenu(
    input_frame, 
    variable=sched_type_var, 
    values=["Mirror Dungeon", "Exp", "Threads", "Chain Automation"],
    font=UIStyle.BODY_FONT
)
sched_type_dropdown.grid(row=0, column=3, padx=5, pady=5)

# Runs Input
ctk.CTkLabel(input_frame, text="Runs:", font=UIStyle.BODY_FONT).grid(row=0, column=4, padx=5, pady=5)
sched_runs_entry = ctk.CTkEntry(input_frame, width=60, font=UIStyle.BODY_FONT)
sched_runs_entry.grid(row=0, column=5, padx=5, pady=5)
sched_runs_entry.insert(0, "1")

def add_schedule_task():
    time_str = sched_time_entry.get().strip()
    try:
        # Validate time format
        datetime.strptime(time_str, "%H:%M")
        runs = int(sched_runs_entry.get())
        if runs < 1: raise ValueError
    except ValueError:
        messagebox.showerror("Invalid Input", "Invalid time (HH:MM) or runs")
        return
        
    task = {
        "time": time_str,
        "type": sched_type_var.get(),
        "runs": runs,
        "enabled": True
    }
    
    schedules = load_schedule()
    schedules.append(task)
    save_schedule(schedules)
    refresh_schedule_ui()
    messagebox.showinfo("Success", "Task scheduled")

ctk.CTkButton(add_task_card, text="Add Task", command=add_schedule_task, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(pady=(0, 15))

# Schedule List Card
list_card = CardFrame(schedule_scroll)
list_card.pack(fill="x", padx=10, pady=10)
ctk.CTkLabel(list_card, text="Scheduled Tasks", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

schedule_list_frame = ctk.CTkFrame(list_card, fg_color="transparent")
schedule_list_frame.pack(fill="x", padx=10, pady=(0, 15))

refresh_schedule_ui()

# Scheduler Logic
last_executed_minute = None

def check_scheduler():
    global last_executed_minute
    current_time = datetime.now().strftime("%H:%M")
    
    # Only check once per minute
    if current_time == last_executed_minute:
        root.after(5000, check_scheduler)
        return
        
    schedules = load_schedule()
    for task in schedules:
        if task.get("enabled") and task["time"] == current_time:
            if not is_any_process_running():
                info(f"Executing scheduled task: {task['type']}")
                last_executed_minute = current_time
                
                # Set runs in entry fields to respect task config
                if task["type"] == "Mirror Dungeon":
                    entry.delete(0, 'end'); entry.insert(0, str(task["runs"]))
                    start_run()
                elif task["type"] == "Exp":
                    exp_entry.delete(0, 'end'); exp_entry.insert(0, str(task["runs"]))
                    start_exp_run()
                elif task["type"] == "Threads":
                    threads_entry.delete(0, 'end'); threads_entry.insert(0, str(task["runs"]))
                    start_threads_run()
                elif task["type"] == "Chain Automation":
                    start_chain_automation()
            else:
                warning(f"Skipped scheduled task {task['type']} because a process is running")
    
    root.after(5000, check_scheduler)

# =====================================================================
# RESPONSIVE LOGS TAB
# =====================================================================

def load_logs_tab():
    """Lazy load the Logs tab content with responsive design"""
    global logs_tab_loaded, log_handler
    if logs_tab_loaded:
        return

    # Filter Card
    filter_card = CardFrame(tab_logs)
    filter_card.pack(fill="x", padx=10, pady=(10, 5))

    # Filter header
    filter_header = ctk.CTkFrame(filter_card, fg_color="transparent")
    filter_header.pack(fill="x", pady=(10, 5), padx=10)
    
    ctk.CTkLabel(filter_header, text="Log Filters", 
                font=UIStyle.SUBHEADER_FONT).pack(side="left")

    # ONE frame for both toggles - using grid for precise control
    toggles = ctk.CTkFrame(filter_header, fg_color="transparent")
    toggles.pack(side="right", padx=10)
    
    # Grid layout - everything in one row, close together
    ctk.CTkLabel(toggles, text="Clean Logs", font=UIStyle.SMALL_FONT).grid(row=0, column=0, padx=(0,2), sticky="e")
    filter_toggle = ctk.CTkSwitch(toggles, text="", variable=ctk.BooleanVar(value=filtered_messages_enabled), command=lambda: toggle_filtered_messages(), onvalue=True, offvalue=False, font=UIStyle.SMALL_FONT)
    filter_toggle.grid(row=0, column=1, padx=(0,10))
    
    ctk.CTkLabel(toggles, text="Do Not Log", font=UIStyle.SMALL_FONT).grid(row=0, column=2, padx=(0,2), sticky="e") 
    logging_toggle = ctk.CTkSwitch(toggles, text="", variable=ctk.BooleanVar(value=not logging_enabled), command=lambda: toggle_logging(), onvalue=True, offvalue=False, font=UIStyle.SMALL_FONT)
    logging_toggle.grid(row=0, column=3, padx=0)

    def toggle_filtered_messages():
        """Toggle filtering of noisy messages"""
        global filtered_messages_enabled
        filtered_messages_enabled = filter_toggle.get()
        common.CLEAN_LOGS_ENABLED = filtered_messages_enabled
        save_gui_config()
        load_log_file(reload_all=True)  # Reload logs with new filter setting
    
    def toggle_logging():
        """Toggle all logging on/off"""
        global logging_enabled
        logging_enabled = not logging_toggle.get()  # Inverted because "Do Not Log" means disable
        
        # Update the async logger
        try:
            if hasattr(common, 'set_logging_enabled'):
                common.set_logging_enabled(logging_enabled)
        except (AttributeError, NameError):
            # Fallback if async logging not available
            pass
        
        save_gui_config()
        
        # Update log display to show current status
        if logging_enabled:
            log_text.insert("end", f"\n[{get_timestamp()}] LOGGING ENABLED\n")
        else:
            log_text.insert("end", f"\n[{get_timestamp()}] LOGGING DISABLED - No new logs will be generated\n")
        log_text.see("end")

    filters_main_frame = ctk.CTkFrame(filter_card, fg_color="transparent")
    filters_main_frame.pack(fill="x", expand=True, padx=10, pady=(0, 10))

    # Level filters section
    levels_frame = ctk.CTkFrame(filters_main_frame, fg_color="transparent")
    levels_frame.pack(side="left", fill="y", padx=(5, 2))
    
    ctk.CTkLabel(levels_frame, text="Log Levels:", 
                font=UIStyle.SMALL_FONT).pack(pady=(5, 0))

    def apply_filter():
        """Re-load log file with current filters and save filter settings"""
        load_log_file(reload_all=True)
        save_gui_config()

    # Create level checkboxes in a compact layout
    level_grid_frame = ctk.CTkFrame(levels_frame, fg_color="transparent")
    level_grid_frame.pack(fill="x", padx=5, pady=5)

    for i, level in enumerate(log_filters):
        chk = ctk.CTkCheckBox(
            master=level_grid_frame,
            text=level,
            variable=log_filters[level],
            command=apply_filter,
            font=(UIStyle.FONT_FAMILY, 10)
        )
        # Arrange in 2 columns for compactness
        row = i % 3
        col = i // 3
        chk.grid(row=row, column=col, sticky="w", padx=2, pady=1)

    modules_frame = ctk.CTkFrame(filters_main_frame, fg_color="transparent")
    modules_frame.pack(side="left", fill="both", expand=True, padx=(2, 5))
    
    ctk.CTkLabel(modules_frame, text="Modules:", 
                font=UIStyle.SMALL_FONT).pack(pady=(5, 0))

    module_scroll_frame = ctk.CTkScrollableFrame(modules_frame, height=60)
    module_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # Calculate optimal columns based on number of modules
    modules_per_column = max(3, len(LOG_MODULES) // 4)  # At least 3, but try to fit in 4 columns

    for i, module in enumerate(LOG_MODULES):
        col = i // modules_per_column
        row = i % modules_per_column
        
        chk = ctk.CTkCheckBox(
            master=module_scroll_frame,
            text=module,
            variable=module_filters[module],
            command=apply_filter,
            font=(UIStyle.FONT_FAMILY, 10)
        )
        chk.grid(row=row, column=col, sticky="w", padx=2, pady=1)

    # Configure grid weights for responsiveness
    for i in range((len(LOG_MODULES) // modules_per_column) + 1):
        module_scroll_frame.grid_columnconfigure(i, weight=1)

    # Log Display Card
    log_card = CardFrame(tab_logs)
    log_card.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    # Log display area
    log_text = ctk.CTkTextbox(log_card, font=(UIStyle.FONT_FAMILY, 11), fg_color=UIStyle.MAIN_BG_COLOR)
    log_text.pack(fill="both", expand=True, padx=10, pady=(10, 5))
    log_text.configure(state="disabled")  # Make it read-only

    # For tracking file position between reloads
    last_file_position = 0
    
    def should_display_line(line):
        """Check if the line should be displayed based on filters"""
        # Check log level filters
        if " | DEBUG | " in line and not log_filters["DEBUG"].get():
            return False
        elif " | INFO | " in line and not log_filters["INFO"].get():
            return False
        elif " | WARNING | " in line and not log_filters["WARNING"].get():
            return False
        elif " | ERROR | " in line and not log_filters["ERROR"].get():
            return False
        elif " | CRITICAL | " in line and not log_filters["CRITICAL"].get():
            return False
        
        # Check module filters
        module_found = False
        for module, pattern in LOG_MODULES.items():
            if f" | {pattern} | " in line:
                module_found = True
                if not module_filters[module].get():
                    return False
                break
        else:
            # If no specific module was found, check the "Other" filter
            if not module_filters["Other"].get():
                return False
        
        # Filter dirty logs when clean logs is enabled
        if " | DIRTY" in line and common.CLEAN_LOGS_ENABLED:
            return False
        
        return True
    
    def load_log_file(reload_all=False):
        """Load log file into display, optionally only loading new content"""
        nonlocal last_file_position
        
        try:
            if not os.path.exists(LOG_FILENAME):
                return
                
            current_size = os.path.getsize(LOG_FILENAME)
            
            # If file was truncated or reload_all requested, start from beginning
            if reload_all or current_size < last_file_position:
                log_text.configure(state="normal")
                log_text.delete("1.0", "end")
                last_file_position = 0
            
            # If there's new content
            if current_size > last_file_position:
                with open(LOG_FILENAME, 'r', encoding='utf-8', errors='replace') as f:
                    # Seek to where we left off
                    f.seek(last_file_position)
                    # Only read new lines
                    new_lines = f.readlines()
                
                # Update tracking position
                last_file_position = current_size
                
                # Process and add only the new lines
                if new_lines:
                    log_text.configure(state="normal")
                    for line in new_lines:
                        # Apply filters to the line
                        if should_display_line(line):
                            # Format line with time ago
                            formatted_line = format_log_line_with_time_ago(line)
                            log_text.insert("end", formatted_line)
                    
                    # Scroll to end to show new content
                    log_text.see("end")
                    log_text.configure(state="disabled")
        except Exception as e:
            error(f"Error loading log file: {e}")

    button_frame = ctk.CTkFrame(log_card, fg_color="transparent")
    button_frame.pack(fill="x", padx=10, pady=(0, 10))

    def clear_gui_logs():
        """Clear only the log display in the GUI"""
        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        log_text.configure(state="disabled")

    def clear_log_file():
        """Clear the content of the log file on disk"""
        try:
            # Close and reopen the log file in write mode to truncate it
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    
            # Truncate the file
            with open(LOG_FILENAME, 'w') as f:
                f.write("")
                
            # Reinitialize the file handler
            for handler in logger.handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.stream = open(handler.baseFilename, handler.mode)
            
            # Refresh the display
            load_log_file(reload_all=True)
        except Exception as e:
            error(f"Error clearing log file: {e}")
            messagebox.showerror("Error", f"Failed to clear log file: {e}")

    # Buttons with responsive layout
    clear_gui_logs_btn = ctk.CTkButton(button_frame, text="Clear GUI", command=clear_gui_logs, width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    clear_gui_logs_btn.pack(side="left", padx=5, pady=5)

    clear_log_file_btn = ctk.CTkButton(button_frame, text="Clear File", command=clear_log_file, width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    clear_log_file_btn.pack(side="left", padx=5, pady=5)

    reload_btn = ctk.CTkButton(button_frame, text="Reload", command=lambda: load_log_file(reload_all=True), width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    reload_btn.pack(side="left", padx=5, pady=5)

    # Auto-reload toggle
    auto_reload_var = ctk.BooleanVar(value=True)  # Default to on
    auto_reload_switch = ctk.CTkSwitch(
        master=button_frame,
        text="Auto-reload",
        variable=auto_reload_var,
        onvalue=True,
        offvalue=False,
        font=UIStyle.BODY_FONT
    )
    auto_reload_switch.pack(side="right", padx=5, pady=5)

    log_handler = OptimizedLogHandler(log_text, log_filters, module_filters)

    # Add the handler to the ROOT logger to capture logs from all scripts
    root_logger = logging.getLogger()
    root_logger.addHandler(log_handler)

    # File monitoring for real-time log updates
    last_modified_time = 0
    
    def check_log_file_changes():
        """Check if log file has been modified and reload if needed"""
        nonlocal last_modified_time
        
        if logs_tab_loaded and sidebar.current_page == "Logs" and auto_reload_var.get():
            try:
                if os.path.exists(LOG_FILENAME):
                    current_modified_time = os.path.getmtime(LOG_FILENAME)
                    if current_modified_time != last_modified_time:
                        last_modified_time = current_modified_time
                        load_log_file(reload_all=False)
            except Exception:
                pass
        
        # Check again in 10ms for instant updates
        root.after(10, check_log_file_changes)
    
    # Initialize last modified time and start monitoring
    if os.path.exists(LOG_FILENAME):
        last_modified_time = os.path.getmtime(LOG_FILENAME)
    
    # Load initial content and start monitoring
    load_log_file(reload_all=True)
    check_log_file_changes()

    logs_tab_loaded = True

# Setting up the Help tab (lightweight, no lazy loading needed)
help_scroll = ctk.CTkScrollableFrame(master=tab_help, corner_radius=UIStyle.CORNER_RADIUS)
help_scroll.pack(fill="both", expand=True, padx=UIStyle.INNER_PADDING, pady=UIStyle.INNER_PADDING)

def render_help_text():
    try:
        if not os.path.exists(HELP_TEXT_PATH):
            ctk.CTkLabel(help_scroll, text="Help file not found.", font=UIStyle.BODY_FONT).pack(pady=20)
            return

        with open(HELP_TEXT_PATH, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        # Simple parsing: Split by double newlines to get paragraphs/sections
        blocks = content.split('\n\n')
        
        # Intro card for the first block(s)
        intro_card = CardFrame(help_scroll)
        intro_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(intro_card, text="General Info", font=UIStyle.SUBHEADER_FONT).pack(anchor="w", padx=20, pady=(15, 10))
        
        current_card = intro_card
        
        text_labels = []
        
        for block in blocks:
            lines = block.strip().split('\n')
            if not lines: continue
            
            # Check if this block looks like a new section (first line ends with :)
            if lines[0].strip().endswith(':'):
                # Create new card
                header = lines[0].strip()[:-1].title()
                body = '\n'.join(lines[1:])
                
                current_card = CardFrame(help_scroll)
                current_card.pack(fill="x", padx=10, pady=10)
                
                ctk.CTkLabel(current_card, text=header, font=UIStyle.SUBHEADER_FONT).pack(anchor="w", padx=20, pady=(15, 10))
                if body.strip():
                    label = ctk.CTkLabel(current_card, text=body, font=UIStyle.BODY_FONT, justify="left", text_color=UIStyle.TEXT_SECONDARY_COLOR)
                    label.pack(anchor="w", padx=20, pady=(0, 15))
                    text_labels.append(label)
            else:
                # Just text, append to current card
                body = '\n'.join(lines)
                label = ctk.CTkLabel(current_card, text=body, font=UIStyle.BODY_FONT, justify="left", text_color=UIStyle.TEXT_SECONDARY_COLOR)
                label.pack(anchor="w", padx=20, pady=(0, 15))
                text_labels.append(label)
        
        # Add About Card
        about_card = CardFrame(help_scroll)
        about_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(about_card, text="About", font=UIStyle.SUBHEADER_FONT).pack(anchor="w", padx=20, pady=(15, 10))
        
        version_text = version_label.cget("text") if 'version_label' in globals() else "v2.0"
        about_text = f"WorkerBee {version_text}\nDeveloped by Bonk\n\nAn automated assistant for Limbus Company. Forked from Kryxzort's release added with Harry's fixes.\nUse responsibly."
        about_label = ctk.CTkLabel(about_card, text=about_text, font=UIStyle.BODY_FONT, justify="left", text_color=UIStyle.TEXT_SECONDARY_COLOR)
        about_label.pack(anchor="w", padx=20, pady=(0, 15))
        text_labels.append(about_label)
        
        def update_wraplength(event):
            width = event.width - 80
            if width < 200: width = 200
            for label in text_labels:
                label.configure(wraplength=width)
        
        help_scroll.bind("<Configure>", update_wraplength)
                
    except Exception as e:
        error(f"Error rendering help text: {e}")
        ctk.CTkLabel(help_scroll, text=f"Error loading help: {e}", font=UIStyle.BODY_FONT).pack(pady=20)

render_help_text()

# Add Discord invite button at bottom of Help tab
discord_card = CardFrame(help_scroll)
discord_card.pack(fill="x", padx=10, pady=10)
discord_button = ctk.CTkButton(discord_card, text="Join Discord", command=join_discord, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
discord_button.pack(pady=20)

if load_settings_on_startup:
    sidebar.show_page("Settings")
    # Manually trigger the Settings tab loading since set() doesn't trigger the callback
    root.after(10, load_settings_tab)

# Register keyboard shortcuts based on config values
register_keyboard_shortcuts()

# Start the dedicated keyboard handler thread
keyboard_handler.start()

# Show default page
sidebar.show_page("Dashboard")

# =====================================================================
# COMPACT MODE
# =====================================================================

is_compact_mode = False
previous_geometry = "900x800"

def toggle_compact_mode():
    global is_compact_mode, previous_geometry
    
    if not is_compact_mode:
        # Enter Compact Mode
        previous_geometry = root.geometry()
        is_compact_mode = True
        
        # Hide main UI
        sidebar_frame.pack_forget()
        content_area.pack_forget()
        
        # Show Compact UI
        compact_frame.pack(fill="both", expand=True)
        
        # Resize window
        root.geometry("300x150")
        root.resizable(False, False)
        root.title("WorkerBee (Compact)")
    else:
        # Exit Compact Mode
        is_compact_mode = False
        
        # Hide Compact UI
        compact_frame.pack_forget()
        
        # Show main UI
        sidebar_frame.pack(side="left", fill="y")
        content_area.pack(side="right", fill="both", expand=True)
        
        # Restore window
        root.geometry(previous_geometry)
        root.resizable(True, True)
        root.title(original_title)

# Create Compact Frame (hidden initially)
compact_frame = ctk.CTkFrame(main_container, fg_color=UIStyle.MAIN_BG_COLOR)

# Compact UI Elements
compact_status_label = ctk.CTkLabel(compact_frame, text="Idle", font=UIStyle.SUBHEADER_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
compact_status_label.pack(pady=(20, 5))

compact_stop_btn = ctk.CTkButton(compact_frame, text="Stop", command=stop_running_process, fg_color="#c42b1c", hover_color="#8f1f14", width=100, height=UIStyle.BUTTON_HEIGHT)

ctk.CTkButton(compact_frame, text="Expand", command=toggle_compact_mode, width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="bottom", pady=20)

# ===============================================
# PROCESS MONITORING AND APPLICATION MANAGEMENT
# ===============================================

def check_processes():
    """Check if processes are still running and update UI accordingly"""
    global process, exp_process, threads_process, function_process_list, battle_process
    
    # Check Mirror Dungeon process
    if process is not None:
        if not process.is_alive():
            # Process has ended
            process = None
            start_button.configure(text="Start")
    
    # Check Exp process
    if exp_process is not None:
        if not exp_process.is_alive():
            # Process has ended
            exp_process = None
            exp_start_button.configure(text="Start")
    
    # Check Threads process
    if threads_process is not None:
        if not threads_process.is_alive():
            # Process has ended
            threads_process = None
            threads_start_button.configure(text="Start")
    
    # Check Battle process specifically
    if battle_process is not None:
        if battle_process.poll() is not None:
            # Battle process has ended
            # Clear the battle process variable
            battle_process = None
    
    # Check all Function Runner processes
    for proc in function_process_list[:]:  # Use a copy of the list for iteration
        if proc.poll() is not None:
            # Process has ended
            # Remove from list
            function_process_list.remove(proc)
    
    # Update terminate button state based on whether any function processes are running
    if function_process_list:
        function_terminate_button.configure(state="normal")
    else:
        function_terminate_button.configure(state="disabled")
    
    # Update Dashboard Status
    if 'status_label' in globals():
        running_process = get_running_process_name()
        if running_process:
            status_label.configure(text=f"Running: {running_process}", text_color=UIStyle.ACCENT_COLOR)
            
            # Update Compact Mode UI
            if 'compact_status_label' in globals():
                compact_status_label.configure(text=f"Running: {running_process}", text_color=UIStyle.ACCENT_COLOR)
                compact_stop_btn.pack(pady=5) # Show stop button
        else:
            status_label.configure(text="Idle", text_color=UIStyle.TEXT_SECONDARY_COLOR)
            
            # Update Compact Mode UI
            if 'compact_status_label' in globals():
                compact_status_label.configure(text="Idle", text_color=UIStyle.TEXT_SECONDARY_COLOR)
                compact_stop_btn.pack_forget() # Hide stop button

    # Schedule next check
    root.after(1000, check_processes)
    root.after(5000, check_scheduler)

def on_closing():
    """Handle application exit cleanup"""
    try:
        
        # Stop async logging process FIRST
        try:
            from src.logger import stop_async_logging
            stop_async_logging()
        except Exception:
            pass  # Ignore cleanup errors
        
        try:
            # Kill multiprocessing processes with force if needed
            if process and process.is_alive():
                process.terminate()
                process.join(timeout=2)
                if process.is_alive():
                    process.kill()
                    process.join(timeout=1)
            if exp_process and exp_process.is_alive():
                exp_process.terminate()
                exp_process.join(timeout=2)
                if exp_process.is_alive():
                    exp_process.kill()
                    exp_process.join(timeout=1)
            if threads_process and threads_process.is_alive():
                threads_process.terminate()
                threads_process.join(timeout=2)
                if threads_process.is_alive():
                    threads_process.kill()
                    threads_process.join(timeout=1)
            if battlepass_process and battlepass_process.is_alive():
                battlepass_process.terminate()
                battlepass_process.join(timeout=2)
                if battlepass_process.is_alive():
                    battlepass_process.kill()
                    battlepass_process.join(timeout=1)
            
            # Kill subprocess processes with force
            if battle_process and battle_process.poll() is None:
                try:
                    os.kill(battle_process.pid, signal.SIGTERM)
                    time.sleep(0.5)
                    if battle_process.poll() is None:
                        os.kill(battle_process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            for proc in function_process_list:
                if proc and proc.poll() is None:
                    try:
                        os.kill(proc.pid, signal.SIGTERM)
                        time.sleep(0.5)
                        if proc.poll() is None:
                            os.kill(proc.pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        except Exception as e:
            error(f"Error killing processes: {e}")
        
        try:
            if 'log_handler' in globals() and log_handler:
                log_handler.close()
        except Exception:
            pass  # Ignore cleanup errors
        
        try:
            keyboard_handler.stop()
        except Exception:
            pass  # Ignore cleanup errors
        
        
        # Stop background threads from running processes
        try:
            if process and hasattr(process, '_target') and process._target:
                # Force stop any connection monitoring threads in compiled_runner
                import threading
                for thread in threading.enumerate():
                    if thread.name.startswith('Thread-') and thread.daemon and thread.is_alive():
                        try:
                            thread._stop()
                        except:
                            pass
        except Exception:
            pass  # Ignore cleanup errors
            
    except Exception as e:
        error(f"Error during application close: {e}")
    finally:
        # Clean up PID file if it exists
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except:
            pass  # Ignore cleanup errors
            
        sys.exit(0)

# Set the callback for window close
root.protocol("WM_DELETE_WINDOW", on_closing)

# =======================
# APPLICATION STARTUP
# =======================

if __name__ == "__main__":
    def start_application():
        """Initialize the application after GUI is loaded"""
        try:
            # Load checkbox data at startup (before any automation can run)
            load_checkbox_data()
            
            # Check for updates if enabled
            if config['Settings'].get('auto_update', False):
                try:
                    import updater
                    def update_cb(success, msg):
                        if success:
                            logger.info(f"Auto-update: {msg}")
                    updater.auto_update("Bonkier", "WorkerBee", callback=update_cb)
                except Exception as e:
                    logger.error(f"Failed to initialize auto-updater: {e}")
            
            check_processes()
            
        except Exception as e:
            error(f"Error in start_application: {e}")
    
    # Make sure "all data" folder exists in the correct location
    os.makedirs(BASE_PATH, exist_ok=True)
    
    # Initialize common module settings after GUI is ready
    def delayed_common_init():
        try:
            init_common_settings()
            monitor_index = shared_vars.game_monitor.value
            common.set_game_monitor(monitor_index)
        except Exception as e:
            error(f"Error initializing common module: {e}")
    
    root.after(5, start_application)
    # Initialize common settings after startup
    root.after(100, delayed_common_init)
    
    root.mainloop()
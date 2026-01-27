import os
import sys
import logging
import json
import subprocess
import webbrowser
import threading
import platform
import time
import traceback

# Setup debug logging immediately
def log_debug(msg):
    try:
        with open("launcher_debug.log", "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} - {msg}\n")
    except: pass

log_debug("Starting gui_launcher.py")

# Try to import GUI libraries first to ensure we can show errors
try:
    import customtkinter as ctk
    import tkinter as tk
    from tkinter import messagebox
except ImportError as e:
    log_debug(f"GUI import failed: {e}")
    # Fallback to ctypes for message box if tkinter fails
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Critical dependency missing: {e}\nPlease run bootstrapper.py", "Startup Error", 0x10)
    except:
        print(f"Critical dependency missing: {e}")
    sys.exit(1)

try:
    log_debug("Importing modules...")
    # Import common FIRST to set up DirtyLogger before any logging setup
    sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
    import common
    from src.mp_types import SharedVars

    # Import GUI components
    from src.gui.styles import UIStyle
    from src.gui.components import SidebarNavigation, CardFrame, ToolTip
    from src.gui.themes import load_available_themes
    from src.gui.constants import DISCORD_INVITE, STATUS_COLUMNS, SINNER_LIST, TEAM_ORDER, LOG_MODULES
    from src.gui.utils import load_json_data, save_json_data, format_log_line_with_time_ago, ensure_schedule_file
    from src.gui.settings_page import load_settings_tab as load_settings_page
    import src.gui.ui_updater as ui_updater_module
    import src.gui.app_lifecycle as app_lifecycle
    from src.gui.statistics_page import load_statistics_tab as load_statistics_page
    from src.gui.schedule_page import load_schedule_tab as load_schedule_page
    from src.gui.others_page import load_others_tab as load_others_page
    from src.gui.logs_page import load_logs_tab as load_logs_page
    from src.gui.help_page import load_help_tab as load_help_page
    from src.gui.mirror_page import load_mirror_tab as load_mirror_page
    from src.gui.exp_page import load_exp_tab as load_exp_page
    from src.gui.threads_page import load_threads_tab as load_threads_page
    from src.gui.dashboard_page import load_dashboard_tab as load_dashboard_page
    import src.gui.process_handler as process_handler
    import src.gui.chain_automation as chain_automation
    from src.gui.keyboard_handler import KeyboardHandler
    from src.gui.scheduler_handler import SchedulerHandler
    log_debug("Modules imported successfully")

except Exception as e:
    log_debug(f"Module import failed: {e}\n{traceback.format_exc()}")
    # Catch any import errors (missing files, syntax errors in modules)
    err_msg = traceback.format_exc()
    print(err_msg)
    # Log to file in case console is not visible
    try:
        with open("launcher_error.log", "w") as f:
            f.write(err_msg)
    except:
        pass
    # Use ctypes for reliable error box on Windows even if tk isn't ready
    try:
        import ctypes
        ctypes.windll.user32.MessageBoxW(0, f"Failed to load application modules:\n\n{e}\n\nSee console for details.", "Startup Error", 0x10)
    except:
        pass
    sys.exit(1)

# Global variables and UI Setup (Moved after imports)
root = None
sidebar = None
shared_vars = None
config = None
keyboard_handler = None
scheduler_handler = None

LOG_FILENAME = common.LOG_FILENAME
BASE_PATH = common.BASE_PATH
HELP_TEXT_PATH = os.path.join(common.BASE_PATH, "Help.txt")
FUNCTION_RUNNER_PATH = os.path.join(BASE_PATH, "src", "function_runner.py")
THEME_RESTART_PATH = os.path.join(BASE_PATH, "src", "theme_restart.py")
PID_FILE = os.path.join(common.BASE_PATH, "workerbee.pid")

original_title = "WorkerBee | Bonk"
is_compact_mode = False
previous_geometry = "1200x800"
compact_frame = None

# UI Context for shared widgets across pages
ui_context = {}

def get_display_version():
    try:
        v_path = os.path.join(BASE_PATH, "version.json")
        if os.path.exists(v_path):
            with open(v_path, "r") as f:
                content = f.read().strip()
                try:
                    data = json.loads(content)
                    if isinstance(data, dict) and "version" in data:
                        v = str(data["version"])
                    else:
                        v = content
                except json.JSONDecodeError:
                    v = content
                if v:
                    return f"v{v}" if v[0].isdigit() else v
    except:
        pass
    return "v2.0"

def get_running_process_name():
    return process_handler.get_running_process_name()

def run_scheduler_check():
    if scheduler_handler:
        scheduler_handler.check_scheduler()
    if root:
        root.after(5000, run_scheduler_check)

def save_window_geometry():
    if root:
        if is_compact_mode and previous_geometry:
            try:
                # Parse previous_geometry (e.g., "1200x800+100+100") to save the restored size
                geo_parts = previous_geometry.split('+')[0].split('x')
                if len(geo_parts) == 2:
                    config["Settings"]["window_width"] = int(geo_parts[0])
                    config["Settings"]["window_height"] = int(geo_parts[1])
                    save_settings()
            except Exception:
                pass
        else:
            config["Settings"]["window_width"] = root.winfo_width()
            config["Settings"]["window_height"] = root.winfo_height()
            save_settings()

def save_settings():
    """Save current shared_vars to config file"""
    if config is None or shared_vars is None:
        return

    if "Settings" not in config:
        config["Settings"] = {}
    
    settings = config["Settings"]
    
    # Helper to save value safely
    def save_val(name):
        if hasattr(shared_vars, name):
            val = getattr(shared_vars, name).value
            settings[name] = val

    # List of variables to save
    vars_to_save = [
        "game_monitor", "skip_restshop", "skip_ego_check", "skip_ego_fusion",
        "skip_sinner_healing", "skip_ego_enhancing", "skip_ego_buying",
        "prioritize_list_over_status", "debug_image_matches", "hard_mode",
        "convert_images_to_grayscale", "reconnection_delay", 
        "reconnect_when_internet_reachable", "good_pc_mode", "click_delay",
        "retry_count", "claim_on_defeat", "pack_refreshes", "mirror_runs",
        "exp_runs", "exp_stage", "threads_runs", "threads_difficulty"
    ]
    
    for v in vars_to_save:
        save_val(v)
        
    save_json_data(os.path.join(BASE_PATH, "config", "gui_config.json"), config)

# Initialize Logger
logger = logging.getLogger("gui_launcher")

# Initialize Shared Variables and Config (Global scope to match 1.0.6.3 behavior)
log_debug("Initializing SharedVars and Config...")
shared_vars = SharedVars()
config = load_json_data(os.path.join(BASE_PATH, "config", "gui_config.json"))
if not config:
    config = {"Settings": {}}
if "Settings" not in config:
    config["Settings"] = {}

# Load preferences immediately at module level to ensure shared_vars is populated
app_lifecycle.load_preferences(config, shared_vars)

def reset_settings_to_defaults():
    """Reset all settings to default values"""
    if messagebox.askyesno("Reset Settings", "Are you sure you want to reset all settings to defaults?"):
        try:
            # Create a new instance to get default values
            default_vars = SharedVars()
            
            # List of all shared variables to reset
            fields = [
                'game_monitor', 'skip_restshop', 'skip_ego_check', 'skip_ego_fusion',
                'skip_sinner_healing', 'skip_ego_enhancing', 'skip_ego_buying',
                'prioritize_list_over_status', 'debug_image_matches', 'hard_mode',
                'convert_images_to_grayscale', 'reconnection_delay', 'reconnect_when_internet_reachable',
                'good_pc_mode', 'click_delay', 'retry_count', 'claim_on_defeat', 'pack_refreshes', 'mirror_runs',
                'exp_runs', 'exp_stage', 'threads_runs', 'threads_difficulty'
            ]
            
            for field in fields:
                if hasattr(shared_vars, field) and hasattr(default_vars, field):
                    getattr(shared_vars, field).value = getattr(default_vars, field).value
            
            save_settings()
            load_settings_tab()
            logger.info("Settings reset to defaults")
            messagebox.showinfo("Success", "Settings have been reset to defaults.")
        except Exception as e:
            logger.error(f"Error resetting settings: {e}")
            messagebox.showerror("Error", f"Failed to reset settings: {e}")


def stop_running_process():
    """Stop whatever automation is currently running"""
    # Update Status Label immediately for better UX
    if ui_context and 'status_label' in ui_context:
        ui_context['status_label'].configure(text="Stopping...", text_color="orange")

    def _stop_thread():
        # 1. Stop Chain Automation (Module level)
        if chain_automation.chain_running:
            chain_automation.stop_chain_automation(ui_context)

        # 2. Cleanup all processes via handler (Parallel kill)
        process_handler.cleanup_processes()

    threading.Thread(target=_stop_thread, daemon=True).start()

def kill_battlepass():
    """Kill Battlepass Collector subprocess"""
    # Delegate to process handler cleanup as it manages the battlepass process now
    if process_handler.battlepass_process:
        process_handler.cleanup_processes()

def start_mirror_dungeon(runs=None):
    try:
        # Save settings before starting
        save_settings() 
        
        # If runs is not specified, load from config
        if runs is None or runs == 999999:
            # Default to 1 if not found or invalid
            runs = int(config.get("Settings", {}).get("mirror_runs", 1))
            log_debug(f"Starting Mirror Dungeon with {runs} runs (from config)")
        
        if process_handler.start_mirror_dungeon(shared_vars, runs=runs):
            if 'mirror_start_button' in ui_context and ui_context['mirror_start_button']:
                ui_context['mirror_start_button'].configure(text="Stop", command=stop_running_process, fg_color="#c42b1c", hover_color="#8f1f14")
            if 'status_label' in ui_context and ui_context['status_label']:
                ui_context['status_label'].configure(text="Running: Mirror Dungeon", text_color=UIStyle.ACCENT_COLOR)
    except Exception as e:
        logger.error(f"Failed to start Mirror Dungeon: {e}")

def start_exp_luxcavation():
    try:
        if process_handler.start_exp_luxcavation(shared_vars):
            if 'exp_start_button' in ui_context and ui_context['exp_start_button']:
                ui_context['exp_start_button'].configure(text="Stop", command=stop_running_process, fg_color="#c42b1c", hover_color="#8f1f14")
            if 'status_label' in ui_context and ui_context['status_label']:
                ui_context['status_label'].configure(text="Running: Luxcavation (EXP)", text_color=UIStyle.ACCENT_COLOR)
    except Exception as e:
        logger.error(f"Failed to start EXP Luxcavation: {e}")

def start_thread_luxcavation():
    try:
        if process_handler.start_thread_luxcavation(shared_vars):
            if 'threads_start_button' in ui_context and ui_context['threads_start_button']:
                ui_context['threads_start_button'].configure(text="Stop", command=stop_running_process, fg_color="#c42b1c", hover_color="#8f1f14")
            if 'status_label' in ui_context and ui_context['status_label']:
                ui_context['status_label'].configure(text="Running: Luxcavation (Thread)", text_color=UIStyle.ACCENT_COLOR)
    except Exception as e:
        logger.error(f"Failed to start Thread Luxcavation: {e}")

def start_chain_automation():
    chain_automation.start_chain_automation(ui_context, shared_vars)

def toggle_compact_mode():
    global is_compact_mode, previous_geometry
    
    if not is_compact_mode:
        # Enter Compact Mode
        previous_geometry = root.geometry()
        is_compact_mode = True
        
        sidebar_frame.pack_forget()
        content_area.pack_forget()
        compact_frame.pack(fill="both", expand=True)
        
        root.geometry("300x150")
        root.resizable(False, False)
        root.title("WorkerBee (Compact)")
    else:
        # Exit Compact Mode
        is_compact_mode = False
        compact_frame.pack_forget()
        sidebar_frame.pack(side="left", fill="y")
        content_area.pack(side="right", fill="both", expand=True)
        root.geometry(previous_geometry)
        root.resizable(True, True)
        root.title(original_title)

def terminate_functions():
    process_handler.terminate_functions()
    if ui_context.get('function_terminate_button'):
        ui_context['function_terminate_button'].configure(state="disabled")

def call_function():
    """Call a function using function_runner.py"""
    function_name = ui_context['function_entry'].get().strip()
    if not function_name:
        messagebox.showerror("Invalid Input", "Please enter a function to call.")
        return
    
    python_cmd = sys.executable
    process_handler.call_function(function_name, BASE_PATH, python_cmd)
    
    if 'function_terminate_button' in ui_context and ui_context['function_terminate_button']:
        ui_context['function_terminate_button'].configure(state="normal")

def start_battle():
    python_cmd = sys.executable
    process_handler.start_battle(BASE_PATH, python_cmd)

def toggle_mirror_dungeon():
    if process_handler.process and process_handler.process.is_alive():
        stop_running_process()
    else:
        start_mirror_dungeon()

def toggle_exp():
    if process_handler.exp_process and process_handler.exp_process.is_alive():
        stop_running_process()
    else:
        start_exp_luxcavation()

def toggle_threads():
    if process_handler.threads_process and process_handler.threads_process.is_alive():
        stop_running_process()
    else:
        start_thread_luxcavation()

def toggle_chain():
    if chain_automation.chain_running:
        chain_automation.stop_chain_automation(ui_context)
    else:
        start_chain_automation()

def restart_with_theme(theme_name):
    """Restart application to apply theme"""
    try:
        # Save settings first
        save_settings()
        
        # Start theme_restart.py
        subprocess.Popen([sys.executable, THEME_RESTART_PATH, theme_name, "Settings"])
        
        # Exit immediately
        os._exit(0)
    except Exception as e:
        logger.error(f"Error applying theme: {e}")
        messagebox.showerror("Error", f"Failed to apply theme: {e}")

def perform_cleanup():
    """Clean up all running processes and resources"""
    try:
        # Stop async logging process FIRST
        try:
            # Fast kill logging process without waiting
            import src.logger as logger_module
            if logger_module._log_process and logger_module._log_process.is_alive():
                logger_module._log_process.terminate()
        except Exception:
            pass  # Ignore cleanup errors
        
        try:
            if chain_automation.chain_running:
                chain_automation.stop_chain_automation(None)
            else:
                process_handler.cleanup_processes()
        except Exception as e:
            print(f"Error killing processes: {e}")
        
        try:
            # Close all logging handlers
            for handler in logging.getLogger().handlers:
                handler.close()
        except Exception:
            pass  # Ignore cleanup errors
        
        try:
            # Only try to stop keyboard handler if it's running, and don't wait too long
            if keyboard_handler and keyboard_handler.running:
                keyboard_handler.stop()
        except Exception as e:
            pass  # Ignore cleanup errors
        
        # Stop background threads from running processes
        try:
            if process_handler.process and hasattr(process_handler.process, '_target') and process_handler.process._target:
                # Force stop any connection monitoring threads
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
        logger.error(f"Error during cleanup: {e}")

def on_closing():
    """Handle application exit cleanup"""
    # Hide window immediately to give instant feedback
    try:
        if root:
            root.withdraw()
    except:
        pass
    
    save_window_geometry()
        
    try:
        perform_cleanup()
    except Exception as e:
        print(f"Error during application close: {e}")
    finally:
        # Clean up PID file if it exists
        try:
            if os.path.exists(PID_FILE):
                os.remove(PID_FILE)
        except:
            pass  # Ignore cleanup errors
            
        # Nuclear option for Windows to ensure everything dies
        if platform.system() == "Windows":
            try:
                # Spawn a taskkill command to kill this process tree forcefully
                # We use shell=True with CREATE_NO_WINDOW to hide the command prompt
                # We add a small delay to ensure this command is dispatched before we exit
                subprocess.Popen(f"taskkill /F /PID {os.getpid()} /T",
                               shell=True, 
                               creationflags=0x08000000) # CREATE_NO_WINDOW
                time.sleep(0.2)
            except:
                pass
        
        os._exit(0)

def join_discord():
    """Open Discord invite link"""
    webbrowser.open(DISCORD_INVITE)


logs_tab_loaded = False
def setup_logs_tab():
    global logs_tab_loaded, tab_logs
    if not logs_tab_loaded:
        try:
            load_logs_page(tab_logs, LOG_FILENAME, LOG_MODULES, config, save_settings, root)
            logs_tab_loaded = True
        except Exception as e:
            logger.error(f"Failed to load logs tab: {e}")

def setup_help_tab():
    if 'tab_help' in globals():
        load_help_page(tab_help, HELP_TEXT_PATH, get_display_version(), join_discord)

# Define wrapper functions for tab loading
def load_dashboard_tab():
    try:
        load_dashboard_page(tab_dashboard, sidebar, callbacks, ui_context)
    except Exception as e:
        logger.error(f"Failed to load dashboard tab: {e}")
        log_debug(f"Failed to load dashboard tab: {e}")

def load_mirror_tab():
    try:
        load_mirror_page(tab_md, config, shared_vars, callbacks, ui_context, BASE_PATH, save_settings)
    except Exception as e:
        logger.error(f"Failed to load mirror tab: {e}")

def load_exp_tab():
    try:
        load_exp_page(tab_exp, config, shared_vars, callbacks, ui_context, BASE_PATH, save_settings)
    except Exception as e:
        logger.error(f"Failed to load exp tab: {e}")

def load_threads_tab():
    try:
        load_threads_page(tab_threads, config, shared_vars, callbacks, ui_context, BASE_PATH, save_settings)
    except Exception as e:
        logger.error(f"Failed to load threads tab: {e}")

def load_schedule_tab():
    try:
        load_schedule_page(tab_schedule, BASE_PATH)
    except Exception as e:
        logger.error(f"Failed to load schedule tab: {e}")

def load_others_tab():
    try:
        load_others_page(tab_others, config, callbacks, ui_context)
    except Exception as e:
        logger.error(f"Failed to load others tab: {e}")

def load_statistics_tab():
    try:
        load_statistics_page(tab_statistics, BASE_PATH)
    except Exception as e:
        logger.error(f"Failed to load statistics tab: {e}")

settings_tab_loaded = False
def load_settings_tab():
    global settings_tab_loaded, tab_settings
    if not settings_tab_loaded:
        try:
            load_settings_page(tab_settings, config, shared_vars, save_settings, BASE_PATH, root, restart_with_theme, keyboard_handler.update_shortcuts)
            settings_tab_loaded = True
        except Exception as e:
            logger.error(f"Failed to load settings tab: {e}")

def _lazy_show_page(name):
    if name == "Settings":
        load_settings_tab()
    elif name == "Logs":
        setup_logs_tab()

# =======================
# APPLICATION STARTUP
# =======================

if __name__ == "__main__":
    # Essential for Windows multiprocessing support
    import multiprocessing
    multiprocessing.freeze_support()

    # Initialize Main UI
    log_debug("Initializing Main UI (ctk.CTk)...")
    root = ctk.CTk()
    root.title(original_title)
    w = config.get("Settings", {}).get("window_width", 1200)
    h = config.get("Settings", {}).get("window_height", 800)
    root.geometry(f"{w}x{h}")

    # Load and apply theme
    log_debug("Loading themes...")
    available_themes = load_available_themes(BASE_PATH)
    current_theme_name = config.get("Settings", {}).get("appearance_mode", "Dark")
    if current_theme_name not in available_themes:
        current_theme_name = "Dark"

    ctk.set_appearance_mode(available_themes[current_theme_name]["mode"])
    ctk.set_default_color_theme(available_themes[current_theme_name]["theme"])

    log_debug("Creating main container...")
    main_container = ctk.CTkFrame(root, corner_radius=0, fg_color=UIStyle.MAIN_BG_COLOR)
    main_container.pack(fill="both", expand=True)

    sidebar_frame = ctk.CTkFrame(main_container, width=UIStyle.SIDEBAR_WIDTH, corner_radius=0, fg_color=UIStyle.SIDEBAR_COLOR)
    sidebar_frame.pack(side="left", fill="y")
    sidebar_frame.pack_propagate(False)

    log_debug("Creating content area...")
    content_area = ctk.CTkFrame(main_container, corner_radius=0, fg_color="transparent")
    content_area.pack(side="right", fill="both", expand=True)

    log_debug("Initializing SidebarNavigation...")
    sidebar = SidebarNavigation(sidebar_frame, content_area)

    # Define tabs globally so lazy loading works
    tab_dashboard = sidebar.add_page("Dashboard")
    tab_md = sidebar.add_page("Mirror Dungeon")
    tab_exp = sidebar.add_page("Exp")
    tab_threads = sidebar.add_page("Threads")
    tab_schedule = sidebar.add_page("Schedule")
    tab_others = sidebar.add_page("Others")
    tab_statistics = sidebar.add_page("Statistics")
    tab_settings = sidebar.add_page("Settings")
    tab_logs = sidebar.add_page("Logs")
    tab_help = sidebar.add_page("Help")

    # Sidebar Footer for Compact Mode
    log_debug("Creating sidebar footer...")
    sidebar_footer = ctk.CTkFrame(sidebar_frame, fg_color="transparent")
    sidebar_footer.pack(side="bottom", fill="x", padx=10, pady=20)

    version_label = ctk.CTkLabel(sidebar_footer, text=get_display_version(), font=UIStyle.SMALL_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
    version_label.pack(anchor="w", padx=10)

    ctk.CTkButton(sidebar_footer, text="Compact Mode", command=toggle_compact_mode, fg_color="transparent", border_width=1, text_color="gray90").pack(fill="x", pady=(10, 0))
    ctk.CTkButton(sidebar_footer, text="Exit Application", command=on_closing, height=30, fg_color="#c42b1c", hover_color="#8f1f14", font=UIStyle.SMALL_FONT).pack(fill="x", pady=(10, 0))

    # Compact Mode Frame
    log_debug("Creating compact mode frame...")
    compact_frame = ctk.CTkFrame(main_container, fg_color=UIStyle.MAIN_BG_COLOR)
    compact_status_label = ctk.CTkLabel(compact_frame, text="Idle", font=UIStyle.SUBHEADER_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
    compact_status_label.pack(pady=(20, 5))
    ui_context['compact_status_label'] = compact_status_label
    compact_stop_btn = ctk.CTkButton(compact_frame, text="Stop", command=stop_running_process, fg_color="#c42b1c", hover_color="#8f1f14", width=100, height=UIStyle.BUTTON_HEIGHT)
    compact_stop_btn.pack_forget()
    ui_context['compact_stop_btn'] = compact_stop_btn
    ctk.CTkButton(compact_frame, text="Expand", command=toggle_compact_mode, width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="bottom", pady=20)

    # Monkeypatch sidebar.show_page to implement lazy loading
    _original_show_page = sidebar.show_page
    def _lazy_show_page_wrapper(name):
        _lazy_show_page(name)
        _original_show_page(name)
    sidebar.show_page = _lazy_show_page_wrapper

    # Initialize Handlers
    callbacks = {
        'toggle_mirror': toggle_mirror_dungeon,
        'start_mirror': start_mirror_dungeon,
        'toggle_exp': toggle_exp,
        'start_exp': start_exp_luxcavation,
        'toggle_threads': toggle_threads,
        'start_threads': start_thread_luxcavation,
        'stop_all': stop_running_process,
        'toggle_chain': toggle_chain,
        'start_chain': start_chain_automation,
        'call_function': call_function,
        'terminate_functions': terminate_functions,
        'battle': start_battle,
        'load_statistics_tab': load_statistics_tab,
        'save_settings': save_settings
    }

    # Wrap callbacks for KeyboardHandler to ensure they run on the main thread
    # This prevents crashes when modifying UI elements from the keyboard thread
    def make_safe_callback(func):
        return lambda *args, **kwargs: root.after(0, lambda: func(*args, **kwargs))
    
    safe_keyboard_callbacks = {k: make_safe_callback(v) for k, v in callbacks.items()}

    log_debug("Initializing handlers...")
    keyboard_handler = KeyboardHandler(safe_keyboard_callbacks, config)
    scheduler_handler = SchedulerHandler(BASE_PATH, shared_vars, callbacks)

    # Start the dedicated keyboard handler thread
    keyboard_handler.start()

    # Handle CLI args for theme/tab restoration
    if len(sys.argv) > 2:
        target_tab = sys.argv[2]
        if target_tab in sidebar.buttons:
            sidebar.show_page(target_tab)
    else:
        # Show default page
        sidebar.show_page("Dashboard")

    log_debug("Loading initial tabs...")
    load_dashboard_tab()
    load_mirror_tab()
    load_exp_tab()
    load_threads_tab()
    setup_help_tab()
    log_debug("Initial tabs loaded")

    # Set the callback for window close
    root.protocol("WM_DELETE_WINDOW", on_closing)

    log_debug("Entering main block")
    def start_application():
        # Singleton check to prevent multiple instances
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(("127.0.0.1", 47329)) # Arbitrary port for lock
            # Keep socket open until exit
            globals()['_singleton_socket'] = s
        except socket.error:
            # Another instance is likely running
            # Check if we are the "updated" instance, if so, we should take precedence
            # But we can't easily kill the other one from here without PID
            # For now, just log and continue, but this might explain multiple instances
            logger.warning("Another instance of WorkerBee appears to be running.")
            
            # If we are the updated instance, give the old one a moment to die
            if "--updated" in sys.argv:
                time.sleep(2)
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.bind(("127.0.0.1", 47329))
                    globals()['_singleton_socket'] = s
                except:
                    pass

        """Initialize the application after GUI is loaded"""
        try:
            log_debug("Initializing application logic...")
            
            # Ensure schedule file exists
            ensure_schedule_file(BASE_PATH)
            load_schedule_tab()
            load_others_tab()
            load_statistics_tab()
            
            # Check for updated flag
            if "--updated" in sys.argv:
                messagebox.showinfo("Update Complete", f"WorkerBee has been updated to {get_display_version()}")

            # Check internet connection
            if not common.check_internet_connection():
                root.title("WorkerBee | Bonk (Offline)")
                logger.warning("No internet connection detected. Running in offline mode.")
                messagebox.showwarning("Offline Mode", "No internet connection detected.\nRunning in offline mode.")
            else:
                # Check for updates if enabled and online
                if config['Settings'].get('auto_update', False):
                    try:
                        import updater
                        def update_cb(success, msg):
                            if success:
                                logger.info(f"Auto-update: {msg}")
                                perform_cleanup()
                                os._exit(0)
                            else:
                                logger.info(f"Auto-update check: {msg}")
                        updater.auto_update("Bonkier", "WorkerBee", create_backup=False, callback=update_cb, pre_exit_callback=perform_cleanup)
                    except Exception as e:
                        logger.error(f"Failed to initialize auto-updater: {e}")
            
            run_scheduler_check()
            
        except Exception as e:
            log_debug(f"Error in start_application: {e}")
            logger.error(f"Error in start_application: {e}")
    
    log_debug("Creating data directory...")
    # Make sure "all data" folder exists in the correct location
    os.makedirs(BASE_PATH, exist_ok=True)
    
    # Initialize common module settings after GUI is ready
    def delayed_common_init():
        try:
            app_lifecycle.setup_environment(shared_vars)
            monitor_index = shared_vars.game_monitor.value
            common.set_game_monitor(monitor_index)
            
            # Initialize logging settings
            common.CLEAN_LOGS_ENABLED = config['Settings'].get('clean_logs', True)
            common.initialize_async_logging()
            if hasattr(common, 'set_logging_enabled'):
                common.set_logging_enabled(config['Settings'].get('logging_enabled', True))
        except Exception as e:
            logger.error(f"Error initializing common module: {e}")
    
    log_debug("Scheduling startup tasks...")
    root.after(5, start_application)
    # Initialize common settings after startup
    root.after(100, delayed_common_init)

    # Initialize UI Updater
    log_debug("Initializing UI Updater...")
    ui_updater = ui_updater_module.UIUpdater(root, ui_context, shared_vars, callbacks, BASE_PATH, sidebar)

    # Start UI Updater loops
    ui_updater.check_processes()
    ui_updater.update_compact_status()
    ui_updater.check_stats_update()
    ui_updater.check_chain_status()
    
    log_debug("Starting mainloop...")
    root.mainloop()
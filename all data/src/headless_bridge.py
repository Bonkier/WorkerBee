import socket
import json
import sys
import os
import threading
import time
import logging
import queue
import multiprocessing
import traceback

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.append(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

import common
from src.mp_types import SharedVars
import src.gui.process_handler as process_handler
import src.gui.app_lifecycle as app_lifecycle
from src.gui.utils import load_json_data, save_json_data
import src.gui.chain_automation as chain_automation
from src.gui.keyboard_handler import KeyboardHandler
import src.gui.scheduler_handler as scheduler_handler
import src.updater as updater

HOST = '127.0.0.1'
PORT = 65432
BASE_PATH = parent_dir

shared_vars = SharedVars()
config = load_json_data(os.path.join(BASE_PATH, "config", "gui_config.json"))
log_queue = queue.Queue()

# --- Mock UI Context for Chain Automation compatibility ---
class DummyEntry:
    def __init__(self, value):
        self.value = str(value)
    def get(self):
        return self.value
    def configure(self, **kwargs):
        pass
    def after(self, ms, func):
        pass

class DummyWidget:
    def configure(self, **kwargs):
        pass
    def pack(self, **kwargs):
        pass
    def pack_forget(self):
        pass
    def winfo_ismapped(self):
        return True
    def after(self, ms, func):
        pass

ui_context = {
    'chain_threads_entry': DummyEntry(3),
    'chain_exp_entry': DummyEntry(2),
    'chain_mirror_entry': DummyEntry(1),
    'launch_game_var': type('obj', (object,), {'get': lambda: False}),
    'collect_rewards_var': type('obj', (object,), {'get': lambda: False}),
    'chain_start_button': DummyWidget(),
    'chain_status_label': DummyWidget(),
    'status_label': DummyWidget()
}

# --- Logging Setup ---
class QueueHandler(logging.Handler):
    def emit(self, record):
        try:
            msg = self.format(record)
            log_queue.put(msg)
        except Exception:
            pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gui_launcher")
queue_handler = QueueHandler()
formatter = logging.Formatter('%(asctime)s | %(name)s | %(levelname)s | %(message)s')
queue_handler.setFormatter(formatter)
logging.getLogger().addHandler(queue_handler)

def load_initial_settings():
    if "Settings" not in config:
        config["Settings"] = {}
    app_lifecycle.load_preferences(config, shared_vars)
    
    if hasattr(shared_vars, 'game_monitor'):
        common.set_game_monitor(shared_vars.game_monitor.value)
    
    if "clean_logs" in config["Settings"]:
        common.CLEAN_LOGS_ENABLED = config["Settings"]["clean_logs"]

    common.initialize_async_logging()

    ui_context['chain_threads_entry'].value = str(config.get("Settings", {}).get("chain_threads_runs", 3))
    ui_context['chain_exp_entry'].value = str(config.get("Settings", {}).get("chain_exp_runs", 2))
    ui_context['chain_mirror_entry'].value = str(config.get("Settings", {}).get("chain_mirror_runs", 1))
    
    launch_game = config.get("Settings", {}).get("launch_game_before_runs", False)
    collect_rewards = config.get("Settings", {}).get("collect_rewards_when_finished", False)
    
    ui_context['launch_game_var'] = type('obj', (object,), {'get': lambda: launch_game})
    ui_context['collect_rewards_var'] = type('obj', (object,), {'get': lambda: collect_rewards})

def handle_command(cmd_data):
    """Process JSON commands from Java UI"""
    response = {"status": "ok"}
    command = cmd_data.get("command")
    
    try:
        if command == "start_mirror":
            runs = int(cmd_data.get("runs", 1))
            config['Settings']['mirror_runs'] = runs
            success = process_handler.start_mirror_dungeon(shared_vars, runs)
            response["success"] = success
            
        elif command == "start_exp":
            runs = int(cmd_data.get("runs", 1))
            stage = cmd_data.get("stage", 6)
            try:
                shared_vars.exp_runs.value = runs
                if str(stage) != "latest":
                    shared_vars.exp_stage.value = int(stage)
            except Exception:
                pass
            success = process_handler.start_exp_luxcavation(shared_vars, runs, stage)
            response["success"] = success
            
        elif command == "start_threads":
            runs = int(cmd_data.get("runs", 1))
            difficulty = cmd_data.get("difficulty", 40)
            try:
                shared_vars.threads_runs.value = runs
                if str(difficulty) != "latest":
                    shared_vars.threads_difficulty.value = int(difficulty)
            except Exception:
                pass
            success = process_handler.start_thread_luxcavation(shared_vars, runs, difficulty)
            response["success"] = success
            
        elif command == "start_chain":
            if "threads_runs" in cmd_data: ui_context['chain_threads_entry'].value = str(cmd_data["threads_runs"])
            if "exp_runs" in cmd_data: ui_context['chain_exp_entry'].value = str(cmd_data["exp_runs"])
            if "mirror_runs" in cmd_data: ui_context['chain_mirror_entry'].value = str(cmd_data["mirror_runs"])
            
            chain_automation.start_chain_automation(ui_context, shared_vars)
            response["message"] = "Chain started"

        elif command == "call_function":
            function_string = cmd_data.get("function_string")
            if function_string:
                process_handler.call_function(function_string, BASE_PATH, sys.executable)
                response["message"] = f"Function '{function_string}' called."
            else:
                response["status"] = "error"
                response["message"] = "No function_string provided."

        elif command == "terminate_functions":
            process_handler.terminate_functions()
            response["message"] = "Function processes terminated."

        elif command == "start_battle":
            process_handler.start_battle(BASE_PATH, sys.executable)
            response["message"] = "Battle process started"

        elif command == "check_update":
            try:
                upd = updater.Updater("Bonkier", "WorkerBee")
                available, version, url = upd.check_for_updates()
                response["update_available"] = available
                response["latest_version"] = version
                response["download_url"] = url
                response["current_version"] = upd.get_current_version()
            except Exception as e:
                response["status"] = "error"
                response["message"] = f"Update check failed: {str(e)}"

        elif command == "perform_update":
            def run_update_thread():
                try:
                    upd = updater.Updater("Bonkier", "WorkerBee")
                    success, msg = upd.perform_update(create_backup=True, auto_restart=False)
                    if success:
                        logger.info("Update successful. Exiting process for restart by controller.")
                        time.sleep(1)
                        os._exit(0)
                except Exception as e:
                    logger.error(f"Update failed: {e}")
            
            threading.Thread(target=run_update_thread, daemon=True).start()
            response["message"] = "Update sequence initiated."

        elif command == "start_battlepass":
            success = process_handler.start_battlepass_collection()
            response["success"] = success

        elif command == "start_extractor":
            success = process_handler.start_extraction()
            response["success"] = success

        elif command == "launch_game":
            success = process_handler.start_game_launcher()
            response["success"] = success

        elif command == "stop":
            if chain_automation.chain_running:
                chain_automation.stop_chain_automation(ui_context)
            process_handler.cleanup_processes()
            response["message"] = "Processes stopping"
            
        elif command == "update_setting":
            key = cmd_data.get("key")
            value = cmd_data.get("value")
            
            if hasattr(shared_vars, key):
                var = getattr(shared_vars, key)
                target_type = type(var.value)
                try:
                    var.value = target_type(value)
                except ValueError:
                    pass
                
                if "Settings" not in config: config["Settings"] = {}
                config["Settings"][key] = value
                save_json_data(os.path.join(BASE_PATH, "config", "gui_config.json"), config)
                
                if key == "game_monitor":
                    common.set_game_monitor(int(value))
                    
                response["message"] = f"Setting {key} updated"

        elif command == "get_status":
            running = process_handler.get_running_process_name()
            if chain_automation.chain_running:
                running = f"Chain: {running if running else 'Waiting'}"
            response["running_process"] = running if running else "Idle"
            
        elif command == "get_logs":
            logs = []
            while not log_queue.empty():
                try:
                    logs.append(log_queue.get_nowait())
                except queue.Empty:
                    break
            response["logs"] = logs

        else:
            response["status"] = "error"
            response["message"] = "Unknown command"
            
    except Exception as e:
        response["status"] = "error"
        response["message"] = str(e)
        logger.error(f"Command error: {e}\n{traceback.format_exc()}")
        
    return response

def run_server():
    load_initial_settings()

    start_callbacks = {
        'start_mirror': lambda runs=1: handle_command({"command": "start_mirror", "runs": runs}),
        'start_exp': lambda: handle_command({"command": "start_exp"}),
        'start_threads': lambda: handle_command({"command": "start_threads"}),
        'start_chain': lambda: handle_command({"command": "start_chain"})
    }
    scheduler = scheduler_handler.SchedulerHandler(BASE_PATH, shared_vars, start_callbacks)

    def background_checks():
        while True:
            try:
                if process_handler.process and not process_handler.process.is_alive(): process_handler.process = None
                if process_handler.exp_process and not process_handler.exp_process.is_alive(): process_handler.exp_process = None
                if process_handler.threads_process and not process_handler.threads_process.is_alive(): process_handler.threads_process = None
                if process_handler.battlepass_process and not process_handler.battlepass_process.is_alive(): process_handler.battlepass_process = None
                if process_handler.extractor_process and not process_handler.extractor_process.is_alive(): process_handler.extractor_process = None
                if process_handler.game_launcher_process and not process_handler.game_launcher_process.is_alive(): process_handler.game_launcher_process = None
                if process_handler.battle_process and process_handler.battle_process.poll() is not None: process_handler.battle_process = None
                chain_automation.check_chain_status(None, ui_context, shared_vars)
                scheduler.check_scheduler()
            except Exception: pass
            time.sleep(1)

    threading.Thread(target=background_checks, daemon=True).start()

    def toggle_mirror():
        if process_handler.process and process_handler.process.is_alive(): handle_command({"command": "stop"})
        else: handle_command({"command": "start_mirror"})

    callbacks = {
        'toggle_mirror': toggle_mirror,
        'stop_all': lambda: handle_command({"command": "stop"}),
        'toggle_exp': lambda: handle_command({"command": "start_exp"}), 
        'toggle_threads': lambda: handle_command({"command": "start_threads"}),
        'toggle_chain': lambda: handle_command({"command": "start_chain"}),
    }
    
    keyboard_handler = KeyboardHandler(callbacks, config)
    keyboard_handler.start()
    
    logger.info(f"WorkerBee Headless Bridge listening on {HOST}:{PORT}")
    
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        
        while True:
            try:
                conn, addr = s.accept()
                with conn:
                    buffer = b""
                    while True:
                        data = conn.recv(4096)
                        if not data: break
                        buffer += data
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.strip()
                            if not line: continue
                            try:
                                cmd_str = line.decode('utf-8')
                                cmd_data = json.loads(cmd_str)
                                resp = handle_command(cmd_data)
                                conn.sendall((json.dumps(resp) + "\n").encode('utf-8'))
                            except Exception as e:
                                logger.error(f"Command processing error: {e}")
            except Exception as e:
                logger.error(f"Server accept error: {e}")
                time.sleep(1)

if __name__ == "__main__":
    multiprocessing.freeze_support()
    run_server()
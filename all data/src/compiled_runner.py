import sys
import ctypes
import logging
import os
import threading
import json
import time
import subprocess
import numpy as np
from PIL import ImageGrab, Image
import mirror
import mirror_1366
import common

_CAPTURE_HANG_LIMIT = 30
_RUN_TIME_LIMIT = 5400

def _run_watchdog(main_thread_id, run_start, stop_event):
    config_dir = os.path.join(get_base_path(), "config")
    screenshot_paths = [
        os.path.join(config_dir, "macro_state_0.png"),
        os.path.join(config_dir, "macro_state_1.png"),
    ]
    SCREENSHOT_INTERVAL = 60
    STUCK_THRESHOLD = 5.0
    last_screenshot = 0
    screenshot_index = 0

    while not stop_event.wait(5):
        now = time.time()

        last_capture = common._capture_heartbeat.get(main_thread_id, run_start)
        capture_elapsed = now - last_capture
        if capture_elapsed > _CAPTURE_HANG_LIMIT:
            logger.warning(f"Run watchdog: capture_screen hung for {capture_elapsed:.0f}s, resetting sct")
            common.reset_sct(main_thread_id)

        run_elapsed = now - run_start
        if run_elapsed > _RUN_TIME_LIMIT:
            logger.warning(f"Run watchdog: run exceeded {_RUN_TIME_LIMIT//60} minutes, injecting TimeoutError to skip run")
            ctypes.pythonapi.PyThreadState_SetAsyncExc(
                ctypes.c_long(main_thread_id),
                ctypes.py_object(TimeoutError)
            )
            break

        if now - last_screenshot >= SCREENSHOT_INTERVAL:
            try:
                current_path = screenshot_paths[screenshot_index % 2]
                prev_path = screenshot_paths[(screenshot_index - 1) % 2]
                img = ImageGrab.grab()
                img.save(current_path)
                if screenshot_index > 0 and os.path.exists(prev_path):
                    prev_img = Image.open(prev_path)
                    curr_arr = np.array(img)
                    prev_arr = np.array(prev_img)
                    try:
                        if curr_arr.shape == prev_arr.shape:
                            diff = np.mean(np.abs(curr_arr.astype(np.int32) - prev_arr.astype(np.int32)))
                            if diff < STUCK_THRESHOLD:
                                logger.warning(f"Run watchdog: screen unchanged for {SCREENSHOT_INTERVAL}s (diff={diff:.2f}), injecting TimeoutError")
                                ctypes.pythonapi.PyThreadState_SetAsyncExc(
                                    ctypes.c_long(main_thread_id),
                                    ctypes.py_object(TimeoutError)
                                )
                                break
                    finally:
                        del curr_arr, prev_arr
                        prev_img.close()
                screenshot_index += 1
                last_screenshot = now
            except Exception as e:
                logger.warning(f"Run watchdog: screenshot check failed: {e}")
            finally:
                try:
                    img.close()
                    del img
                except Exception:
                    pass

logger = None

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def setup_paths_and_imports():
    BASE_PATH = get_base_path()

    src_path = os.path.join(BASE_PATH, 'src')
    sys.path.append(src_path)
    sys.path.append(BASE_PATH)

    config_path = os.path.join(BASE_PATH, "config")
    status_json_path = os.path.join(config_path, "status_selection.json")
    
    if os.path.exists(status_json_path):
        status_path = status_json_path
    else:
        basic_logger = logging.getLogger(__name__)
        basic_logger.critical(f"Status selection file not found at: {status_json_path}")
        raise FileNotFoundError(f"Status selection file not found: {status_json_path}")

    
    try:
        import common
        from core import reconnect
        from common import error_screenshot, element_exist
        import mirror

        global logger
        logger = logging.getLogger(__name__)
        
        return BASE_PATH, status_path
    except ImportError as e:
        basic_logger = logging.getLogger(__name__)
        basic_logger.critical(f"Failed to import modules: {e}")
        raise

def load_status_list(status_path):
    try:
        with open(status_path, "r") as f:
            data = json.load(f)
            if all(key.isdigit() for key in data.keys()):
                sorted_items = sorted(data.items(), key=lambda x: int(x[0]))
                statuses = [item[1] for item in sorted_items]
            else:
                statuses = data.get("selected_statuses", [])
            return [status.strip().lower() for status in statuses if status.strip()]
    except Exception as e:
        logger.critical(f"Error reading status selection file: {e}")
        raise

class ConnectionManager:
    
    def __init__(self):
        self.connection_event = threading.Event()
        self.connection_event.set() 
    
    def start_connection_monitor(self):
        connection_thread = threading.Thread(target=self._connection_check, daemon=True)
        connection_thread.start()
    
    def _connection_check(self):
        from common import element_exist

        while True:
            try:
                if element_exist("pictures/general/connection.png", quiet_failure=True):
                    self.connection_event.clear()
                else:
                    self.connection_event.set()
            except Exception as e:
                logger.error(f"Error in connection check: {e}")
            time.sleep(2)
    
    def handle_reconnection(self):
        try:
            from core import reconnect
            from common import element_exist
            
            logger.warning(f"Server error detected")
            self.connection_event.clear()
            
            connection_listener_thread = threading.Thread(target=reconnect)
            connection_listener_thread.start()
            connection_listener_thread.join(timeout=300)
            if connection_listener_thread.is_alive():
                logger.warning("Reconnection thread did not complete within 5 minutes, continuing anyway")
            
            self.connection_event.set()
        except Exception as e:
            logger.error(f"Error in reconnection: {e}")

def sync_shared_vars(shared_vars_instance):
    import shared_vars as sv_module
    import time
    import common
    
    last_monitor = -1
    
    while True:
        try:
            sv_module.x_offset = shared_vars_instance.x_offset.value
            sv_module.y_offset = shared_vars_instance.y_offset.value
            sv_module.game_monitor = shared_vars_instance.game_monitor.value

            if sv_module.game_monitor != last_monitor:
                common.set_game_monitor(sv_module.game_monitor)
                last_monitor = sv_module.game_monitor
                
            sv_module.skip_restshop = shared_vars_instance.skip_restshop.value
            sv_module.skip_ego_check = shared_vars_instance.skip_ego_check.value
            sv_module.skip_ego_fusion = shared_vars_instance.skip_ego_fusion.value
            sv_module.skip_sinner_healing = shared_vars_instance.skip_sinner_healing.value
            sv_module.skip_ego_enhancing = shared_vars_instance.skip_ego_enhancing.value
            sv_module.skip_ego_buying = shared_vars_instance.skip_ego_buying.value
            sv_module.hard_mode = shared_vars_instance.hard_mode.value
            sv_module.retry_count = shared_vars_instance.retry_count.value
            sv_module.claim_on_defeat = shared_vars_instance.claim_on_defeat.value
            sv_module.pack_refreshes = shared_vars_instance.pack_refreshes.value
            sv_module.debug_image_matches = shared_vars_instance.debug_image_matches.value
            sv_module.convert_images_to_grayscale = shared_vars_instance.convert_images_to_grayscale.value
            sv_module.reconnection_delay = shared_vars_instance.reconnection_delay.value
            sv_module.reconnect_when_internet_reachable = shared_vars_instance.reconnect_when_internet_reachable.value
            sv_module.good_pc_mode = shared_vars_instance.good_pc_mode.value
            sv_module.click_delay = shared_vars_instance.click_delay.value
            sv_module.stop_after_current_run = shared_vars_instance.stop_after_current_run.value
            sv_module.convert_enkephalin_to_modules = shared_vars_instance.convert_enkephalin_to_modules.value
        except AttributeError:
            pass
        except Exception:
            break
        time.sleep(1)

def update_stats(win, run_data=None):
    try:
        base_path = get_base_path()
        stats_path = os.path.join(base_path, "config", "stats.json")
        
        data = {"mirror": {"runs": 0, "wins": 0, "losses": 0}, "exp": {"runs": 0}, "threads": {"runs": 0}}
        if os.path.exists(stats_path):
            with open(stats_path, 'r') as f:
                data = json.load(f)

        if "mirror" not in data: data["mirror"] = {"runs": 0, "wins": 0, "losses": 0}
        if "exp" not in data: data["exp"] = {"runs": 0}
        if "threads" not in data: data["threads"] = {"runs": 0}
        
        packs = run_data.get("packs", []) if run_data else []
        is_dnf = not win and len(packs) < 5

        data["mirror"]["runs"] += 1
        
        if is_dnf:
            if "dnf" not in data["mirror"]:
                data["mirror"]["dnf"] = 0
            data["mirror"]["dnf"] += 1
        else:
            if win: data["mirror"]["wins"] += 1
            else: data["mirror"]["losses"] += 1

        if run_data:
            if "history" not in data["mirror"]:
                data["mirror"]["history"] = []
            
            result_str = "Win" if win else "Loss"
            if is_dnf:
                result_str = "DNF"

            history_entry = {
                "timestamp": time.time(),
                "result": result_str,
                "duration": run_data.get("duration", 0),
                "floor_times": run_data.get("floor_times", {}),
                "packs": packs,
                "packs_by_floor": run_data.get("packs_by_floor", {})
            }
            
            data["mirror"]["history"].insert(0, history_entry)
            data["mirror"]["history"] = data["mirror"]["history"][:50] 
        
        with open(stats_path, 'w') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Statistics updated: Win={win}, DNF={is_dnf}")
    except Exception as e:
        logger.error(f"Failed to update stats: {e}")

def mirror_dungeon_run(num_runs, status_list_file, connection_manager, shared_vars):
    try:
        import common
        from common import element_exist, error_screenshot

        win_count = 0
        lose_count = 0

        if not status_list_file:
            logger.critical(f"Status list file is empty, cannot proceed")
            return

        status_list = (status_list_file * ((num_runs // len(status_list_file)) + 1))[:num_runs]
        unique_statuses = list(dict.fromkeys(status_list_file))
        logger.info(f"Starting Run with statuses: {unique_statuses}")

        res_w, _ = common.get_resolution()
        MirrorClass = mirror.Mirror
        logger.info(f"Resolution detected: {res_w}px - using mirror.Mirror (1366 disabled)")

        sync_thread = threading.Thread(target=sync_shared_vars, args=(shared_vars,), daemon=True)
        sync_thread.start()

        time.sleep(1.0)
        
        i = 0
        while i < num_runs:
            if hasattr(shared_vars, 'stop_after_current_run') and shared_vars.stop_after_current_run.value:
                logger.info("Stop after current run signal detected. Stopping sequence.")
                break

            logger.info(f"Run {i + 1}")

            try:
                common.reset_sct()
            except Exception as e:
                logger.warning(f"Failed to reset sct between runs: {e}")
            
            _stop_watchdog = threading.Event()
            _wt = threading.Thread(
                target=_run_watchdog,
                args=(threading.current_thread().ident, time.time(), _stop_watchdog),
                daemon=True
            )
            _wt.start()
            try:
                run_complete = 0
                win_flag = 0
                MD = MirrorClass(status_list[i])
                logger.info(f"Current Team: " + status_list[i])
                MD.setup_mirror()

                while run_complete != 1:
                    if connection_manager.connection_event.is_set():
                        win_flag, run_complete, run_stats = MD.mirror_loop()
                    else:
                        connection_manager.connection_event.wait(timeout=30)

                    if element_exist("pictures/general/server_error.png"):
                        connection_manager.handle_reconnection()

                if win_flag == 1:
                    win_count += 1
                    logger.info(f"Run {i + 1} completed with a win")
                    update_stats(True, run_stats)
                else:
                    lose_count += 1
                    logger.info(f"Run {i + 1} completed with a loss")
                    update_stats(False, run_stats)
                i += 1

            except Exception as e:
                logger.exception(f"Error in run {i + 1}: {e}")
                error_screenshot()
                i += 1
            finally:
                _stop_watchdog.set()
        
        logger.info(f'Completed all runs. Won: {win_count}, Lost: {lose_count}')
        
    except Exception as e:
        logger.exception(f"Critical error in mirror_dungeon_run: {e}")
        from common import error_screenshot
        error_screenshot()

def main(num_runs, shared_vars):
    try:
        base_path, status_path = setup_paths_and_imports()

        logger.info(f"compiled_runner.py main function started with {num_runs} runs")

        try:
            import luxcavation_functions as _lux
            _lux._get_ocr()
        except Exception as _e:
            logger.warning(f"OCR preload failed: {_e}")
        
        status_list_file = load_status_list(status_path)
        
        connection_manager = ConnectionManager()
        connection_manager.start_connection_monitor()
        
        mirror_dungeon_run(num_runs, status_list_file, connection_manager, shared_vars)
        logger.info(f"mirror_dungeon_run completed successfully")
        
    except Exception as e:
        logger.critical(f"Unhandled exception in compiled_runner main: {e}")
        try:
            from common import error_screenshot
            error_screenshot()
        except Exception as screenshot_err:
            logger.warning(f"Failed to take error screenshot: {screenshot_err}")
        return

if __name__ == "__main__":
    """Legacy support for command line execution"""
    
    try:
        base_path, status_path = setup_paths_and_imports()
        
        logger.info(f"compiled_runner.py main execution started")

        if len(sys.argv) > 1:
            try:
                count = int(sys.argv[1])
                logger.info(f"Run count from arguments: {count}")
            except ValueError:
                count = 1
                logger.warning(f"Invalid run count argument: {sys.argv[1]}, using default 1")
        else:
            count = 1
            logger.info(f"No run count specified, using default 1")
        
        class FakeSharedVars:
            def __init__(self):
                x_offset = 0
                y_offset = 0
                if len(sys.argv) > 2:
                    try:
                        x_offset = int(sys.argv[2])
                    except ValueError:
                        pass
                if len(sys.argv) > 3:
                    try:
                        y_offset = int(sys.argv[3])
                    except ValueError:
                        pass

                from multiprocessing import Value
                self.x_offset = Value('i', x_offset)
                self.y_offset = Value('i', y_offset)
                self.debug_mode = Value('b', False)
                self.click_delay = Value('f', 0.5)
        
        fake_shared_vars = FakeSharedVars()
        logger.info(f"Created fake shared vars for command line execution")
        
        status_list_file = load_status_list(status_path)
        
        connection_manager = ConnectionManager()
        connection_manager.start_connection_monitor()
        
        mirror_dungeon_run(count, status_list_file, connection_manager, fake_shared_vars)
        logger.info(f"mirror_dungeon_run completed successfully")
        
    except Exception as e:
        logger.critical(f"Unhandled exception in compiled_runner main: {e}")
        try:
            from common import error_screenshot
            error_screenshot()
        except Exception as screenshot_err:
            logger.warning(f"Failed to take error screenshot: {screenshot_err}")
        sys.exit(1)
    
    logger.info(f"compiled_runner.py completed successfully")

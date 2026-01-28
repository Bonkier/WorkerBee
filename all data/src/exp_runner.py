"""
Exp Runner Script - Runs Luxcavation Exp automation
This script is called by the GUI and runs as a separate process
"""
import sys
import os
import time
import logging
import signal
import threading

def get_base_path():
    """Get the base directory path"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

BASE_PATH = get_base_path()
sys.path.append(BASE_PATH)
sys.path.append(os.path.join(BASE_PATH, 'src'))

import luxcavation_functions
import common

logger = logging.getLogger(__name__)

class ConnectionManager:
    """Manages connection checking and reconnection"""
    
    def __init__(self):
        """Initialize connection manager"""
        self.connection_event = threading.Event()
        self.connection_event.set()
    
    def start_connection_monitor(self):
        """Start the connection monitoring thread"""
        connection_thread = threading.Thread(target=self._connection_check, daemon=True)
        connection_thread.start()
    
    def _connection_check(self):
        """Monitor connection status"""
        from common import element_exist
        
        while True:
            try:
                if element_exist("pictures/general/connection.png", quiet_failure=True):
                    self.connection_event.clear()
                else:
                    self.connection_event.set()
            except Exception as e:
                logger.error(f"Error in connection check: {e}")
    
    def handle_reconnection(self):
        """Handle reconnection when needed"""
        try:
            from core import reconnect
            from common import element_exist
            
            self.connection_event.clear()
            
            connection_listener_thread = threading.Thread(target=reconnect)
            connection_listener_thread.start()
            connection_listener_thread.join()
            
            self.connection_event.set()
        except Exception as e:
            logger.error(f"Error in reconnection: {e}")

def sync_shared_vars(shared_vars_instance):
    """Synchronize multiprocessing.Value objects with local shared_vars module"""
    import shared_vars as sv_module
    
    if shared_vars_instance is None:
        return

    while True:
        try:
            if hasattr(shared_vars_instance, 'x_offset'): sv_module.x_offset = shared_vars_instance.x_offset.value
            if hasattr(shared_vars_instance, 'y_offset'): sv_module.y_offset = shared_vars_instance.y_offset.value
            if hasattr(shared_vars_instance, 'game_monitor'): sv_module.game_monitor = shared_vars_instance.game_monitor.value
            if hasattr(shared_vars_instance, 'click_delay'): sv_module.click_delay = shared_vars_instance.click_delay.value
            if hasattr(shared_vars_instance, 'good_pc_mode'): sv_module.good_pc_mode = shared_vars_instance.good_pc_mode.value
            if hasattr(shared_vars_instance, 'debug_image_matches'): sv_module.debug_image_matches = shared_vars_instance.debug_image_matches.value
            if hasattr(shared_vars_instance, 'convert_images_to_grayscale'): sv_module.convert_images_to_grayscale = shared_vars_instance.convert_images_to_grayscale.value
            if hasattr(shared_vars_instance, 'reconnection_delay'): sv_module.reconnection_delay = shared_vars_instance.reconnection_delay.value
            if hasattr(shared_vars_instance, 'reconnect_when_internet_reachable'): sv_module.reconnect_when_internet_reachable = shared_vars_instance.reconnect_when_internet_reachable.value
            if hasattr(shared_vars_instance, 'stop_after_current_run'): sv_module.stop_after_current_run = shared_vars_instance.stop_after_current_run.value
            
        except AttributeError:
            pass 
        except Exception as e:
            logger.error(f"Error in sync_shared_vars: {e}")
        time.sleep(1)

def signal_handler(sig, frame):
    """Handle termination signals"""
    logger.warning(f"Termination signal received, shutting down...")
    sys.exit(0)

def main(runs, stage, shared_vars=None):
    """Main function for exp runner"""
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
   
    try:
        if shared_vars:
            sync_thread = threading.Thread(target=sync_shared_vars, args=(shared_vars,), daemon=True)
            sync_thread.start()

        stage_arg = stage

        if stage_arg == "latest":
            stage = "latest"
        else:
            stage = int(stage_arg)

        connection_manager = ConnectionManager()
        connection_manager.start_connection_monitor()
       
        luxcavation_functions.pre_exp_setup(stage, SelectTeam=True, config_type="exp_team_selection")
        runs = runs - 1
        for i in range(runs):
            
            if shared_vars and hasattr(shared_vars, 'stop_after_current_run') and shared_vars.stop_after_current_run.value:
                logger.info("Stop after current run signal detected. Stopping sequence.")
                break
           
            try:
                time.sleep(1)
                while True:
                    if connection_manager.connection_event.is_set():
                        luxcavation_functions.pre_exp_setup(stage, config_type="exp_team_selection")
                        break
                    else:
                        connection_manager.connection_event.wait()

                    try:
                        from common import element_exist
                        if element_exist("pictures/general/server_error.png"):
                            connection_manager.handle_reconnection()
                    except ImportError:
                        pass
                    except Exception as e:
                        logger.error(f"Error checking for server error: {e}")
                        
            except Exception as e:
                logger.error(f"Error during Exp run {i+1}: {e}")
           
            time.sleep(2)
       
        
    except Exception as e:
        logger.critical(f"Critical error in Exp runner: {e}")
        return 1
   
    return 0

if __name__ == "__main__":
    try:
        if len(sys.argv) >= 3:
            runs = int(sys.argv[1])
            stage = sys.argv[2]
        else:
            logger.error("Usage: exp_runner.py <runs> <stage>")
            sys.exit(1)
            
        sys.exit(main(runs, stage))
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        logger.critical(f"Critical error in exp_runner main: {e}")
        sys.exit(1)

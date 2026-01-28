import multiprocessing
import subprocess
import os
import signal
import logging
import time
from src import compiled_runner, exp_runner, threads_runner, battlepass_collector, extractor

logger = logging.getLogger("gui_launcher")

process = None
exp_process = None
threads_process = None
battle_process = None
battlepass_process = None
extractor_process = None
function_process_list = []
game_launcher_process = None

def is_any_process_running():
    global process, exp_process, threads_process, game_launcher_process, battlepass_process, extractor_process
    return (process is not None and process.is_alive()) or \
           (exp_process is not None and exp_process.is_alive()) or \
           (threads_process is not None and threads_process.is_alive()) or \
           (game_launcher_process is not None and game_launcher_process.is_alive()) or \
           (battlepass_process is not None and battlepass_process.is_alive()) or \
           (extractor_process is not None and extractor_process.is_alive())

def get_running_process_name():
    if process is not None and process.is_alive():
        return "Mirror Dungeon"
    if exp_process is not None and exp_process.is_alive():
        return "Exp"
    if threads_process is not None and threads_process.is_alive():
        return "Threads"
    if game_launcher_process is not None and game_launcher_process.is_alive():
        return "Game Launcher"
    if battlepass_process is not None and battlepass_process.is_alive():
        return "Battlepass Collector"
    if extractor_process is not None and extractor_process.is_alive():
        return "Extractor"
    return None

def start_mirror_dungeon(shared_vars, runs=1):
    global process
    if is_any_process_running():
        logger.warning("Cannot start Mirror Dungeon: Another process is running")
        return False
        
    try:
        if multiprocessing.current_process().daemon:
            logger.error("CRITICAL: gui_launcher is running as a daemon process! Cannot spawn children.")
            return False

        process = multiprocessing.Process(target=compiled_runner.main, args=(runs, shared_vars), daemon=True)
        process.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start Mirror Dungeon: {e}")
        return False

def start_exp_luxcavation(shared_vars):
    global exp_process
    if is_any_process_running():
        logger.warning("Cannot start Exp: Another process is running")
        return False
        
    try:
        runs = shared_vars.exp_runs.value
        stage = shared_vars.exp_stage.value
        exp_process = multiprocessing.Process(target=exp_runner.main, args=(runs, stage, shared_vars), daemon=True)
        exp_process.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start Exp: {e}")
        return False

def start_thread_luxcavation(shared_vars):
    global threads_process
    if is_any_process_running():
        logger.warning("Cannot start Threads: Another process is running")
        return False
        
    try:
        runs = shared_vars.threads_runs.value
        difficulty = shared_vars.threads_difficulty.value
        threads_process = multiprocessing.Process(target=threads_runner.main, args=(runs, difficulty, shared_vars), daemon=True)
        threads_process.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start Threads: {e}")
        return False

def start_battlepass_collection():
    global battlepass_process
    if is_any_process_running():
        logger.warning("Cannot start Battlepass Collector: Another process is running")
        return False
        
    try:
        battlepass_process = multiprocessing.Process(target=battlepass_collector.main, daemon=True)
        battlepass_process.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start Battlepass Collector: {e}")
        return False

def start_extraction():
    global extractor_process
    if is_any_process_running():
        logger.warning("Cannot start Extractor: Another process is running")
        return False
        
    try:
        extractor_process = multiprocessing.Process(target=extractor.main, daemon=True)
        extractor_process.start()
        return True
    except Exception as e:
        logger.error(f"Failed to start Extractor: {e}")
        return False

def start_battle(base_path, python_cmd):
    global battle_process
    if battle_process is not None and battle_process.poll() is None:
        try:
            os.kill(battle_process.pid, signal.SIGTERM)
        except:
            pass
        battle_process = None

    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = base_path + os.pathsep + os.path.join(base_path, 'src')

        import sys
        if getattr(sys, 'frozen', False):
             battle_process = subprocess.Popen([python_cmd, "-m", "src.battler"], env=env)
        else:
             script_path = os.path.join(base_path, "src", "battler.py")
             battle_process = subprocess.Popen([python_cmd, script_path], env=env)
             
    except Exception as e:
        logger.error(f"Failed to start battle: {e}")

def call_function(function_name, base_path, python_cmd):
    global function_process_list
    try:
        env = os.environ.copy()
        env['PYTHONPATH'] = base_path + os.pathsep + os.path.join(base_path, 'src')
        
        import sys
        if getattr(sys, 'frozen', False):
            cmd = [python_cmd, "-m", "src.function_runner", function_name, "--listen-stdin"]
        else:
            script_path = os.path.join(base_path, "src", "function_runner.py")
            cmd = [python_cmd, script_path, function_name, "--listen-stdin"]
            
        proc = subprocess.Popen(cmd, env=env)
        function_process_list.append(proc)
    except Exception as e:
        logger.error(f"Failed to call function: {e}")

def terminate_functions():
    global function_process_list
    for proc in function_process_list[:]:
        if proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=1.0)
                except subprocess.TimeoutExpired:
                    proc.kill()
            except:
                pass
    function_process_list.clear()

def cleanup_processes():
    global process, exp_process, threads_process, battle_process, function_process_list, game_launcher_process, battlepass_process, extractor_process

    mp_processes = [process, exp_process, threads_process, game_launcher_process, battlepass_process, extractor_process]
    
    for p in mp_processes:
        if p and p.is_alive():
            try:
                p.terminate()
            except Exception as e:
                logger.error(f"Error terminating process: {e}")

    for p in mp_processes:
        if p and p.is_alive():
            try:
                p.join(timeout=1.0)
                if p.is_alive():
                    logger.warning(f"Process {p.name if hasattr(p, 'name') else 'Unknown'} did not terminate gracefully, forcing kill...")
                    p.kill()
                    p.join(timeout=0.1)
            except Exception as e:
                logger.error(f"Error cleaning up process: {e}")
            
    if battle_process and battle_process.poll() is None:
        try:
            battle_process.terminate()
            try:
                battle_process.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                logger.warning("Battle process did not terminate gracefully, forcing kill...")
                battle_process.kill()
        except:
            pass
            
    terminate_functions()

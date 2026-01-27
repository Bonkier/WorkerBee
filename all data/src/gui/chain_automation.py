import multiprocessing
import time
import logging
import src.gui.process_handler as process_handler
from src import Game_Launcher, battlepass_collector, extractor

logger = logging.getLogger("gui_launcher")

chain_running = False
chain_queue = []
current_chain_step = 0
battlepass_process = None
battlepass_completed = False

def start_chain_automation(ui_context, shared_vars):
    global chain_running, chain_queue, current_chain_step, battlepass_completed
    
    if chain_running:
        stop_chain_automation(ui_context)
        return

    if process_handler.is_any_process_running():
        logger.warning("Cannot start Chain: Another process is running")
        return

    try:
        threads_runs = int(ui_context['chain_threads_entry'].get())
        exp_runs = int(ui_context['chain_exp_entry'].get())
        mirror_runs = int(ui_context['chain_mirror_entry'].get())
        launch_game = ui_context['launch_game_var'].get()
    except (ValueError, KeyError):
        logger.error("Invalid chain configuration")
        return

    chain_queue = []
    if launch_game:
        chain_queue.append(("GameLauncher", 1))
    if threads_runs > 0:
        chain_queue.append(("Threads", threads_runs))
    if exp_runs > 0:
        chain_queue.append(("Exp", exp_runs))
    if mirror_runs > 0:
        chain_queue.append(("Mirror", mirror_runs))
        
    if not chain_queue and not ui_context['collect_rewards_var'].get():
        logger.warning("Chain queue empty")
        return

    chain_running = True
    current_chain_step = 0
    battlepass_completed = False
    
    if 'chain_start_button' in ui_context:
        ui_context['chain_start_button'].configure(text="Stop Chain")
    
    if 'chain_status_label' in ui_context:
        ui_context['chain_status_label'].configure(text="Chain Status: Starting...")
        
    run_next_chain_step(ui_context, shared_vars)

def stop_chain_automation(ui_context):
    global chain_running, battlepass_process
    
    chain_running = False
    process_handler.cleanup_processes()
    
    if battlepass_process and battlepass_process.is_alive():
        battlepass_process.terminate()
        battlepass_process.join(timeout=1.0)
        if battlepass_process.is_alive():
            battlepass_process.kill()
        battlepass_process = None
        
    if ui_context and 'chain_start_button' in ui_context:
        try:
            ui_context['chain_start_button'].after(0, lambda: ui_context['chain_start_button'].configure(text="Start Chain"))
        except:
            pass
    if ui_context and 'chain_status_label' in ui_context:
        try:
            ui_context['chain_status_label'].after(0, lambda: ui_context['chain_status_label'].configure(text="Chain Status: Stopped"))
        except:
            pass

def run_next_chain_step(ui_context, shared_vars):
    global current_chain_step, chain_running
    
    if not chain_running:
        return

    if current_chain_step >= len(chain_queue):
        # Chain automations done, check for rewards
        if ui_context['collect_rewards_var'].get():
            start_reward_collection(ui_context)
        else:
            finish_chain(ui_context)
        return

    automation_type, runs = chain_queue[current_chain_step]
    
    if 'chain_status_label' in ui_context:
        ui_context['chain_status_label'].configure(text=f"Chain Status: Running {automation_type} ({runs})")

    success = False
    if automation_type == "GameLauncher":
        process_handler.game_launcher_process = multiprocessing.Process(target=Game_Launcher.launch_limbus, daemon=True)
        process_handler.game_launcher_process.start()
        success = True
    elif automation_type == "Threads":
        shared_vars.threads_runs.value = runs
        success = process_handler.start_thread_luxcavation(shared_vars)
    elif automation_type == "Exp":
        shared_vars.exp_runs.value = runs
        success = process_handler.start_exp_luxcavation(shared_vars)
    elif automation_type == "Mirror":
        success = process_handler.start_mirror_dungeon(shared_vars, runs)
        
    if success:
        current_chain_step += 1
    else:
        logger.error(f"Failed to start chain step: {automation_type}")
        stop_chain_automation(ui_context)

def start_reward_collection(ui_context):
    global battlepass_process
    if 'chain_status_label' in ui_context:
        ui_context['chain_status_label'].configure(text="Chain Status: Collecting Rewards")
        
    battlepass_process = multiprocessing.Process(target=battlepass_collector.main, daemon=True)
    battlepass_process.start()

def check_chain_status(root, ui_context, shared_vars):
    """Called periodically by UI updater to monitor chain progress"""
    global chain_running, battlepass_process
    
    if not chain_running:
        return

    # Check active process
    if process_handler.is_any_process_running():
        # Still running
        return
        
    # Check if we were running rewards
    if battlepass_process:
        if not battlepass_process.is_alive():
            battlepass_process = None
            finish_chain(ui_context)
        return

    # If we are here, a regular step finished.
    run_next_chain_step(ui_context, shared_vars)

def finish_chain(ui_context):
    global chain_running
    chain_running = False
    if 'chain_start_button' in ui_context:
        ui_context['chain_start_button'].configure(text="Start Chain")
    if 'chain_status_label' in ui_context:
        ui_context['chain_status_label'].configure(text="Chain Status: Completed")
    logger.info("Chain automation completed")

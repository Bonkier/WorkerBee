import logging
import common

logger = logging.getLogger("gui_launcher")

def load_preferences(config, shared_vars):
    """Load settings from config into shared_vars"""
    settings = config.get("Settings", {})

    if "game_monitor" in settings: shared_vars.game_monitor.value = int(settings["game_monitor"])
    if "exp_runs" in settings: shared_vars.exp_runs.value = int(settings["exp_runs"])
    if "exp_stage" in settings: shared_vars.exp_stage.value = int(settings["exp_stage"])
    if "threads_runs" in settings: shared_vars.threads_runs.value = int(settings["threads_runs"])
    if "threads_difficulty" in settings: shared_vars.threads_difficulty.value = int(settings["threads_difficulty"])

    if "skip_restshop" in settings: shared_vars.skip_restshop.value = bool(settings["skip_restshop"])
    if "skip_ego_check" in settings: shared_vars.skip_ego_check.value = bool(settings["skip_ego_check"])
    if "skip_ego_fusion" in settings: shared_vars.skip_ego_fusion.value = bool(settings["skip_ego_fusion"])
    if "skip_sinner_healing" in settings: shared_vars.skip_sinner_healing.value = bool(settings["skip_sinner_healing"])
    if "skip_ego_enhancing" in settings: shared_vars.skip_ego_enhancing.value = bool(settings["skip_ego_enhancing"])
    if "skip_ego_buying" in settings: shared_vars.skip_ego_buying.value = bool(settings["skip_ego_buying"])
    if "prioritize_list_over_status" in settings: shared_vars.prioritize_list_over_status.value = bool(settings["prioritize_list_over_status"])
    if "claim_on_defeat" in settings: shared_vars.claim_on_defeat.value = bool(settings["claim_on_defeat"])

    if "debug_image_matches" in settings: shared_vars.debug_image_matches.value = bool(settings["debug_image_matches"])
    if "hard_mode" in settings: shared_vars.hard_mode.value = bool(settings["hard_mode"])
    if "convert_images_to_grayscale" in settings: shared_vars.convert_images_to_grayscale.value = bool(settings["convert_images_to_grayscale"])
    if "reconnection_delay" in settings: shared_vars.reconnection_delay.value = int(settings["reconnection_delay"])
    if "reconnect_when_internet_reachable" in settings: shared_vars.reconnect_when_internet_reachable.value = bool(settings["reconnect_when_internet_reachable"])
    if "good_pc_mode" in settings: shared_vars.good_pc_mode.value = bool(settings["good_pc_mode"])
    if "click_delay" in settings: shared_vars.click_delay.value = float(settings["click_delay"])
    if "retry_count" in settings: shared_vars.retry_count.value = int(settings["retry_count"])
    if "pack_refreshes" in settings: shared_vars.pack_refreshes.value = int(settings["pack_refreshes"])
    if "x_offset" in settings: shared_vars.x_offset.value = int(settings["x_offset"])
    if "y_offset" in settings: shared_vars.y_offset.value = int(settings["y_offset"])

def setup_environment(shared_vars):
    """Initialize common settings from shared_vars"""
    try:
        if hasattr(shared_vars, 'game_monitor'):
            common.set_game_monitor(shared_vars.game_monitor.value)
        logger.info("Common settings initialized")
    except Exception as e:
        logger.error(f"Error initializing common settings: {e}")
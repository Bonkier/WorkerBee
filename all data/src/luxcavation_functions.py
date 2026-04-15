import sys
import os
import json
import common
import core
import logging
import keyboard
import time
import threading
import signal
import mirror
import mirror_utils
import shared_vars

_ocr_reader = None

def _get_ocr():
    global _ocr_reader
    if _ocr_reader is None:
        logger = logging.getLogger(__name__)
        logger.info("Loading EasyOCR model (first use, may take a moment)...")
        try:
            import easyocr as _easyocr
            _ocr_reader = _easyocr.Reader(['en'], gpu=False, verbose=False)
            logger.info("EasyOCR model loaded")
        except Exception as e:
            import traceback
            logger.error(f"Failed to load OCR: {e}\n{traceback.format_exc()}")
    return _ocr_reader

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        folder_path = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(folder_path) == 'src':
            return os.path.dirname(folder_path)
        return folder_path

BASE_PATH = get_base_path()

logger = logging.getLogger(__name__)

def get_mirror_instance(config_type="status_selection"):
    status = "poise" 
    
    try:
        data = shared_vars.ConfigCache.get_config(config_type)
        if data:
            if all(key.isdigit() for key in data.keys()):
                sorted_items = sorted(data.items(), key=lambda x: int(x[0]))
                statuses = [item[1] for item in sorted_items]
            else:
                statuses = data.get("selected_statuses", [])
            if statuses:
                status = statuses[0].strip().lower()
        
        mirror_instance = mirror.Mirror(status)
        logger.info(f"Initialized Mirror with {config_type} status: {status}")
        return mirror_instance
    except Exception as e:
        logger.error(f"Error initializing Mirror with {config_type}: {e}")
        return mirror.Mirror("poise") 

m = get_mirror_instance("status_selection")

screen_width, screen_height = common.get_resolution()
logger.debug(f"Screen dimensions: {screen_width}x{screen_height}")

def click_matching_EXP(image_path, threshold=0.8, area="center", 
                      movewidth=0, moveheight=0, move2width=0, move2height=0,
                      dragwidth=0, dragheight=0, drag2width=0, drag2height=0,
                      dragspeed=1):
    
    def verify_element_visible(image_path, threshold):
        try:
            if common.element_exist(image_path, threshold):
                time.sleep(0.5)  
                
                if common.element_exist(image_path, threshold):
                    return True
                else:
                    return False
            else:
                return False
        except Exception as e:
            logger.error(f"Exception during element verification: {e}")
            return False
    
    def try_click_element(image_path, threshold, area, attempt_name):
        try:
            found = common.match_image(image_path, threshold, area)
            
            if found and len(found) > 0:
                x, y = found[0]
                common.mouse_move_click(x, y)
                return True
            else:
                return False
        except Exception as e:
            logger.error(f"Exception during click attempt ({attempt_name}): {e}")
            return False

    if verify_element_visible(image_path, threshold):
        if try_click_element(image_path, threshold, area, "initial check"):
            return True

    try:
        common.mouse_move(movewidth, moveheight)
        common.mouse_drag(dragwidth, dragheight, dragspeed)
        time.sleep(0.5)  
        
        if verify_element_visible(image_path, threshold):
            if try_click_element(image_path, threshold, area, "first drag"):
                return True
    except Exception as e:
        logger.error(f"Exception during first drag attempt: {e}")

    try:
        common.mouse_move(move2width, move2height)
        common.mouse_drag(drag2width, drag2height, dragspeed)
        time.sleep(0.5)  
        
        if verify_element_visible(image_path, threshold):
            if try_click_element(image_path, threshold, area, "second drag"):
                return True
    except Exception as e:
        logger.error(f"Exception during second drag attempt: {e}")
    
    logger.warning(f"All attempts to find {os.path.basename(image_path)} failed")
    return False

def click_continue():
    start_time = time.time()

    continue_clicked = False

    while time.time() - start_time < 60:  
        
        if common.click_matching("pictures/CustomAdded1080p/luxcavation/thread/confirminverted.png", recursive=False):
            logger.info(f"Confirmation dialog found, clicked it")
            common.mouse_move(*common.scale_coordinates_1080p(200, 200))
            logger.info(f"clicked comfirm")
            continue_clicked = True
        elif common.click_matching("pictures/general/confirm_w.png", recursive=False):
            pass
            time.sleep(0.5)
        elif common.element_exist("pictures/CustomAdded1080p/battle/in_battle_area.png"):
            logger.info(f"tried to click continue but battle ongoing")
            common.error_screenshot()
            core.battle()
        if not common.element_exist("pictures/CustomAdded1080p/luxcavation/thread/confirminverted.png") and continue_clicked:
            break
        time.sleep(0.5)
            
    if time.time() - start_time >= 60:
        return

def squad_select_lux(mirror_instance, SelectTeam=False):
    
    if SelectTeam:
        status = mirror_utils.squad_choice(mirror_instance.status)
        if status is None:
            status = "poise"
        else:
            if not common.click_matching(status, recursive=False):
                found = common.match_image("pictures/CustomAdded1080p/general/squads/squad_select.png")
                x,y = found[0]
                offset_x, offset_y = common.scale_offset_1440p(90, 90)
                common.mouse_move(x + offset_x, y + offset_y)
                for i in range(30):
                    common.mouse_scroll(1000)
                common.sleep(1)
                for _ in range(4):
                    if not common.element_exist(status):
                        for i in range(7):
                            common.mouse_scroll(-1000)
                        common.sleep(1)
                        if common.click_matching(status, recursive=False):
                            break
                        continue
                    else:
                        common.click_matching(status)
                        break
    if SelectTeam or not (common.element_exist("pictures/CustomAdded1080p/general/squads/five_squad.png") or common.element_exist("pictures/CustomAdded1080p/general/squads/full_squad.png")):
        common.click_matching("pictures/CustomAdded1080p/general/squads/clear_selection.png", mousegoto200=True)
        common.click_matching("pictures/CustomAdded1080p/general/confirm.png", recursive=False)
        for i, position in enumerate(mirror_instance.squad_order):
            x, y = position
            common.mouse_move_click(x, y)
        
    common.click_matching("pictures/CustomAdded1080p/general/squads/to_battle.png")
    
    while not common.element_exist("pictures/battle/winrate.png"):
        common.sleep(0.5)
        
    logger.info(f"Battle screen detected, entering battle")
    core.battle()
    common.mouse_move(*common.scale_coordinates_1080p(200, 200))
    logger.info(f"Battle completed, checking for confirmation dialog")
    core.check_loading()
    click_continue()

def navigate_to_lux():
    if common.click_matching("pictures/CustomAdded1080p/luxcavation/luxcavation.png", recursive=False):
        return
    common.click_matching("pictures/general/window.png")
    common.sleep(0.5)
    common.click_matching("pictures/general/drive.png")
    common.sleep(0.5)
    common.click_matching("pictures/CustomAdded1080p/luxcavation/luxcavation.png", recursive=False, quiet_failure=True)

def pre_exp_setup(Stage, SelectTeam=False, config_type="exp_team_selection"):
    logger.info(f"Starting EXP farming setup for stage: {Stage} with config: {config_type}")
    core.refill_enkephalin()
    navigate_to_exp(Stage, SelectTeam, config_type)

def pre_threads_setup(Difficulty, SelectTeam=False, config_type="threads_team_selection"):
    logger.info(f"Starting Thread farming setup for difficulty: {Difficulty} with config: {config_type}")
    core.refill_enkephalin()
    navigate_to_threads(Difficulty, SelectTeam, config_type)

def navigate_to_exp(Stage, SelectTeam=False, config_type="exp_team_selection"):
    logger.info(f"Navigating to EXP stage: {Stage} with config: {config_type}")
    
    already_on_lux_screen = common.element_exist("pictures/CustomAdded1080p/luxcavation/luxcavation_brown.png")

    if not already_on_lux_screen:
        logger.debug(f"Not on Luxcavation screen, navigating there first")
        navigate_to_lux()

    logger.debug("Clicking EXP tab")
    common.click_matching("pictures/CustomAdded1080p/luxcavation/exp/exp.png", 0.8)
    time.sleep(1.0)
    
    if Stage == "latest":
        logger.debug("Clicking latest stage using coordinates")
        lux_coords = shared_vars.ScaledCoordinates.get_scaled_coords("luxcavation_coords")
        latest_x, latest_y = lux_coords["latest_stage"]
        common.mouse_move_click(latest_x, latest_y)
        success = True
    else:
        enter_image = "pictures/CustomAdded1080p/luxcavation/exp/exp_enter.png"
        target_label = f"{int(Stage):02d}"

        lux_coords = shared_vars.ScaledCoordinates.get_scaled_coords("luxcavation_coords")
        drag_start_x, drag_start_y = lux_coords["exp_drag_start"]
        drag_end_x, drag_end_y = lux_coords["exp_drag_end"]

        _ocr = _get_ocr()

        success = False
        for attempt in range(8):
            screenshot = common.capture_screen()
            sh, sw = screenshot.shape[:2]
            enter_matches = common.match_image(enter_image, 0.85)

            if not enter_matches:
                logger.debug(f"No exp_enter buttons visible on screen (attempt {attempt+1})")
            elif not _ocr:
                logger.warning("OCR unavailable, cannot read stage labels")
            if enter_matches and _ocr:
                stage_y1 = int(0.268 * sh)
                stage_y2 = int(0.398 * sh)
                ocr_hw = int(0.094 * sw)
                for ex, ey in enter_matches:
                    cx1 = max(0, ex - ocr_hw)
                    cx2 = min(sw, ex + ocr_hw)
                    crop = screenshot[stage_y1:stage_y2, cx1:cx2]
                    texts = _ocr.readtext(crop, detail=0)
                    combined = " ".join(texts)
                    logger.debug(f"OCR at x={ex}: '{combined}' (looking for '{target_label}')")
                    if target_label in combined:
                        logger.info(f"Stage {Stage} (label '{target_label}') found at x={ex}, clicking Enter at ({ex},{ey})")
                        common.mouse_move_click(ex, ey)
                        success = True
                        break

            if success:
                break
            logger.warning(f"Stage {Stage} not found on screen (attempt {attempt+1}), scrolling")
            if not common.element_exist("pictures/CustomAdded1080p/luxcavation/luxcavation_brown.png"):
                logger.warning("No longer on Luxcavation screen, aborting scroll")
                break
            step = int((drag_end_x - drag_start_x) * 0.25)
            scroll_x = drag_start_x + step
            common.mouse_move(drag_start_x, drag_start_y)
            common.mouse_drag(scroll_x, drag_end_y, 0.3)
            time.sleep(0.5)
    
    if not success:
        logger.warning(f"Failed to click Stage {Stage}")
        if common.element_exist("pictures/battle/winrate.png"):
            core.battle()
            click_continue()
            return

        common.click_matching("pictures/CustomAdded1080p/general/goback.png")
        navigate_to_exp(Stage, SelectTeam, config_type)
        return
    
    logger.debug(f"Click successful, waiting for UI to settle...")
    time.sleep(0.5) 
    
    if common.element_exist("pictures/CustomAdded1080p/general/squads/squad_select.png"):
        logger.info(f"Squad select screen detected")
        mirror_instance = get_mirror_instance(config_type)
        squad_select_lux(mirror_instance, SelectTeam)
        common.key_press(Key="esc", presses=2)
    else:
        logger.warning(f"Squad select screen not detected, retrying")
        common.key_press(Key="esc", presses=2)
        time.sleep(1)
        common.key_press(Key="esc", presses=2)
        navigate_to_exp(Stage, SelectTeam, config_type)
        return
    

def navigate_to_threads(Difficulty, SelectTeam=False, config_type="threads_team_selection"):
    
    if Difficulty != "latest" and Difficulty not in [20, 30, 40, 50, 60]:
        logger.error(f"Invalid thread difficulty: {Difficulty}")
        return
        
    already_on_lux_screen = common.element_exist("pictures/CustomAdded1080p/luxcavation/luxcavation_brown.png")
    
    if not already_on_lux_screen:
        logger.debug(f"Not on Luxcavation screen, navigating there first")
        navigate_to_lux()
        
    common.click_matching("pictures/CustomAdded1080p/luxcavation/thread/thread.png")
    
    if not common.element_exist("pictures/CustomAdded1080p/luxcavation/thread/enter.png"):
        logger.warning("Enter button not found")
        navigate_to_threads(Difficulty, SelectTeam, config_type)
        return

    lux_coords = shared_vars.ScaledCoordinates.get_scaled_coords("luxcavation_coords")
    thread_x, thread_y = lux_coords["thread_select"]
    common.mouse_move_click(thread_x, thread_y)
    time.sleep(0.5)
    
    if Difficulty == "latest":
        logger.info(f"clicking latest using coordinates")
        lux_coords = shared_vars.ScaledCoordinates.get_scaled_coords("luxcavation_coords")
        latest_diff_x, latest_diff_y = lux_coords["latest_difficulty"]
        common.mouse_move_click(latest_diff_x, latest_diff_y)
        success = True
    else:
        difficulty_image = f"pictures/CustomAdded1080p/luxcavation/thread/difficulty{Difficulty}.png"

        drag_x = common.scale_x_1080p(900)
        drag_start_y = common.scale_y_1080p(500)
        drag_end_y = common.scale_y_1080p(700)

        for _ in range(3):
            common.mouse_move(drag_x, drag_start_y)
            common.mouse_drag(drag_x, drag_end_y, 0.3)
        time.sleep(0.3)

        success = False
        for attempt in range(8):
            if common.click_matching(difficulty_image, threshold=0.97, area="center", mousegoto200=False, recursive=False):
                success = True
                break
            logger.warning(f"Difficulty {Difficulty} not found (attempt {attempt+1}), dragging down")
            common.mouse_move(drag_x, drag_end_y)
            common.mouse_drag(drag_x, drag_start_y, 0.3)
            time.sleep(0.3)
        
    logger.debug(f"Click successful, waiting for UI to settle...")
    time.sleep(0.5) 
        
    if common.element_exist("pictures/CustomAdded1080p/general/squads/squad_select.png"):
        logger.info(f"Squad select screen detected")
        mirror_instance = get_mirror_instance(config_type)
        squad_select_lux(mirror_instance, SelectTeam)
        common.key_press(Key="esc", presses=2)
    else:
        logger.warning(f"Squad select screen not detected, retrying")
        common.key_press(Key="esc", presses=2)
        time.sleep(1)
        common.key_press(Key="esc", presses=2)
        navigate_to_threads(Difficulty, SelectTeam, config_type)
        return

import time
import logging
import sys
import pyautogui
import common
import shared_vars

logger = logging.getLogger(__name__)

def check_loading():
    """Check for loading screens and wait until they disappear"""
    loading_images = [
        "pictures/general/loading.png",
        "pictures/general/connecting.png",
        "pictures/general/loading_icon.png"
    ]
    
    timeout = 60
    start_time = time.time()
    
    while True:
        is_loading = False
        for img in loading_images:
            if common.element_exist(img, quiet_failure=True):
                is_loading = True
                break
        
        if not is_loading:
            break
            
        if time.time() - start_time > timeout:
            logger.warning("Loading check timed out")
            break
            
        time.sleep(0.5)

def transition_loading():
    """Wait for transitions between screens"""
    common.sleep(5)

def post_run_load():
    """Wait for return to main menu after run completion"""
    while(not common.element_exist("pictures/general/module.png")):
        common.sleep(1)

def reconnect():
    """Handle server disconnections and retry connection"""
    while(common.element_exist("pictures/general/server_error.png")):
        if shared_vars.reconnect_when_internet_reachable:
            if common.check_internet_connection():
                common.click_matching("pictures/general/retry.png")
                common.mouse_move(*common.scale_coordinates_1080p(200,200))
            else:
                common.sleep(1)
        else:
            common.sleep(shared_vars.reconnection_delay)
            common.click_matching("pictures/general/retry.png")
            common.mouse_move(*common.scale_coordinates_1080p(200,200))
    if common.element_exist("pictures/general/no_op.png"):
        common.click_matching("pictures/general/close.png")
        logger.critical("COULD NOT RECONNECT TO THE SERVER. SHUTTING DOWN!")
        sys.exit(0)

def battle():
    """Main battle loop handling winrate, ego checks, and skill events"""
    logger.info("Starting battle loop")
    battle_finished = 0
    winrate_visible_start = None
    winrate_timeout = 5
    winrate_invisible_start = None
    winrate_invisible_timeout = 10
    
    while(battle_finished != 1):
        if common.element_exist("pictures/general/server_error.png"):
            logger.warning("Server error detected during battle")
            common.mouse_up()
            reconnect()
            
        # Check for defeat screens
        if (common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.6, quiet_failure=True) or 
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.6, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.jpg", threshold=0.6, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.6, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.jpg", threshold=0.6, quiet_failure=True)):
            logger.info("Defeat detected during battle")
            return # Exit battle loop, let check_run handle it

        if common.element_exist("pictures/general/loading.png") and not common.element_exist("pictures/CustomAdded1080p/battle/setting_cog.png"): #Checks for loading screen to end the while loop
            common.mouse_up()
            if common.element_exist("pictures/battle/winrate.png"):
                logger.info("false read loading")
                battle()
                return

            battle_finished = 1
            logger.info(f"Battle finished!")
            return
            
        common.mouse_move(*common.scale_coordinates_1080p(20, 1060))
        if common.element_exist("pictures/events/skip.png"): #Checks for special battle skill checks prompt then calls skill check functions
            logger.info("Skip button found, handling skill check")
            common.mouse_up()
            while(True):
                common.click_skip(1) 
                if common.element_exist("pictures/mirror/general/event.png", 0.7):
                    logger.info("Battle check event detected")
                    battle_check()
                    break
                if common.element_exist("pictures/events/skill_check.png"):
                    logger.info("Skill check event detected")
                    skill_check()
                    break

                common.click_matching("pictures/events/continue.png", recursive=False)
                    
        if common.element_exist("pictures/battle/winrate.png"):
            logger.debug("Winrate screen detected")
            winrate_invisible_start = None
            current_time = time.time()
            if winrate_visible_start is None:
                winrate_visible_start = current_time
            
            elif current_time - winrate_visible_start > winrate_timeout:
                winrate_visible_start = None
                logger.warning(f"Winrate screen stuck for {winrate_timeout} seconds")
                common.mouse_up()
                common.click_matching("pictures/battle/winrate.png", 0.9)
                ego_check()
                common.key_press("enter")
            else:
                logger.info("Clicking Winrate (P)")
                common.mouse_up()
                common.key_press("p")
                if not shared_vars.good_pc_mode:
                    common.sleep(0.5)
                ego_check()
                common.key_press("enter")
                common.mouse_down()
                time.sleep(1)
                if not common.element_exist("pictures/CustomAdded1080p/battle/battle_in_progress.png"):
                    common.mouse_move_click(*common.scale_coordinates_1080p(20, 1060))

        else:
            if common.element_exist("pictures/mirror/general/encounter_reward.png"):
                battle_finished = 1
                logger.info(f"battle ended, in mirror")
                return
            
            winrate_visible_start = None
            current_time = time.time()
            if winrate_invisible_start is None:
                winrate_invisible_start = current_time
            
            elif current_time - winrate_invisible_start > winrate_invisible_timeout:
                winrate_invisible_start = None
                logger.debug(f"No winrate for {winrate_invisible_timeout} seconds")
                common.mouse_up()
                common.mouse_move_click(*common.scale_coordinates_1080p(20, 1060))

def ego_check():
    """Check for bad clashes and use EGO skills to counter them"""
    logger.info("Starting ego check")
    if shared_vars.skip_ego_check:
        logger.info("Skipping ego check due to settings")
        return
        
    bad_clashes = []
    hopeless_matches = common.ifexist_match("pictures/battle/ego/hopeless.png",0.79, no_grayscale=True)
    if hopeless_matches:
        logger.info(f"Found {len(hopeless_matches)} hopeless clashes")
        bad_clashes += hopeless_matches
        
    struggling_matches = common.ifexist_match("pictures/battle/ego/struggling.png",0.79, no_grayscale=True)
    if struggling_matches:
        logger.info(f"Found {len(struggling_matches)} struggling clashes")
        bad_clashes += struggling_matches
    
    bad_clashes = [i for i in bad_clashes if i]
    if len(bad_clashes):
        logger.info(f"Processing {len(bad_clashes)} bad clashes for EGO usage")
        bad_clashes = [x for x in bad_clashes if x[1] > common.scale_y(1023)]
        for x,y in bad_clashes:
            offset_x, offset_y = common.scale_offset_1440p(-55, 100)
            slot_x, slot_y = x + offset_x, y + offset_y
            
            # Check if EGO is already selected (sanity icon visible near slot)
            region_size = common.uniform_scale_single(100)
            if common.ifexist_match("pictures/battle/ego/sanity.png", threshold=0.8, 
                                  x1=max(0, int(slot_x - region_size)), y1=max(0, int(slot_y - region_size)), 
                                  x2=int(slot_x + region_size), y2=int(slot_y + region_size)):
                logger.info("Struggling EGO detected, switching to defensive")
                common.mouse_move_click(slot_x, slot_y)
                common.sleep(0.5)
                continue

            usable_ego = []
            common.mouse_move(slot_x, slot_y)
            common.mouse_hold()
            egos = common.match_image("pictures/battle/ego/sanity.png")
            for i in egos:
                x,y = i
                if common.luminence(x,y) > 100:
                    usable_ego.append(i)
            if len(usable_ego):
                ego = common.random_choice(usable_ego)
                x,y = ego
                if common.element_exist("pictures/battle/ego/sanity.png"):
                    logger.info("Using EGO to counter bad clash")
                    offset_x, offset_y = common.scale_offset_1440p(30, 30)
                    common.mouse_move_click(x + offset_x, y + offset_y)
                    common.sleep(0.3)
                    common.mouse_click()
                    common.sleep(1)
            else:
                logger.warning("No usable EGO found for bad clash")
                if common.element_exist("pictures/battle/ego/sanity.png"):
                    common.mouse_move_click(*common.scale_coordinates_1080p(20, 1060))
                    common.sleep(1)
        common.key_press("p")
        if not shared_vars.good_pc_mode:
            common.sleep(0.5)
        common.key_press("p")
        if not shared_vars.good_pc_mode:
            common.sleep(0.5)
        common.key_press("p")
        if not shared_vars.good_pc_mode:
            common.sleep(0.5)
        logger.info("EGO check completed")
    else:
        logger.debug("No bad clashes found, EGO not needed")
    return

def battle_check():
    """Handle special battle events and skill checks"""
    if common.click_matching("pictures/battle/investigate.png", recursive=False):
        logger.info("Investigate button clicked")
        common.wait_skip("pictures/events/continue.png")
        return 0
        
    elif common.element_exist("pictures/battle/NO.png"): #Woppily
        logger.info("WOPPILY PT2")
        for i in range(3):
            common.click_matching("pictures/battle/NO.png")
            common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
            while(not common.element_exist("pictures/events/proceed.png")):
                if common.click_matching("pictures/events/continue.png", recursive=False):
                    return 0
                common.mouse_click()
            common.click_matching("pictures/events/proceed.png")
            common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
            while(not common.element_exist("pictures/battle/NO.png")):
                common.mouse_click()

    elif common.click_matching("pictures/battle/refuse.png", recursive=False): # Pink Shoes or rose
        # TODO: handle this monkey patching, should find and click skip button instead
        for _ in range(20):
            common.mouse_click()
            common.sleep(0.1)
        # Fuck PM for inconsistency
        if common.element_exist("pictures/battle/rose_refuse.png"):
            logger.info("Event: [LINE 2] ROSE")
            common.wait_skip("pictures/events/continue.png")
        else:
            logger.info("Event: PINK SHOES")
            common.wait_skip("pictures/events/proceed.png")
            skill_check()
        return 0
    
    elif common.element_exist("pictures/battle/shield_passive.png"):
        options = ["pictures/battle/shield_passive.png","pictures/battle/poise_passive.png", "pictures/battle/sp_passive.png"]
        for option in options:
            if option == "pictures/battle/sp_passive.png":
                common.click_matching("pictures/battle/small_scroll.png")
                for i in range(5):
                    common.mouse_scroll(-1000)
            common.click_matching(option)
            common.sleep(0.5)
            if not common.element_exist("pictures/events/result.png",0.9):
                continue
            else:
                break
        common.wait_skip("pictures/events/continue.png")
        return 0
    
    elif common.element_exist("pictures/battle/offer_sinner.png"):
        logger.info("Event: Offer Sinner")
        found = common.match_image("pictures/battle/offer_clay.png")
        if found:
            x,y = found[0]
            _, offset_y = common.scale_offset_1440p(0, -72)
            if common.luminence(x, y + offset_y) < 195:
                common.click_matching("pictures/battle/offer_clay.png")
                common.wait_skip("pictures/events/continue.png")
                return 0

        common.click_matching("pictures/battle/offer_sinner.png")
        common.wait_skip("pictures/events/proceed.png")
        skill_check()
        return 0

    elif common.click_matching("pictures/battle/hug_bear.png", recursive=False):
        logger.info("Event: Hug Bear")
        while(not common.click_matching("pictures/events/proceed.png", recursive=False)):
            common.sleep(0.5)
        skill_check()
        return 0

    elif common.click_matching("pictures/battle/arknight_mayors_begin.png", recursive=False):
        logger.info("[Arknights] Mayors Battle Beginning")
        common.wait_skip("pictures/events/continue.png")
        return 0

    elif common.click_matching("pictures/battle/arknight_mayors_2nd.png", recursive=False):
        logger.info("[Arknights] Mayors Battle 2nd stage")
        common.wait_skip("pictures/events/continue.png")
        return 0

    elif common.click_matching("pictures/battle/line4_king.png", recursive=False):
        logger.info("[Line 4] King Battle Beginning")
        common.wait_skip("pictures/events/continue.png")
        return 0

    elif common.click_matching("pictures/battle/warpbokgak_pill.png", recursive=False):
        logger.info("[Warp Bokgak] Pill event")
        common.wait_skip("pictures/events/continue.png")
        return 0

    elif common.click_matching("pictures/battle/violet_hp.png", recursive=False):
        logger.info("Noon event - Choose HP recover")
        common.wait_skip("pictures/events/continue.png")
        return 0
    
    elif common.click_matching("pictures/battle/event_check.png", recursive=False):
        logger.info("Global event checker, Nothing was detected so did a general check.")
        common.wait_skip("pictures/events/continue.png")
        return 0

    return 1

def skill_check():
    """Handle skill check events by selecting appropriate difficulty level"""
    logger.info("Handling Skill Check")
    check_images = [
        "pictures/CustomAdded1080p/general/very_high.png",
        "pictures/CustomAdded1080p/general/high.png",
        "pictures/CustomAdded1080p/general/normal.png",
        "pictures/CustomAdded1080p/general/low.png",
        "pictures/CustomAdded1080p/general/very_low.png"
        ]
    
    common.wait_skip("pictures/events/skill_check.png")
    common.sleep(1)
    for i in check_images:
        if common.click_matching(i, threshold=0.9, recursive=False):
            break
    common.click_matching("pictures/CustomAdded1080p/general/commence.png")
    common.sleep(3)
    common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
    while(True):
        common.mouse_click()
        if common.click_matching("pictures/events/proceed.png", recursive=False):
            break
        if common.click_matching("pictures/events/continue.png", recursive=False):
            break
        if common.click_matching("pictures/events/commence_battle.png", recursive=False):
            break

    if common.element_exist("pictures/events/skip.png"):
        if common.element_exist("pictures/events/skill_check.png"):
            skill_check()
        if common.element_exist("pictures/battle/violet_hp.png"):
            common.wait_skip("pictures/battle/violet_hp.png")
            common.wait_skip("pictures/events/continue.png")

    else:
        common.sleep(1)
        if common.element_exist("pictures/mirror/general/ego_gift_get.png"):
            common.click_matching("pictures/general/confirm_b.png")

def refill_enkephalin():
    """Try to refill enkephalin using modules"""
    logger.info("Starting enkephalin refill")
    if common.click_matching("pictures/general/module.png", recursive=False):
        logger.debug("Module button clicked successfully")
        if not common.click_matching("pictures/general/right_arrow.png", recursive=False):
            logger.debug("Right arrow not found, navigating back")
            while common.click_matching("pictures/CustomAdded1080p/general/goback.png", recursive=False):
                pass
            return refill_enkephalin()
        common.click_matching("pictures/general/confirm_w.png")
        logger.info("Enkephalin refill completed")
        while common.element_exist("pictures/general/right_arrow.png"):
            common.key_press("esc")
            time.sleep(0.1)
        return True
    elif common.element_exist("pictures/general/no_enkephalin.png", quiet_failure=True):
        logger.info("Refilling Enkephalin (Popup)")
        common.click_matching("pictures/general/confirm_b.png")
        time.sleep(1)
        common.click_matching("pictures/general/close.png", quiet_failure=True)
        return True
    return False

def navigate_to_md():
    """Navigate to mirror dungeon interface"""
    while not common.element_exist("pictures/general/MD.png"):
        while common.click_matching("pictures/CustomAdded1080p/general/goback.png", recursive=False):
            pass
        common.click_matching("pictures/general/window.png")
        common.click_matching("pictures/general/drive.png")
    common.click_matching("pictures/general/MD.png")
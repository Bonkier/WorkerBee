import sys
import os
import logging
import json
import time
import common
import copy
import shared_vars
import mirror_utils
import pyautogui
from core import (skill_check, battle_check, battle, check_loading, 
                  transition_loading, post_run_load, refill_enkephalin,
                  navigate_to_md)

def get_base_path():
    """Determine if running as executable or script and return base path"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        folder_path = os.path.dirname(os.path.abspath(__file__))
        return (os.path.dirname(folder_path) if os.path.basename(folder_path) == 'src' 
                else folder_path)

BASE_PATH = get_base_path()
sys.path.append(os.path.join(BASE_PATH, "src"))
os.chdir(BASE_PATH)

logger = logging.getLogger(__name__)

class Mirror:
    def __init__(self, status):
        """Initialize Mirror instance with status and setup squad order"""
        self.status = status
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initializing Mirror with status: {status}")
        self.squad_order = self.set_sinner_order(status)
        self.aspect_ratio = common.get_aspect_ratio()
        self.res_x, self.res_y = common.get_resolution()
        self.squad_set = False
        self.vestige_coords = None
        self.logger.debug(f"Mirror initialized - resolution: {self.res_x}x{self.res_y}, aspect ratio: {self.aspect_ratio}")
        self.run_stats = {
            "start_time": time.time(),
            "floor_times": {},
            "packs": []
        }
        self.current_floor_tracker = None
        self.retries_used = 0
        self.loop_counter = 0

    @staticmethod
    def floor_id():
        """Detect current floor number from pack selection screen"""
        screenshot = common.capture_screen()
        detected_floors = []
        
        for i in range(1, 6):
            floor_name = f"floor{i}"
            if common.element_exist(f'pictures/mirror/packs/{floor_name}.png', 0.8, grayscale=True, screenshot=screenshot):
                detected_floors.append(floor_name)

        if len(detected_floors) == 1:
            logger.info(f"Current floor detected: {detected_floors[0]}")
            return detected_floors[0]
        elif len(detected_floors) > 1:
            logger.warning(f"Multiple floors detected visually: {detected_floors}. Defaulting to {detected_floors[-1]}")
            return detected_floors[-1]
        else:
            logger.warning("Could not detect current floor visually")
            return ""

    @staticmethod
    def set_sinner_order(status):
        """Get squad order for the given status, fallback to default"""
        if mirror_utils.squad_choice(status) is None:
            return common.squad_order("default")
        else:
            return common.squad_order(status)

    def setup_mirror(self):
        """Complete mirror dungeon setup from entry to gift selection"""
        
        if (common.element_exist("pictures/mirror/general/danteh.png", quiet_failure=True) or
            common.element_exist("pictures/battle/winrate.png", quiet_failure=True) or
            common.element_exist("pictures/events/skip.png", quiet_failure=True) or
            common.element_exist("pictures/mirror/restshop/shop.png", quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/packs/inpack.png", quiet_failure=True) or
            common.element_exist("pictures/mirror/general/reward_select.png", quiet_failure=True) or
            common.element_exist("pictures/mirror/general/encounter_reward.png", quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.6, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.6, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/general/squads/clear_selection.png", quiet_failure=True)):
             self.logger.info("Detected existing run state, skipping setup.")
             return

        refill_enkephalin()
        if not (common.element_exist("pictures/general/resume.png", quiet_failure=True) or common.element_exist("pictures/mirror/general/md_enter.png", quiet_failure=True)):
            navigate_to_md()
        self.logger.info("Setting up Mirror Dungeon run...")

        while not common.click_matching("pictures/mirror/general/md_enter.png", recursive=False):
            
            if (common.element_exist("pictures/mirror/general/explore_reward.png", quiet_failure=True) or
                common.element_exist("pictures/general/resume.png", quiet_failure=True) or
                common.element_exist("pictures/CustomAdded1080p/general/squads/squad_select.png", quiet_failure=True)):
                self.logger.info("Detected existing state, skipping main menu entry.")
                break
            common.sleep(0.5)

        if common.element_exist("pictures/mirror/general/explore_reward.png"):
            self.logger.info("Found explore rewards, claiming...")
            if common.element_exist("pictures/mirror/general/clear.png"):
                common.click_matching("pictures/general/md_claim.png")
                if common.click_matching("pictures/general/confirm_w.png", recursive=False):
                    while True:  
                        if common.element_exist("pictures/mirror/general/weekly_reward.png"):
                            common.key_press("enter")
                        if common.element_exist("pictures/mirror/general/pass_level.png"):
                            common.key_press("enter")
                            break
                    common.click_matching("pictures/general/cancel.png")
            else:
                self.logger.info("Run was not cleared, giving up...")
                common.click_matching("pictures/general/give_up.png")
                common.click_matching("pictures/general/cancel.png")

        if common.click_matching("pictures/general/resume.png", recursive=False): 
            self.logger.info("Resuming existing run...")
            check_loading()

        if common.click_matching("pictures/general/enter.png", recursive=False): 
            self.logger.info("Starting fresh run...")
            while(not common.element_exist("pictures/CustomAdded1080p/general/squads/squad_select.png")):
                common.sleep(0.5) 

        if common.element_exist("pictures/CustomAdded1080p/general/squads/squad_select.png"): 
            self.logger.info("In squad selection screen")
            self.initial_squad_selection()

        if common.element_exist("pictures/CustomAdded1080p/mirror/general/grace_menu.png"): 
            self.logger.info("In grace menu")
            self.grace_of_stars()

        if common.element_exist("pictures/mirror/general/gift_select.png"): 
            self.logger.info("In gift selection")
            self.gift_selection()

    def check_run(self):
        """Check if run ended and return win status and completion flag"""
        run_complete = 0
        win_flag = 0
        if (common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.6, quiet_failure=True) or 
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.6, quiet_failure=True) or 
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.jpg", threshold=0.6, quiet_failure=True) or 
            common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.6, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.jpg", threshold=0.6, quiet_failure=True)):
            self.logger.info("Defeat detected in check_run")
            run_ended = self.defeat()
            if run_ended:
                run_complete = 1
            else:
                run_complete = 0

        if common.element_exist("pictures/general/victory.png"):
            self.logger.info("Victory detected in check_run")
            self.victory()
            run_complete = 1
            win_flag = 1

        if run_complete:
            self.run_stats["duration"] = time.time() - self.run_stats["start_time"]

        return win_flag, run_complete, self.run_stats

    def mirror_loop(self):
        """Handles all the mirror dungeon logic in this"""
        self.loop_counter += 1
        if common.element_exist("pictures/general/maint.png"): 
            common.click_matching("pictures/general/close.png", recursive=False)
            common.sleep(0.5)
            common.click_matching("pictures/general/no_op.png")
            common.click_matching("pictures/general/close.png")
            self.logger.critical("Server under maintenance")
            sys.exit(0)

        if common.element_exist("pictures/events/skip.png"): 
            self.logger.info("Event skip button detected")
            common.mouse_move(*common.scale_coordinates_1080p(200, 200))
            common.click_skip(15)
            self.event_choice()

        elif common.click_matching("pictures/events/proceed.png", recursive=False):
            self.logger.info("Event proceed button detected")
            self.event_choice()

        elif common.element_exist("pictures/mirror/general/danteh.png"): 
            self.logger.info("Navigation screen detected (danteh)")
            self.navigation()

        elif common.element_exist("pictures/CustomAdded1080p/general/squads/clear_selection.png"): 
            self.logger.info("Squad selection for battle detected")
            self.squad_select()

        elif common.element_exist("pictures/mirror/general/reward_select.png"): 
            self.logger.info("Reward selection detected")
            self.reward_select()

        elif common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
            self.logger.info("EGO Gift acquisition detected")
            common.click_matching("pictures/general/confirm_b.png") 
            
        elif common.element_exist("pictures/mirror/restshop/shop.png") or common.element_exist("pictures/mirror/restshop/super_shop.png") : 
            self.logger.info("Rest shop detected")
            self.rest_shop()

        elif common.element_exist("pictures/mirror/general/encounter_reward.png"): 
            self.logger.info("Encounter reward detected")
            self.encounter_reward_select()            

        elif common.element_exist("pictures/CustomAdded1080p/mirror/packs/inpack.png"): 
            self.logger.info("Pack selection detected")
            self.pack_selection()

        elif common.element_exist("pictures/battle/winrate.png"):
            self.logger.info("Battle winrate button detected")
            battle()
            check_loading()

        elif common.element_exist("pictures/mirror/general/event_effect.png"):
            self.logger.info("Event effect selection detected")
            found = common.match_image("pictures/mirror/general/event_select.png")
            x,y = common.random_choice(found)
            common.mouse_move_click(x, y)
            common.sleep(1)
            common.click_matching("pictures/general/confirm_b.png")
            
        elif common.element_exist("pictures/general/module.png") or common.element_exist("pictures/mirror/general/md_enter.png"):
            self.logger.info("Main menu detected in loop. Forcing run completion.")
            return 0, 1, self.run_stats

        if self.loop_counter % 50 == 0:
            
            stuck_images = [
                "pictures/events/proceed.png",
                "pictures/battle/event_check.png",
                "pictures/battle/winrate.png",
                "pictures/general/victory.png",
                "pictures/mirror/general/encounter_reward.png",
            ]
            
            for img in stuck_images:
                if common.element_exist(img, threshold=0.7, quiet_failure=True):
                    self.logger.warning(f"Anti-stuck: Found {os.path.basename(img)} with low threshold. Refreshing SCT.")
                    common.reset_sct()
                    
                    
                    if "proceed.png" in img and common.click_matching(img, threshold=0.75):
                        self.event_choice()
                    elif "event_check.png" in img and common.click_matching(img, threshold=0.75):
                        common.wait_skip("pictures/events/continue.png")
                    
                    break 

        return self.check_run()

    def grace_of_stars(self):
        """Selects grace of stars blessings for the runs in the specified order"""
        
        if not hasattr(self, '_grace_coords_cache'):
            
            grace_config = shared_vars.ConfigCache.get_config("grace_selection")
            grace_order = grace_config.get('order', {})
            grace_coordinates = shared_vars.ScaledCoordinates.get_scaled_coords("grace_of_stars")
            
            
            self._grace_coords_cache = []
            if grace_order:
                sorted_graces = sorted(grace_order.items(), key=lambda x: x[1])
                self._grace_coords_cache = [grace_coordinates[name] for name, _ in sorted_graces if name in grace_coordinates]

        self.logger.info(f"Selecting Grace of Stars blessings...")
        for x, y in self._grace_coords_cache:
            common.mouse_move_click(x, y)
        
        common.click_matching("pictures/CustomAdded1080p/mirror/general/Enter.png")
        common.sleep(1)
        common.click_matching("pictures/CustomAdded1080p/mirror/general/Confirm.png")
        while(not common.element_exist("pictures/mirror/general/gift_select.png")): 
            common.sleep(0.5)
    
    def gift_selection(self):
        """selects the ego gift of the same status, fallsback on random if not unlocked"""
        self.logger.info("Starting EGO gift selection")
        
        if common.click_matching("pictures/mirror/general/gift_search_enabled.png", 0.58, recursive=False, enable_scaling=True, no_grayscale=True):
            self.logger.info("Gift search was enabled, turning it off.")
        else:
            pass

        gift = mirror_utils.gift_choice(self.status)
        if not common.element_exist(gift,0.9): 
            self.logger.info(f"Gift {gift} not found immediately, scrolling...")
            found = common.match_image("pictures/mirror/general/gift_select.png")
            x,y = found[0]
            offset_x, offset_y = common.scale_offset_1440p(-1365, 50)
            common.mouse_move(x + offset_x, y + offset_y)
            for i in range(5):
                common.mouse_scroll(-1000)

        found = common.match_image("pictures/mirror/general/gift_select.png")
        x,y = found[0]
        _, offset_y = common.scale_offset_1440p(0, 235)
        y = y + offset_y
        _, offset1 = common.scale_offset_1440p(0, 190)
        _, offset2 = common.scale_offset_1440p(0, 380)
        gift_pos = [y, y+offset1, y+offset2]

        initial_gift_coords = gift_pos if self.status != "sinking" else [*gift_pos[1:], gift_pos[0]]  

        self.logger.info(f"Selecting gift: {gift}")
        common.click_matching(gift,0.9) 
        

        for i in initial_gift_coords:
            scaled_x, _ = common.scale_coordinates_1440p(1640, 0)
            common.mouse_move_click(scaled_x, i)
        
        common.key_press("enter")
        while not common.element_exist("pictures/mirror/general/ego_gift_get.png"):
            common.sleep(0.5)
        for i in range(3):
            if common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
                common.key_press("enter")
                common.sleep(0.5)
        check_loading()

    def initial_squad_selection(self):
        """Searches for the squad name with the status type, if not found then uses the current squad"""
        self.logger.info("Performing initial squad selection")
        status = mirror_utils.squad_choice(self.status)
        if status is None:
            common.key_press("enter")
            self.status = "poise"
            while(not common.element_exist("pictures/CustomAdded1080p/mirror/general/grace_menu.png")): 
                common.click_matching("pictures/CustomAdded1080p/general/confirm.png", recursive=False, mousegoto200=True)
            return
        
        found = common.match_image("pictures/CustomAdded1080p/general/squads/squad_select.png")
        x,y = found[0]
        offset_x, offset_y = common.scale_offset_1440p(90, 90)
        common.mouse_move(x+offset_x,y+offset_y)
        if not common.click_matching(status, recursive=False):
            for i in range(30):
                common.mouse_scroll(1000)

            
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
        common.key_press("enter")
        while(not common.element_exist("pictures/CustomAdded1080p/mirror/general/grace_menu.png")):
            common.click_matching("pictures/CustomAdded1080p/general/confirm.png", recursive=False, mousegoto200=True)

    def pack_selection(self) -> None:
        """Prioritises the status gifts for packs if not follows a list"""
        status = mirror_utils.pack_choice(self.status) or "pictures/mirror/packs/status/poise_pack.png"

        pack_count = len(self.run_stats["packs"])
        floor_num = min(pack_count + 1, 5)
        floor = f"floor{floor_num}"
        self.logger.info(f"Calculated Floor: {floor_num} (based on {pack_count} previous packs)")

        visual_floor = self.floor_id()
        if visual_floor and visual_floor != floor:
             self.logger.warning(f"Visual floor detection ({visual_floor}) mismatch with calculated ({floor}). Updating to visual floor.")
             floor = visual_floor

        if floor != self.current_floor_tracker:
            self.current_floor_tracker = floor
            self.run_stats["floor_times"][floor] = time.time() - self.run_stats["start_time"]
            
        if floor == "floor1":
            common.sleep(0.5)

        self.logger.info(f"Hard Mode setting: {shared_vars.hard_mode}")

        if shared_vars.hard_mode:
            if (common.element_exist("pictures/CustomAdded1080p/mirror/packs/floor_normal.png", 0.8, quiet_failure=True) or
                common.element_exist("pictures/CustomAdded1080p/mirror/packs/normal_toggle.png", 0.8, quiet_failure=True)):
                self.logger.info("Detected Normal Mode, switching to Hard Mode")
                if not common.click_matching("pictures/CustomAdded1080p/mirror/packs/normal_toggle.png", threshold=0.75, recursive=False, quiet_failure=True):
                    self.logger.warning("Could not find normal_toggle.png. Attempting to click floor_normal.png as fallback.")
                    common.click_matching("pictures/CustomAdded1080p/mirror/packs/floor_normal.png", threshold=0.75, recursive=False, quiet_failure=True)
        else:
            if (common.element_exist("pictures/CustomAdded1080p/mirror/packs/floor_hard.png", 0.8, quiet_failure=True) or 
                common.element_exist("pictures/mirror/packs/floor_hard.png", 0.8, quiet_failure=True) or
                common.element_exist("pictures/CustomAdded1080p/mirror/packs/hard_toggle.png", 0.8, quiet_failure=True) or
                common.element_exist("pictures/mirror/packs/hard_toggle.png", 0.8, quiet_failure=True)): 
                self.logger.info("Detected Hard Mode, switching to Normal Mode")
                common.sleep(2) 
                if not common.click_matching("pictures/CustomAdded1080p/mirror/packs/hard_toggle.png", threshold=0.75, recursive=False, quiet_failure=True):
                    if not common.click_matching("pictures/mirror/packs/hard_toggle.png", threshold=0.75, recursive=False, quiet_failure=True):
                        self.logger.warning("Could not find hard_toggle.png. Attempting to click floor_hard.png as fallback.")
                        if not common.click_matching("pictures/CustomAdded1080p/mirror/packs/floor_hard.png", threshold=0.75, recursive=False, quiet_failure=True):
                            common.click_matching("pictures/mirror/packs/floor_hard.png", threshold=0.75, recursive=False, quiet_failure=True)

        min_y_scaled = common.scale_y_1080p(260)
        max_y_scaled = common.scale_y_1080p(800)
        min_x_scaled = common.scale_x_1080p(150)
        max_x_scaled = common.scale_x_1080p(1730)

        known_pack_names = {} 
        refresh_count = 0
        MAX_REFRESHES = getattr(shared_vars, 'pack_refreshes', 7)

        retry_attempt = 10
        while retry_attempt > 0:
            retry_attempt -= 1

            floor_priorities = shared_vars.ConfigCache.get_config("pack_priority").get(floor, {})
            exception_packs = shared_vars.ConfigCache.get_config("pack_exceptions").get(floor, [])

            # Sort priorities for clearer logging
            sorted_priorities_log = sorted(floor_priorities.items(), key=lambda x: x[1])
            self.logger.info(f"Pack Selection - Floor: {floor} | Priorities: {sorted_priorities_log}")
            
            common.mouse_move(*common.scale_coordinates_1080p(200,200))
            common.sleep(0.2)
            screenshot = common.capture_screen()

            selectable_packs_pos = common.match_image(
                "pictures/CustomAdded1080p/mirror/packs/inpack.png", 
                screenshot=screenshot,
                x1=min_x_scaled,
                y1=min_y_scaled,
                x2=max_x_scaled,
                y2=max_y_scaled
            )
            
            if len(selectable_packs_pos) == 0:
                if retry_attempt > 0:
                    logger.debug("No packs detected, retrying...")
                    common.sleep(0.5)
                    continue
            
            self.logger.debug(f"Found {len(selectable_packs_pos)} selectable packs")

            except_packs_pos = []
            if floor:
                for pack in exception_packs:
                    floor_num = floor[-1]
                    image_floor = f"f{floor_num}"
                    pack_image = f"pictures/mirror/packs/{image_floor}/{pack}.png"
                    except_packs_pos.extend(common.match_image(
                        pack_image, 
                        0.65, 
                        screenshot=screenshot, 
                        enable_scaling=True,
                        x1=min_x_scaled,
                        y1=min_y_scaled,
                        x2=max_x_scaled,
                        y2=max_y_scaled
                    ))
            
            self.logger.debug(f"Found {len(except_packs_pos)} exception packs")

            found_priority_packs = [] 
            
            if floor and floor_priorities:
                sorted_priorities = sorted(floor_priorities.items(), key=lambda x: x[1])
                
                for pack, rank in sorted_priorities:
                    if pack in exception_packs:
                        continue
                        
                    floor_num = floor[-1]
                    image_floor = f"f{floor_num}"
                    pack_image = f"pictures/mirror/packs/{image_floor}/{pack}.png"
                    
                    
                    high_conf_matches = common.match_image(
                        pack_image, 
                        0.85, 
                        grayscale=True,
                        screenshot=screenshot, 
                        enable_scaling=True,
                        x1=min_x_scaled,
                        y1=min_y_scaled,
                        x2=max_x_scaled,
                        y2=max_y_scaled
                    )

                    matches = common.match_image(
                        pack_image, 
                        0.60, 
                        grayscale=True,
                        screenshot=screenshot, 
                        enable_scaling=True,
                        x1=min_x_scaled,
                        y1=min_y_scaled,
                        x2=max_x_scaled,
                        y2=max_y_scaled
                    )

                    if not matches:
                        matches = common.match_image(
                            pack_image, 
                            0.55, 
                            grayscale=False,
                            no_grayscale=True,
                            screenshot=screenshot, 
                            enable_scaling=True,
                            x1=min_x_scaled,
                            y1=min_y_scaled,
                            x2=max_x_scaled,
                            y2=max_y_scaled
                        )
                    
                    if matches:
                        
                        high_conf_set = set()
                        if high_conf_matches:
                            high_conf_overlaps = common.proximity_check(matches, high_conf_matches, common.scale_x_1080p(10))
                            high_conf_set = set(high_conf_overlaps)

                        
                        overlaps = common.proximity_check(matches, except_packs_pos, common.scale_x_1080p(100))
                        
                        valid_matches = []
                        for m in matches:
                            if m in high_conf_set:
                                
                                valid_matches.append(m)
                                if m in overlaps:
                                    logger.debug(f"Keeping high confidence priority pack '{pack}' despite exception overlap")
                            elif m not in overlaps:
                                
                                valid_matches.append(m)
                            else:
                                logger.debug(f"Filtered low confidence priority pack '{pack}' due to exception overlap")

                        if valid_matches:
                            logger.debug(f"Found priority pack '{pack}' (Rank {rank})")
                            for m in valid_matches:
                                known_pack_names[m] = pack
                                found_priority_packs.append((rank, m, pack))

            packs_to_remove = common.proximity_check(selectable_packs_pos, except_packs_pos, common.scale_y_1080p(450))
            selectable_packs_pos = [p for p in selectable_packs_pos if p not in packs_to_remove]

            offset_x, offset_y = common.scale_offset_1440p(-100, 150)
            selectable_packs_pos = [(pos[0]+offset_x, pos[1]+offset_y) for pos in selectable_packs_pos]

            status_gift_pos = common.match_image(
                status, 
                screenshot=screenshot,
                enable_scaling=True,
                x1=min_x_scaled,
                y1=min_y_scaled,
                x2=max_x_scaled,
                y2=max_y_scaled
            )
            self.logger.debug(f"Found {len(status_gift_pos)} status packs")
            
            if status == "pictures/mirror/packs/status/pierce_pack.png":
                status_gift_pos = [x for x in status_gift_pos if x[1] > common.scale_y(1092)]  

            owned_gift_pos = common.match_image(
                "pictures/mirror/packs/status/owned.png", 
                0.8, 
                screenshot=screenshot,
                enable_scaling=True,
                x1=min_x_scaled,
                y1=min_y_scaled,
                x2=max_x_scaled,
                y2=max_y_scaled
            )
            if owned_gift_pos:
                
                owned_gift_pos = common.proximity_check(status_gift_pos, owned_gift_pos, common.scale_x_1080p(50))
                if owned_gift_pos:
                    for i in owned_gift_pos:
                        if i in status_gift_pos:
                            status_gift_pos.remove(i)

            status_selectable_packs_pos = common.proximity_check(selectable_packs_pos, status_gift_pos, common.scale_x_1080p(432))
            status_selectable_packs_pos = [pos for pos in status_selectable_packs_pos if min_y_scaled <= pos[1] <= max_y_scaled and min_x_scaled <= pos[0] <= max_x_scaled]

            def robust_drag_pack(x, y):
                common.mouse_move(x, y)
                common.sleep(0.15)
                pyautogui.mouseDown()
                common.sleep(0.15)
                dest_x, dest_y = common.get_MonCords(x, y + 350)
                pyautogui.moveTo(dest_x, dest_y, duration=0.6)
                common.sleep(0.15)
                pyautogui.mouseUp()

            def select_pack(coords, name="unknown_pack", source="unknown"):
                pack_name = name
                raw_name = name 
                
                if source == "status":
                    raw_name = os.path.basename(status).replace("_pack.png", "")
                    pack_name = raw_name.capitalize()
                elif coords in known_pack_names:
                    raw_name = known_pack_names[coords]
                    pack_name = raw_name

                if pack_name.lower().endswith('.png'):
                    pack_name = pack_name[:-4]

                detected_floor = "unknown_floor"
                if raw_name != "unknown_pack":
                    for i in range(1, 6):
                        
                        found = False
                        for ext in [".png", ".jpg", ".jpeg"]:
                            check_path = os.path.join(BASE_PATH, f"pictures/mirror/packs/f{i}/{raw_name}{ext}")
                            if os.path.exists(check_path):
                                detected_floor = f"Floor {i}"
                                found = True
                                break
                        if found:
                            break
                
                self.logger.info(f"Selected Pack: {pack_name} | Location: {detected_floor}")

                if not self.run_stats["packs"] or self.run_stats["packs"][-1] != pack_name:
                    self.run_stats["packs"].append(pack_name)
                
                x, y = coords
                robust_drag_pack(x, y)

                wait_start = time.time()
                while time.time() - wait_start < 5:
                    if not common.element_exist("pictures/CustomAdded1080p/mirror/packs/inpack.png", 
                                              threshold=0.8, x1=min_x_scaled, y1=min_y_scaled, x2=max_x_scaled, y2=max_y_scaled, quiet_failure=True):
                        break
                    common.sleep(0.2)

            if found_priority_packs:
                found_priority_packs.sort(key=lambda x: x[0])

            if not shared_vars.prioritize_list_over_status and status_selectable_packs_pos and floor != "floor5":
                logger.info("Selecting status pack (Status > List)")
                select_pack(status_selectable_packs_pos[0], source="status")
                return

            if found_priority_packs:
                best_pack = found_priority_packs[0]
                logger.info(f"Selecting priority pack: {best_pack[2]}")
                select_pack(best_pack[1], best_pack[2])
                return

            if floor_priorities and refresh_count < MAX_REFRESHES:
                logger.info(f"Priority packs defined but none found. Attempting refresh ({refresh_count + 1}/{MAX_REFRESHES}).")
                
                
                refresh_x1, refresh_y1 = common.scale_coordinates_1080p(1400, 0)
                refresh_x2, refresh_y2 = common.scale_coordinates_1080p(1920, 200)
                
                refresh_btn = common.match_image(
                    "pictures/mirror/general/refresh.png", 
                    0.75, 
                    screenshot=screenshot, 
                    enable_scaling=True,
                    x1=refresh_x1, y1=refresh_y1, x2=refresh_x2, y2=refresh_y2
                )
                
                if not refresh_btn:
                    
                    refresh_btn = common.match_image(
                        "pictures/mirror/general/refresh.png", 
                        0.6, 
                        screenshot=screenshot, 
                        enable_scaling=True,
                        x1=common.scale_x_1080p(1000), y1=0, 
                        x2=common.scale_x_1080p(1920), y2=common.scale_y_1080p(400)
                    )

                if refresh_btn:
                    x, y = refresh_btn[0]
                    common.mouse_move_click(x, y)
                    logger.info("Refreshed via image detection.")
                    
                    common.mouse_move(*common.scale_coordinates_1080p(200, 200))
                    common.sleep(2.5)
                    refresh_count += 1
                    retry_attempt = 10
                    continue
                else:
                    
                    logger.warning("Refresh button not found via image. Attempting blind click.")
                    
                    common.mouse_move_click(*common.scale_coordinates_1080p(1600, 50))
                    
                    common.mouse_move(*common.scale_coordinates_1080p(200, 200))
                    common.sleep(2.5)
                    refresh_count += 1
                    retry_attempt = 10
                    continue

            if status_selectable_packs_pos and floor != "floor5":
                logger.info("Selecting status pack")
                select_pack(status_selectable_packs_pos[0], source="status")
                return

            if selectable_packs_pos:
                logger.info("Fallback: Selecting random available pack")
                
                pack_identities = {}
                if floor:
                    try:
                        floor_num = floor[-1]
                        image_floor = f"f{floor_num}"
                        floor_dir = os.path.join(BASE_PATH, f"pictures/mirror/packs/{image_floor}")
                        
                        if os.path.exists(floor_dir):
                            all_packs = [f.replace(".png", "") for f in os.listdir(floor_dir) if f.endswith(".png")]
                            
                            for pack in all_packs:
                                if pack in known_pack_names.values():
                                    continue
                                    
                                pack_image = f"pictures/mirror/packs/{image_floor}/{pack}.png"
                                matches = common.match_image(pack_image, 0.65, grayscale=True, screenshot=screenshot, enable_scaling=True, x1=min_x_scaled, y1=min_y_scaled, x2=max_x_scaled, y2=max_y_scaled)
                                
                                if matches:
                                    close_targets = common.proximity_check(selectable_packs_pos, matches, common.scale_x_1080p(250))
                                    for t in close_targets:
                                        pack_identities[t] = pack
                    except Exception as e:
                        logger.error(f"Error identifying fallback packs: {e}")

                for target_coords in selectable_packs_pos:
                    pack_name = pack_identities.get(target_coords, "unknown_pack")
                    
                    if pack_name in exception_packs:
                        logger.info(f"Fallback identified excluded pack '{pack_name}', skipping.")
                        continue
                    
                    if pack_name != "unknown_pack":
                        logger.info(f"Identified fallback pack as: {pack_name}")
                        
                    select_pack(target_coords, pack_name)
                    return

        if retry_attempt == 0:
            logger.error("Something went wrong, not fixable after 10 retries.")

    def squad_select(self):
        """selects sinners in squad order"""
        self.logger.info("Selecting squad members for battle")
        if not self.squad_set or not common.element_exist("pictures/CustomAdded1080p/general/squads/full_squad.png"):
            common.click_matching("pictures/CustomAdded1080p/general/squads/clear_selection.png")
            common.click_matching("pictures/general/confirm_w.png", recursive=False)
            for i in self.squad_order: 
                x,y = i
                self.logger.info(f"Clicking squad member at ({x}, {y})")
                common.mouse_move_click(x, y)
            self.squad_set = True
        
        common.mouse_move_click(*common.scale_coordinates_1080p(1722, 881))
        for i in range(20):
            if common.element_exist("pictures/battle/winrate.png"):
                logger.debug("Premature break due to winrate detected.")
                break
            if common.element_exist("pictures/events/skip.png"):
                logger.debug("Premature break due to event skip button detected")
                break
            common.sleep(0.5)
        battle()
        check_loading()

    def reward_select(self):
        """Selecting EGO Gift rewards, when randomly rewarded or rewarded at floor end."""
        self.logger.info("Selecting rewards")
        status_effect = mirror_utils.reward_choice(self.status)
        if status_effect is None:
            status_effect = "pictures/mirror/rewards/poise_reward.png"
        ego_gift_matches = common.match_image("pictures/CustomAdded1080p/mirror/general/acquire_ego_gift_identifier.png")

        
        owned_ego_gift_matches = common.match_image("pictures/mirror/rewards/owned.png")
        
        for i in range(len(owned_ego_gift_matches)):
            owned_ego_gift_matches[i] = (owned_ego_gift_matches[i][0]+common.scale_x(200), owned_ego_gift_matches[i][1])
        
        selectable_ego_gift_matches = copy.deepcopy(ego_gift_matches)
        if owned_ego_gift_matches:
            owned_ego_gift_matches = common.proximity_check(ego_gift_matches, owned_ego_gift_matches, common.scale_x_1080p(150))
            for pos in owned_ego_gift_matches:
                selectable_ego_gift_matches.remove(pos)

        found = common.match_image(status_effect,0.85)
        if not found:
            logger.info("No gift matching status found.")
        
        min_y_scaled = common.scale_y_1080p(225)
        max_y_scaled = common.scale_y_1080p(845)
        filtered_rewards = [reward for reward in found if min_y_scaled <= reward[1] <= max_y_scaled]
        if owned_ego_gift_matches:
            owned_filtered_rewards = common.proximity_check(filtered_rewards, owned_ego_gift_matches, common.scale_x_1080p(200))
            for pos in owned_filtered_rewards:
                filtered_rewards.remove(pos)

        mounting_trials = common.match_image("pictures/mirror/general/ego_gift_mounting_trials.png", 0.9)
        num_choice = 2 if shared_vars.hard_mode and len(mounting_trials) > 0 else 1

        for i in range(num_choice):
            if len(filtered_rewards) > 0:
                x,y = common.random_choice(filtered_rewards)
                
                filtered_rewards.remove((x, y))
                selected_gift = common.proximity_check(selectable_ego_gift_matches, [(x, y)], common.scale_x_1080p(200))
                for pos in selected_gift:
                    selectable_ego_gift_matches.remove(pos)
            if len(selectable_ego_gift_matches) > 0:

                x,y = common.random_choice(selectable_ego_gift_matches)
                
                selectable_ego_gift_matches.remove((x, y))
            elif i == 0:
                logger.info("Force select at least 1 ego gift.")

                x,y = common.random_choice(ego_gift_matches)
                
                ego_gift_matches.remove((x, y))
            else:
                logger.info("No good ego gift choice left, skip to select.")
                break
            common.mouse_move_click(x, y)

        common.key_press("enter")
        common.sleep(1)
        common.key_press("enter")

    def encounter_reward_select(self):
        """Select Encounter Rewards prioritising starlight first"""
        self.logger.info("Selecting encounter rewards")
        encounter_reward = ["pictures/mirror/encounter_reward/cost_gift.png",
                            "pictures/mirror/encounter_reward/cost.png",
                            "pictures/mirror/encounter_reward/gift.png",
                            "pictures/mirror/encounter_reward/resource.png"]
        common.sleep(0.5)
        
        min_x = common.scale_x_1080p(360)
        max_x = common.scale_x_1080p(1555)
        min_y = common.scale_y_1080p(225)
        max_y = common.scale_y_1080p(845)
        for rewards in encounter_reward:
            if common.click_matching(rewards, recursive=False, x1=min_x, y1=min_y, x2=max_x, y2=max_y):
                common.click_matching("pictures/general/confirm_b.png")
                common.sleep(1)
                if common.element_exist("pictures/mirror/encounter_reward/prompt.png"):
                    common.click_matching("pictures/CustomAdded1080p/mirror/general/BorderedConfirm.png")
                    break
                if common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
                    common.click_matching("pictures/general/confirm_b.png", recursive=False)
                break
        common.sleep(3) 

    def check_nodes(self,nodes):
        """Check which navigation nodes exist on the current floor"""
        screenshot = common.capture_screen()
        non_exist = [1,1,1]
        top = common.greyscale_match_image("pictures/mirror/general/node_1.png",0.75, screenshot=screenshot)
        top_alt = common.greyscale_match_image("pictures/mirror/general/node_1_o.png",0.75, screenshot=screenshot)
        middle = common.greyscale_match_image("pictures/mirror/general/node_2.png",0.75, screenshot=screenshot)
        middle_alt = common.greyscale_match_image("pictures/mirror/general/node_2_o.png",0.75, screenshot=screenshot)
        bottom = common.greyscale_match_image("pictures/mirror/general/node_3_o.png",0.75, screenshot=screenshot)
        bottom_alt = common.greyscale_match_image("pictures/mirror/general/node_3.png",0.75, screenshot=screenshot)
        if not top and not top_alt:
            non_exist[0] = 0
        if not middle and not middle_alt:
            non_exist[1] = 0
        if not bottom and not bottom_alt:
            non_exist[2] = 0
        nodes = [y for y, exists in zip(nodes, non_exist) if exists != 0]
        return nodes

    def navigation(self, drag_danteh=True):
        """Core navigation function to reach the end of floor"""
        self.logger.info("Navigating floor nodes")
        if common.click_matching("pictures/mirror/general/nav_enter.png", recursive=False):
            return

        duration = 5
        end_time = time.time() + duration

        while not (
            common.click_matching("pictures/mirror/general/danteh.png", recursive=False) or
            common.click_matching("pictures/CustomAdded1080p/mirror/general/danteh_zoomed.png", recursive=False)
        ):
            if time.time() > end_time:
                break

        while common.element_exist("pictures/general/connection_o.png"):
            pass

        if common.click_matching("pictures/mirror/general/nav_enter.png", recursive=False):
            return
        
        else:
            
            node_location = []
            if self.aspect_ratio == "16:10": 
                node_y = [189,607,1036] 
            else:
                node_y = [263,689,1115] 

            node_y = self.check_nodes(node_y)

            for y in node_y:
                if self.aspect_ratio == "4:3":
                    node_location.append(common.scale_coordinates_1440p(1440, y + 105))
                else:
                    node_location.append(common.scale_coordinates_1440p(1440, y))
            if drag_danteh and self.aspect_ratio == "16:9": 
                common.mouse_move(*common.scale_coordinates_1080p(200, 200))
                if found := common.match_image("pictures/mirror/general/danteh.png"):
                    x,y = found[0]
                    common.mouse_move(x,y)
                    _, offset_y = common.scale_offset_1440p(0, 100)
                    common.mouse_drag(x, y + offset_y)

            combat_nodes = common.match_image("pictures/mirror/general/cost.png")
            combat_nodes = [x for x in combat_nodes if x[0] > common.scale_x(1280) and x[0] < common.scale_x(1601)]
            combat_nodes_locs = common.proximity_check_fuse(node_location, combat_nodes,common.scale_x(100), common.scale_y(200))
            node_location = [i for i in node_location if i not in list(combat_nodes_locs)]
            node_location = node_location + list(combat_nodes_locs)

            if not node_location:
                common.logger.error("No nodes detected, retrying")
                
                common.error_screenshot()
                
                self.navigation(drag_danteh=False)
                return
            
            self.logger.info(f"Found {len(node_location)} possible navigation nodes")

            while(not common.element_exist("pictures/mirror/general/nav_enter.png")):
                if (common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.6, quiet_failure=True) or 
                    common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.6, quiet_failure=True) or 
                    common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.jpg", threshold=0.6, quiet_failure=True) or 
                    common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.6, quiet_failure=True) or 
                    common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.jpg", threshold=0.6, quiet_failure=True) or 
                    common.element_exist("pictures/general/victory.png")):
                    return
                nav_found = False
                for x,y in node_location:
                    common.mouse_move_click(x, y)
                    common.sleep(1)
                    if common.element_exist("pictures/mirror/general/nav_enter.png"):
                        nav_found = True
                        break
                
                if not nav_found:
                    self.navigation(drag_danteh=False)
                    return
            common.click_matching("pictures/mirror/general/nav_enter.png")

    def sell_gifts(self):
        """Handles Selling gifts"""
        for _ in range(3):
            common.sleep(1)
            if common.click_matching("pictures/mirror/restshop/market/vestige_2.png", recursive=False):
                common.click_matching("pictures/mirror/restshop/market/sell_b.png")
                common.click_matching("pictures/general/confirm_w.png")

            if common.click_matching("pictures/mirror/restshop/scroll_bar.png", recursive=False):
                for k in range(5):
                    common.mouse_scroll(-1000)
    
    def fuse(self):
        """Execute fusion of selected gifts"""

        common.mouse_move(*common.scale_coordinates_1080p(50, 50))
        common.sleep(0.3) 
        
        start_time = time.time()
        while not common.click_matching("pictures/mirror/restshop/fusion/fuse_b.png", recursive=False):
            if time.time() - start_time > 10: 
                return False
            common.sleep(0.5)
            
        if common.element_exist("pictures/CustomAdded1080p/mirror/general/cannot_fuse.png"):
            common.mouse_move(*common.scale_coordinates_1080p(50, 50))
            return False
        common.click_matching("pictures/general/confirm_b.png")
        
        wait_start = time.time()
        while(not common.element_exist("pictures/mirror/general/ego_gift_get.png")): 
            if time.time() - wait_start > 10:
                self.logger.warning("Timed out waiting for fusion result")
                return False
            common.sleep(0.5)

        common.click_matching("pictures/general/confirm_b.png")
        common.sleep(0.5)

        if common.element_exist("pictures/mirror/general/ego_gift_get.png"):
             common.key_press("enter")
             
        return True

    def find_gifts(self, statuses, excluded_statuses=None):
        """Find all gifts matching the given status list for fusion, with region optimization"""
        fusion_gifts = []
        gift_types = {} 

        x1 = common.scale_x_1080p(920) 
        y1 = common.scale_y_1080p(300)
        x2 = common.scale_x_1080p(1700)
        y2 = common.scale_y_1080p(680) 
        
        screenshot = common.capture_screen()

        exception_gifts = self.load_fusion_exceptions()
        skip_keywordless = any(os.path.basename(p).lower() == "keywordless.png" for p in exception_gifts)
        
        if not skip_keywordless:
            vestige_coords = common.ifexist_match("pictures/mirror/restshop/market/vestige_2.png", threshold=0.8, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot)
            if vestige_coords:
                self.logger.info(f"find_gifts: Detected {len(vestige_coords)} 'vestige' gifts")
                fusion_gifts += vestige_coords
                for coord in vestige_coords:
                    if coord not in gift_types: gift_types[coord] = []
                    gift_types[coord].append("vestige")
            
            wordless_coords = common.ifexist_match("pictures/mirror/restshop/market/wordless.png", threshold=0.8, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot)
            if wordless_coords:
                self.logger.info(f"find_gifts: Detected {len(wordless_coords)} 'wordless' gifts")
                fusion_gifts += wordless_coords
                for coord in wordless_coords:
                    if coord not in gift_types: gift_types[coord] = []
                    gift_types[coord].append("wordless")
            
        for i in statuses:
            status = mirror_utils.get_status_gift_template(i)

            threshold = 0.7
            
            status_coords = common.ifexist_match(status, threshold, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot)
            if status_coords:
                self.logger.info(f"find_gifts: Detected {len(status_coords)} '{i}' gifts at {status_coords}")
                fusion_gifts += status_coords
                for coord in status_coords:
                    if coord not in gift_types: gift_types[coord] = []
                    gift_types[coord].append(i)
            
            market_status = mirror_utils.market_choice(i)
            if market_status:
                market_coords = common.ifexist_match(market_status, threshold, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot)
                if market_coords:
                    self.logger.info(f"find_gifts: Detected {len(market_coords)} '{i}' market gifts at {market_coords}")
                    fusion_gifts += market_coords
                    for coord in market_coords:
                        if coord not in gift_types: gift_types[coord] = []
                        gift_types[coord].append(f"{i}_market")

        if excluded_statuses:
            for i in excluded_statuses:
                status = mirror_utils.get_status_gift_template(i)
                excluded_coords = common.ifexist_match(status, 0.70, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, quiet_failure=True)
                if excluded_coords:
                    self.logger.info(f"find_gifts: Detected {len(excluded_coords)} excluded '{i}' gifts, removing overlaps.")
                    to_remove = common.proximity_check(fusion_gifts, excluded_coords, common.scale_x_1080p(70))
                    fusion_gifts = [g for g in fusion_gifts if g not in to_remove]

        fusion_gifts = list(dict.fromkeys(fusion_gifts))

        for gift in fusion_gifts:
            types = gift_types.get(gift, ["unknown"])
            self.logger.info(f"Candidate gift at {gift} identified as: {', '.join(types)}")

        self.logger.debug("Checking for fully upgraded (++) gifts...")
        fully_upgraded_coords = common.ifexist_match("pictures/CustomAdded1080p/mirror/general/fully_upgraded.png", 0.8, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, enable_scaling=True)
        if fully_upgraded_coords:
             self.logger.info(f"find_gifts: Detected {len(fully_upgraded_coords)} fully upgraded (++) markers.")

             upgraded_gifts = common.enhanced_proximity_check(fully_upgraded_coords, fusion_gifts, 
                                                            expand_left=common.scale_x_1080p(50),
                                                            expand_right=common.scale_x_1080p(100), 
                                                            expand_above=common.scale_y_1080p(50),
                                                            expand_below=common.scale_y_1080p(100),
                                                            use_bounding_box=False, return_bool=False)
             if upgraded_gifts:
                 self.logger.info(f"Filtered {len(upgraded_gifts)} fully upgraded (++) gifts.")
                 fusion_gifts = [g for g in fusion_gifts if g not in upgraded_gifts]

        fusion_gifts = self.filter_exception_gifts(fusion_gifts, screenshot, exception_gifts)

        fusion_gifts = [x for x in fusion_gifts if x[1] < common.scale_y_1080p(680) and x[0] > x1]

        unique_gifts = []
        for gift in fusion_gifts:
            is_duplicate = False
            for unique in unique_gifts:
                
                if abs(gift[0] - unique[0]) < common.scale_x_1080p(100) and abs(gift[1] - unique[1]) < common.scale_y_1080p(100):
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique_gifts.append(gift)
        
        self.logger.info(f"find_gifts: Found {len(unique_gifts)} gifts. Coords: {unique_gifts}")
        
        return unique_gifts
    
    def filter_exception_gifts(self, fusion_gifts, screenshot=None, exception_gifts=None):
        """Remove status detections that are inside exception gift areas"""
        if not fusion_gifts:
            return fusion_gifts
        
        if exception_gifts is None:
            exception_gifts = self.load_fusion_exceptions()
            
        if not exception_gifts:
            return fusion_gifts
        
        if screenshot is None:
            screenshot = common.capture_screen()
        
        filtered_gifts = []

        radius_x = common.scale_x_1080p(80)
        radius_y = common.scale_y_1080p(80)
        
        for gift_x, gift_y in fusion_gifts:
            is_exception = False

            x1 = max(0, gift_x - radius_x)
            y1 = max(0, gift_y - radius_y)
            x2 = gift_x + radius_x
            y2 = gift_y + radius_y
            
            for gift_img in exception_gifts:
                if os.path.basename(gift_img).lower() == "keywordless.png":
                    continue

                try:
                    if common.ifexist_match(gift_img, 0.8, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot):
                        self.logger.info(f"Filtered gift at ({gift_x}, {gift_y}) - matched exception: {os.path.basename(gift_img)}")
                        is_exception = True
                        break
                except Exception as e:
                    self.logger.debug(f"Error matching exception {gift_img}: {e}")
                    continue
            
            if not is_exception:
                filtered_gifts.append((gift_x, gift_y))
        
        self.logger.info(f"filter_exception_gifts: {len(fusion_gifts)} -> {len(filtered_gifts)} gifts remaining")
        return filtered_gifts
    
    def load_fusion_exceptions(self):
        """Load fusion exceptions from JSON config file"""
        exception_gifts = []
        
        try:
            exceptions_data = shared_vars.ConfigCache.get_config("fusion_exceptions")

            if isinstance(exceptions_data, list):
                for name in exceptions_data:
                    
                    folder_path = os.path.join(BASE_PATH, "pictures", "CustomFuse", name)
                    if os.path.isdir(folder_path):
                        
                        for file in os.listdir(folder_path):
                            if file.lower().endswith(('.png', '.jpg', '.jpeg')):
                                exception_gifts.append(f"pictures/CustomFuse/{name}/{file}")
                    else:
                        found_file = False
                        for ext in ['.png', '.jpg', '.jpeg']:
                            probe_path = f"pictures/CustomFuse/{name}{ext}"
                            if os.path.exists(os.path.join(BASE_PATH, probe_path)):
                                exception_gifts.append(probe_path)
                                found_file = True
                                break
                        if not found_file:
                            self.logger.warning(f"FUSION: Exception image not found for '{name}'")
            else:
                self.logger.warning(f"FUSION: Expected list format, got {type(exceptions_data)}. Use format: [\"gift_name1\", \"gift_name2\"]")
                        
        except Exception as e:
            self.logger.warning(f"Error loading fusion exceptions: {e}")
        
        return exception_gifts
    
    def fuse_gifts(self):
        """Main fusion process - find gifts and fuse them into target status"""
        self.logger.info("Starting gift fusion")

        def exit_fusion():
            if common.element_exist("pictures/mirror/restshop/close.png"):
                common.click_matching("pictures/mirror/restshop/close.png", recursive=False)
            else:
                common.sleep(2)
                common.click_matching("pictures/mirror/restshop/close.png", recursive=False)
            
            common.sleep(1) 

        statuses = ["burn","bleed","tremor","rupture","sinking","poise","charge","slash","pierce","blunt"] 
        all_statuses = list(statuses)
        excluded_statuses = [self.status]
        statuses.remove(self.status)

        try:
            
            exceptions_data = shared_vars.ConfigCache.get_config("fusion_exceptions")
            
            if isinstance(exceptions_data, list):
                
                exceptions_lower = [e.lower() for e in exceptions_data]
                
                statuses = [s for s in statuses if s not in exceptions_lower]
                excluded_statuses.extend([s for s in exceptions_lower if s in all_statuses])
        except Exception as e:
            logger.warning(f"Error filtering fusion statuses: {e}")

        if not common.click_matching("pictures/mirror/restshop/fusion/fuse.png", recursive=False):
            self.logger.warning("Could not find fuse button. Aborting fusion.")
            return

        start_time = time.time()
        duration = 3  
        while not common.element_exist("pictures/mirror/restshop/fusion/fuse_menu.png"):
            if time.time() > (start_time + duration):
                logger.info(f"No fuse menu appeared after {duration}s. Aborting.")
                exit_fusion()
                return
            time.sleep(0.2)

        status_picture = f"pictures/mirror/restshop/fusion/{self.status}_fusion.png"
        self.logger.info(f"Attempting to select fusion keyword: {status_picture}")
        
        common.mouse_move_click(*common.scale_coordinates_1440p(730, 700)) 
        time.sleep(0.5) 

        selection_start_time = time.time()
        while not common.click_matching(status_picture, recursive=False, quiet_failure=True):
            if time.time() - selection_start_time > 15: 
                self.logger.error(f"Timed out trying to select fusion keyword '{status_picture}'. Aborting fusion.")
                exit_fusion()
                return
            
            self.logger.debug("Keyword not found, re-clicking dropdown and waiting...")
            common.mouse_move_click(*common.scale_coordinates_1440p(730, 700))
            time.sleep(2) 

        self.logger.debug("Keyword selected, confirming...")
        common.click_matching("pictures/general/confirm_b.png")

        wait_start = time.time()
        while not (common.element_exist("pictures/mirror/restshop/fusion/bytier.png") or \
                   common.element_exist("pictures/mirror/restshop/fusion/bykeyword.png")):
            if time.time() - wait_start > 5:
                self.logger.warning("Timed out waiting for gift selection screen after confirming keyword.")
                exit_fusion()
                return
            common.sleep(0.5)
            
        common.click_matching("pictures/mirror/restshop/fusion/bytier.png")
        common.click_matching("pictures/mirror/restshop/fusion/bykeyword.png")

        while True:
            if not common.click_matching("pictures/CustomAdded1080p/mirror/general/fully_scrolled_up.png", threshold=0.95, recursive=False) and common.click_matching("pictures/mirror/restshop/scroll_bar.png", recursive=False): 
                for i in range(5):
                    common.mouse_scroll(1000)
                common.sleep(0.5)
                
            selected_gifts_coords = []
            scroll_attempts = 0
            max_scroll_attempts = 5 

            while len(selected_gifts_coords) < 3 and scroll_attempts < max_scroll_attempts:
                current_screen_gifts = self.find_gifts(statuses, excluded_statuses)
                self.logger.info(f"fuse_gifts: Loop start. Found {len(current_screen_gifts)} gifts on screen.")
                
                # Sort gifts by Y coordinate descending (bottom to top) to prioritize new gifts appearing at the bottom after scrolling
                current_screen_gifts.sort(key=lambda p: p[1], reverse=True)
                
                new_gifts_on_screen = current_screen_gifts

                self.logger.info(f"fuse_gifts: {len(new_gifts_on_screen)} new gifts available to click.")
                for x, y in new_gifts_on_screen:
                    if len(selected_gifts_coords) < 3:
                        self.logger.info(f"Clicking EGO gift at ({x}, {y}). Selected {len(selected_gifts_coords) + 1}/3.")
                        common.mouse_move_click(x, y)
                        self.logger.debug(f"Delaying for 0.5 second after clicking gift at ({x}, {y}).")
                        common.sleep(0.5) 
                        selected_gifts_coords.append((x, y))
                    else:
                        break 
                
                if len(selected_gifts_coords) >= 3:
                    break 
                
                if common.element_exist("pictures/mirror/restshop/scroll_bar.png") and \
                   not common.element_exist("pictures/CustomAdded1080p/mirror/general/fully_scrolled_down.png", quiet_failure=True):
                    self.logger.debug(f"Not enough gifts found, scrolling down. Scroll attempt {scroll_attempts + 1}/{max_scroll_attempts}.")
                    common.click_matching("pictures/mirror/restshop/scroll_bar.png") 
                    common.mouse_scroll(-1000) 
                    common.sleep(1.0) 
                    scroll_attempts += 1
                else:
                    self.logger.debug("No more scrolling possible or needed.")
                    break 

            if len(selected_gifts_coords) == 3:
                self.logger.info("3 EGO gifts selected. Attempting fusion.")
                if not self.fuse():
                    self.logger.warning("Fusion failed after selecting 3 gifts.")
                    break
                else:
                    self.logger.info("Fusion successful. Repeating process to find more gifts.")
                    common.sleep(1.0)
                    continue
            else:
                self.logger.info(f"Could not find 3 EGO gifts for fusion (found {len(selected_gifts_coords)}). Exiting fusion menu.")
                break
        
        exit_fusion()
                
    def rest_shop(self):
        """Handle rest shop activities: fusion, healing, enhancement, and buying"""
        self.logger.info("Entering rest shop logic")
        def leave_restshop():
            """Leave the restshop with proper confirmation handling"""
            self.logger.info("Leaving rest shop")
            common.mouse_move_click(*common.scale_coordinates_1080p(50,50))
            while not common.click_matching("pictures/mirror/restshop/leave.png", recursive=False):
                common.key_press("esc")
                for _ in range(5):
                    common.mouse_move_click(*common.scale_coordinates_1080p(50,50))

            if not common.element_exist("pictures/general/confirm_w.png"):
                common.mouse_move_click(*common.scale_coordinates_1080p(50,50))
                common.click_matching("pictures/mirror/restshop/leave.png")
            common.click_matching("pictures/general/confirm_w.png")
            common.click_matching("pictures/general/confirm_b.png", recursive=False)
        
        if shared_vars.skip_restshop:
            self.logger.info("Skipping rest shop as per settings")
            leave_restshop()
            return

        if not shared_vars.skip_ego_fusion:
            self.logger.info("Attempting fusion")
            self.fuse_gifts()
        
        if common.element_exist("pictures/mirror/restshop/small_not.png"):
            leave_restshop()
            return
            
        else:
            
            if not shared_vars.skip_sinner_healing:
                self.logger.info("Attempting healing")
                if not common.click_matching("pictures/mirror/restshop/heal.png", recursive=False):
                    if common.element_exist("pictures/mirror/restshop/small_not.png"):
                        leave_restshop()
                        return

                common.click_matching("pictures/mirror/restshop/heal_all.png")
                common.sleep(1)
                common.click_matching("pictures/mirror/restshop/return.png")

            if not shared_vars.skip_ego_enhancing:
                self.logger.info("Attempting enhancing")
                status = mirror_utils.get_status_gift_template(self.status)
                if status is None:
                    status = "pictures/mirror/restshop/enhance/poise_enhance.png"
                common.click_matching("pictures/mirror/restshop/enhance/enhance.png")
                if not common.click_matching("pictures/CustomAdded1080p/mirror/general/fully_scrolled_up.png", threshold=0.95, recursive=False) and common.click_matching("pictures/mirror/restshop/scroll_bar.png", recursive=False): 
                    for i in range(5):
                        common.mouse_scroll(1000)
                self.enhance_gifts(status)
                while not common.click_matching("pictures/mirror/restshop/close.png", recursive=False):
                    common.mouse_move(*common.scale_coordinates_1080p(50, 50))
                    time.sleep(0.5)

            if not shared_vars.skip_ego_buying:
                self.logger.info("Attempting buying")
                status = mirror_utils.market_choice(self.status)
                if status is None:
                    status = "pictures/mirror/restshop/market/poise_market.png"
                for _ in range(2):  
                    if common.click_matching("pictures/mirror/restshop/shop_scroll_up.png", recursive=False):  
                        for _ in range(45): 
                            common.mouse_scroll(1000)
                    for _ in range(3): 
                        market_gifts = []
                        if common.element_exist(status):
                            market_gifts += common.match_image(status)
                        if len(market_gifts):
                            market_gifts = [x for x in market_gifts if (x[0] > common.scale_x(1091) and x[0] < common.scale_x(2322)) and (x[1] > common.scale_y(434) and x[1] < common.scale_y(919))] 
                            for x,y in market_gifts:
                                offset_x, offset_y = common.scale_offset_1440p(25, 1)
                                if common.luminence(x + offset_x, y + offset_y) < 2: 
                                    continue
                                if common.element_exist("pictures/mirror/restshop/small_not.png"):
                                    break
                                common.mouse_move_click(x, y) 

                                purchase_button_visible = False
                                wait_start_time = time.time()
                                while time.time() - wait_start_time < 3: 
                                    if common.element_exist("pictures/mirror/restshop/market/purchase.png"):
                                        purchase_button_visible = True
                                        break
                                    common.sleep(0.1)

                                if purchase_button_visible:
                                    if common.click_matching("pictures/mirror/restshop/market/purchase.png", recursive=False):
                                        for _ in range(10): 
                                            if common.click_matching("pictures/general/confirm_b.png", recursive=False):
                                                break
                                            common.sleep(0.1)
                                else:
                                    self.logger.warning(f"Purchase button not found after clicking gift at ({x}, {y}). Skipping purchase.")

                        common.sleep(1)
                        if common.click_matching("pictures/mirror/restshop/shop_scroll_down.png", recursive=False):
                            for _ in range(15):
                                common.mouse_scroll(-1000) 
                        else:
                            break  
                    if common.element_exist("pictures/mirror/restshop/small_not.png"):
                        break
                    common.mouse_move_click(*common.scale_coordinates_1080p(50, 50))
                    common.sleep(1)
                    common.click_matching("pictures/mirror/restshop/market/refresh.png")
                    common.sleep(1)

        leave_restshop()

    def upgrade(self,gifts,status,shift_x,shift_y):
        """Upgrade gifts twice using power up button"""
        for x,y in gifts:
            common.mouse_move_click(x, y)
            for _ in range(2): 
                common.click_matching("pictures/mirror/restshop/enhance/power_up.png")
                if common.element_exist("pictures/mirror/restshop/enhance/more.png"): 
                    common.click_matching("pictures/mirror/restshop/enhance/cancel.png")
                    return False  
                common.click_matching("pictures/mirror/restshop/enhance/confirm.png", recursive=False)
        return True  

    def enhance_gifts(self,status):
        """Enhancement gift process"""
        self.logger.info("Starting gift enhancement")
        
        x1, y1 = common.scale_coordinates_1080p(900, 300)
        x2, y2 = common.scale_coordinates_1080p(1700, 800)
        
        attempted_gifts = []

        while(True):
            raw_gifts = common.ifexist_match(status, x1=x1, y1=y1, x2=x2, y2=y2)
            gifts = raw_gifts
            if gifts:
                gifts = [i for i in gifts if i[0] > common.scale_x(1200)] 
                
                fully_upgraded_coords = common.ifexist_match("pictures/CustomAdded1080p/mirror/general/fully_upgraded.png", 0.7, x1=x1, y1=y1, x2=x2, y2=y2)
                if fully_upgraded_coords:
                    
                    expand_left_scaled = common.scale_x_1080p(100)
                    expand_below_scaled = common.scale_y_1080p(100)
                    
                    gifts = [gift for gift in gifts if not common.enhanced_proximity_check(fully_upgraded_coords,
                                                                                         [gift], 
                                                                                         expand_left=expand_left_scaled, 
                                                                                         expand_below=expand_below_scaled,
                                                                                         use_bounding_box=False, return_bool=True)]
                
                if attempted_gifts:
                    gifts = [g for g in gifts if not common.proximity_check([g], attempted_gifts, common.scale_x_1080p(30))]

                if len(gifts):
                    if not self.upgrade(gifts,status,0,0):
                        break  
                    attempted_gifts.extend(gifts)

            raw_wordless = common.ifexist_match("pictures/mirror/restshop/enhance/wordless_enhance.png", x1=x1, y1=y1, x2=x2, y2=y2)
            wordless_gifts = raw_wordless
            if wordless_gifts:
                shift_x, shift_y = mirror_utils.enhance_shift("wordless")
                shift_x_scaled, shift_y_scaled = common.scale_offset_1440p(shift_x, shift_y)
                wordless_gifts = [i for i in wordless_gifts if common.luminence(i[0]+shift_x_scaled,i[1]+shift_y_scaled) > 22]
                
                if attempted_gifts:
                    wordless_gifts = [g for g in wordless_gifts if not common.proximity_check([g], attempted_gifts, common.scale_x_1080p(30))]

                if len(wordless_gifts):
                    if not self.upgrade(wordless_gifts,"pictures/mirror/restshop/enhance/wordless_enhance.png",shift_x,shift_y):
                        break  
                    attempted_gifts.extend(wordless_gifts)

            scrolled = False
            if common.element_exist("pictures/mirror/restshop/scroll_bar.png") and not common.element_exist("pictures/CustomAdded1080p/mirror/general/fully_scrolled.png"):
                common.click_matching("pictures/mirror/restshop/scroll_bar.png")
                for k in range(5):
                    common.mouse_scroll(-1000)
                scrolled = True
                attempted_gifts = []

            if not scrolled and not gifts and not wordless_gifts:
                break

    def event_choice(self):
        """Handle different event types and make appropriate choices"""
        self.logger.info("Handling event choice")
        if common.click_matching("pictures/events/level_up.png", recursive=False):
            self.logger.info("Event: Level Up")
            common.wait_skip("pictures/events/proceed.png")
            skill_check()

        elif common.click_matching("pictures/events/select_gain.png", recursive=False): 
            self.logger.info("Event: Select Gain")
            common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
            while(True):
                common.mouse_click()
                if common.click_matching("pictures/events/proceed.png", recursive=False):
                    break
                if common.click_matching("pictures/events/continue.png", recursive=False):
                    break
            common.sleep(1)
            if common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
                common.key_press("enter")

        elif common.click_matching("pictures/events/gain_check.png", recursive=False): 
            self.logger.info("Event: Gain Check")
            common.wait_skip("pictures/events/proceed.png")
            skill_check()

        elif common.click_matching("pictures/events/gain_check_o.png", recursive=False): 
            self.logger.info("Event: Gain Check (Alt)")
            common.wait_skip("pictures/events/proceed.png")
            skill_check()

        elif common.click_matching("pictures/events/gain_gift.png", recursive=False): 
            self.logger.info("Event: Gain Gift")
            common.wait_skip("pictures/events/proceed.png")
            if common.element_exist("pictures/events/skip.png"):
                common.click_skip(15)
                self.event_choice()

        elif common.element_exist("pictures/events/select_right.png"): 
            self.logger.info("Event: Select Right")
            if common.click_matching("pictures/events/helterfly.png", recursive=False):
                pass
            elif common.click_matching("pictures/events/midwinter.png", recursive=False):
                pass
            common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
            while(True):
                common.mouse_click()
                if common.click_matching("pictures/events/proceed.png", recursive=False):
                    break
                if common.click_matching("pictures/events/continue.png", recursive=False):
                    break
            common.sleep(1)
            if common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
                common.key_press("enter")

        elif common.click_matching("pictures/events/win_battle.png", recursive=False): 
            self.logger.info("Event: Win Battle")
            common.wait_skip("pictures/events/commence_battle.png")
        
        elif common.element_exist("pictures/events/skill_check.png"): 
            self.logger.info("Event: Skill Check")
            skill_check()

        elif common.click_matching("pictures/mirror/events/kqe.png", recursive=False): 
            self.logger.info("Event: KQE")
            common.wait_skip("pictures/events/continue.png")
            if common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
                common.click_matching("pictures/general/confirm_b.png")
        
        elif common.click_matching("pictures/CustomAdded1080p/mirror/events/slot_machine.png", recursive=False): 
            self.logger.info("Event: Slot Machine")
            pass

        elif common.click_matching("pictures/events/proceed.png", recursive=False):
            pass

        elif common.click_matching("pictures/events/continue.png", recursive=False):
            pass

        elif not battle_check():
            battle()
            check_loading()

    def victory(self):
        """Handle victory screen and claim rewards"""
        common.click_matching("pictures/general/confirm_w.png", recursive=False)
        common.click_matching("pictures/general/beeg_confirm.png")
        common.mouse_move(*common.scale_coordinates_1080p(200,200))
        common.click_matching("pictures/general/claim_rewards.png")
        common.sleep(1)
        common.click_matching("pictures/general/md_claim.png")
        common.sleep(0.5)
        if common.click_matching("pictures/general/confirm_w.png", recursive=False):
            while(True):
                if common.element_exist("pictures/mirror/general/weekly_reward.png"): 
                    common.key_press("enter")
                if common.element_exist("pictures/mirror/general/pass_level.png"): 
                    common.key_press("enter")
                    break
            if "floor5" not in self.run_stats["floor_times"]:
                self.run_stats["floor_times"]["floor5"] = time.time() - self.run_stats["start_time"]  
            post_run_load()
        else: 
            common.click_matching("pictures/general/to_window.png")
            common.click_matching("pictures/general/confirm_w.png")
            post_run_load()
            self.logger.error("Insufficient modules")
            sys.exit(0)

    def defeat(self):
        """Handle defeat screen and cleanup"""
        self.logger.info("Defeat detected. Checking for retry or forfeit options...")
        while True:
            retry_img = None
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.6, quiet_failure=True):
                retry_img = "pictures/CustomAdded1080p/mirror/general/retrystage.png"
            elif common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.jpg", threshold=0.6, quiet_failure=True):
                retry_img = "pictures/CustomAdded1080p/mirror/general/retrystage.jpg"
            if retry_img:
                retry_limit = getattr(shared_vars, 'retry_count', 0)
                if self.retries_used < retry_limit:
                    self.logger.info(f"Retry stage button detected. Retrying ({self.retries_used + 1}/{retry_limit})...")

                    retry_start = time.time()
                    while time.time() - retry_start < 15:
                        if common.click_matching(retry_img, threshold=0.6, quiet_failure=True):
                            
                            wait_start = time.time()
                            while time.time() - wait_start < 4:
                                if common.click_matching("pictures/general/confirm_w.png", threshold=0.6, quiet_failure=True):
                                    self.retries_used += 1
                                    common.sleep(3) 
                                    return False 
                                common.sleep(0.2)
                        common.sleep(0.5)        
                else:
                    self.logger.debug("Retry button found but retries exhausted/disabled.")
                    pass
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.6, quiet_failure=True):
                self.logger.info("Battle defeat detected. Proceeding to forfeit...")
                break 
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.6, quiet_failure=True):
                self.logger.info("Accept defeat detected. Proceeding to forfeit...")
                break 
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.jpg", threshold=0.6, quiet_failure=True):
                self.logger.info("Accept defeat detected (JPG). Proceeding to forfeit...")
                break 
            
            self.logger.debug("Waiting for retry/forfeit buttons...")
            common.sleep(0.5)

        self.logger.info("Attempting to click Accept Defeat...")
        start_time = time.time()
        while True:
            if time.time() - start_time > 30:
                self.logger.warning("Timed out waiting for confirm_w after accept defeat")
                break

            accept_clicked = False
            if common.click_matching("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.5, quiet_failure=True, recursive=False, grayscale=True):
                self.logger.info("Clicked acceptdefeat button (PNG)")
                accept_clicked = True
            elif common.click_matching("pictures/CustomAdded1080p/mirror/general/acceptdefeat.jpg", threshold=0.5, quiet_failure=True, recursive=False, grayscale=True):
                self.logger.info("Clicked acceptdefeat button (JPG)")
                accept_clicked = True
            else:
                
                matches = common.match_image("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.4, quiet_failure=True, enable_scaling=True, grayscale=True)
                if not matches:
                    matches = common.match_image("pictures/CustomAdded1080p/mirror/general/acceptdefeat.jpg", threshold=0.4, quiet_failure=True, enable_scaling=True, grayscale=True)
                
                if matches:
                    common.mouse_move_click(matches[0][0], matches[0][1])
                    self.logger.info("Clicked acceptdefeat button (scaled)")
                    accept_clicked = True
                else:
                    
                    retry_matches = common.match_image("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.5, quiet_failure=True, enable_scaling=True, grayscale=True)
                    if not retry_matches:
                        retry_matches = common.match_image("pictures/CustomAdded1080p/mirror/general/retrystage.jpg", threshold=0.5, quiet_failure=True, enable_scaling=True, grayscale=True)
                        
                    if retry_matches:

                        rx, ry = retry_matches[0]
                        offset_x = common.scale_x_1080p(350)
                        common.mouse_move_click(rx + offset_x, ry)
                        self.logger.info("Clicked estimated acceptdefeat position (relative to retrystage)")
                        accept_clicked = True
                    else:
                        self.logger.debug("acceptdefeat button not found")

            if accept_clicked:
                self.logger.debug("Waiting for confirm_w...")
                wait_lit_start = time.time()
                while time.time() - wait_lit_start < 2:
                    if common.click_matching("pictures/general/confirm_w.png", threshold=0.6, quiet_failure=True, recursive=False):
                        self.logger.info("Clicked confirm_w")
                        break
                    else:
                        self.logger.debug("confirm_w not found yet")
                    common.sleep(0.2)
                else:
                    common.sleep(0.5)
                    continue
                break

            common.sleep(0.5)

        common.sleep(1) 

        common.click_matching("pictures/general/beeg_confirm.png", quiet_failure=True)
        common.mouse_move(*common.scale_coordinates_1080p(200,200))
        common.click_matching("pictures/general/claim_rewards.png", quiet_failure=True)
        common.sleep(1)

        if getattr(shared_vars, 'claim_on_defeat', False):
            self.logger.info("Claiming rewards on defeat (Enabled).")
            common.click_matching("pictures/general/md_claim.png")
            if common.click_matching("pictures/general/confirm_w.png", recursive=False):

                end_time = time.time() + 5
                while time.time() < end_time:
                    if common.element_exist("pictures/mirror/general/weekly_reward.png"):
                        common.key_press("enter")
                    if common.element_exist("pictures/mirror/general/pass_level.png"):
                        common.key_press("enter")
                    if common.element_exist("pictures/general/module.png"):
                        break
                    common.sleep(0.5)
        else:
            self.logger.info("Giving up without claiming rewards (Disabled).")
            common.click_matching("pictures/general/give_up.png")
            common.click_matching("pictures/general/confirm_w.png")
        post_run_load()
        return True 
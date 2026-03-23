import sys
import os
import logging
import time
import common
import copy
import shared_vars
import mirror_utils
from core import (skill_check, battle_check, battle, check_loading,
                  post_run_load, refill_enkephalin, navigate_to_md)

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        folder_path = os.path.dirname(os.path.abspath(__file__))
        return (os.path.dirname(folder_path) if os.path.basename(folder_path) == 'src' 
                else folder_path)

BASE_PATH = get_base_path()
sys.path.append(os.path.join(BASE_PATH, "src"))
os.chdir(BASE_PATH)

logger = logging.getLogger(__name__)

_orb_descriptor_cache = {}

class Mirror:
    def __init__(self, status):
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
            "packs": [],
            "packs_by_floor": {}
        }
        self.current_floor_tracker = None
        self.retries_used = 0

    @staticmethod
    def floor_id():
        import cv2
        screenshot = common.capture_screen()

        if common.element_exist("pictures/CustomAdded1080p/battle/battle_in_progress.png", quiet_failure=True, screenshot=screenshot):
            return ""

        screen = screenshot
        if len(screen.shape) == 2:
            screen = cv2.cvtColor(screen, cv2.COLOR_GRAY2BGR)

        try:
            import re
            import easyocr
            import numpy as np
            h = screen.shape[0]
            y1, y2 = round(130 * h / 1080), round(200 * h / 1080)
            title_strip = screen[y1:y2, :]
            ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            texts = ocr_reader.readtext(title_strip, detail=0)
            combined = " ".join(texts)
            m = re.search(r'FLOOR\s+(\d)', combined, re.IGNORECASE)
            if m:
                floor_num = int(m.group(1))
                if 1 <= floor_num <= 5:
                    logger.info(f"OCR floor detected: floor{floor_num} (from '{combined}')")
                    return f"floor{floor_num}"
            logger.warning(f"OCR floor detection failed (text='{combined}'), trying visual fallback")
        except Exception as e:
            logger.warning(f"OCR floor error: {e}, trying visual fallback")

        threshold = 0.73
        best_floor = None
        best_score = 0.0

        for i in range(1, 6):
            floor_name = f"floor{i}"
            template_path = f"pictures/mirror/packs/{floor_name}.png"
            full_path = common.resource_path(template_path)

            cache_key = (full_path, cv2.IMREAD_COLOR)
            if cache_key in common._template_cache:
                template = common._template_cache[cache_key]
            else:
                try:
                    import numpy as np
                    raw = np.fromfile(full_path, dtype=np.uint8)
                    template = cv2.imdecode(raw, cv2.IMREAD_COLOR)
                except Exception:
                    template = None
                if template is None:
                    continue
                common._template_cache[cache_key] = template

            base_w, base_h = common.get_template_reference_resolution(full_path)
            scale = min(common.EXPECTED_WIDTH / base_w, common.EXPECTED_HEIGHT / base_h)
            if scale != 1.0:
                scaled = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_LINEAR)
            else:
                scaled = template

            if scaled.shape[0] > screen.shape[0] or scaled.shape[1] > screen.shape[1]:
                continue

            res = cv2.matchTemplate(screen, scaled, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)

            logger.debug(f"Floor {i} visual confidence: {max_val:.4f}")

            if max_val >= threshold and max_val > best_score:
                best_score = max_val
                best_floor = floor_name

        if best_floor:
            logger.info(f"Visual floor detected: {best_floor} (confidence: {best_score:.4f})")
            return best_floor

        logger.warning("Both OCR and visual floor detection failed")
        return ""

    def is_pack_screen(self):
        if common.element_exist("pictures/CustomAdded1080p/battle/battle_in_progress.png", quiet_failure=True):
            return False
        if common.element_exist("pictures/mirror/restshop/shop.png", quiet_failure=True):
            return False
        if common.element_exist("pictures/mirror/restshop/super_shop.png", quiet_failure=True):
            return False
        if common.element_exist("pictures/CustomAdded1080p/mirror/general/enhance_ego_gift_page.png", quiet_failure=True):
            return False

        threshold = 0.82

        floor_found = False
        if self.current_floor_tracker:
            if common.element_exist(f'pictures/mirror/packs/{self.current_floor_tracker}.png', threshold, no_grayscale=True, quiet_failure=True):
                floor_found = True
        if not floor_found:
            for i in range(1, 6):
                floor_name = f"floor{i}"
                if floor_name == self.current_floor_tracker:
                    continue
                if common.element_exist(f'pictures/mirror/packs/{floor_name}.png', threshold, no_grayscale=True, quiet_failure=True):
                    floor_found = True
                    break

        if not floor_found:
            return common.element_exist("pictures/CustomAdded1080p/mirror/packs/inpack.png", quiet_failure=True, threshold=0.80)

        difficulty_found = (
            common.element_exist("pictures/mirror/packs/floor_hard.png", quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/packs/floor_normal.png", quiet_failure=True)
        )

        if shared_vars.hard_mode:
            toggle_found = common.element_exist("pictures/mirror/packs/hard_toggle.png", quiet_failure=True)
        else:
            toggle_found = common.element_exist("pictures/CustomAdded1080p/mirror/packs/normal_toggle.png", quiet_failure=True)

        return difficulty_found and toggle_found

    @staticmethod
    def set_sinner_order(status):
        if mirror_utils.squad_choice(status) is None:
            return common.squad_order("default")
        else:
            return common.squad_order(status)

    def setup_mirror(self):
        
        if (common.element_exist("pictures/mirror/general/danteh.png", quiet_failure=True) or
            common.element_exist("pictures/battle/winrate.png", quiet_failure=True) or
            common.element_exist("pictures/battle/winrate_wave.png", quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/battle/setting_cog.png", quiet_failure=True) or
            common.element_exist("pictures/events/skip.png", quiet_failure=True) or
            common.element_exist("pictures/mirror/restshop/shop.png", quiet_failure=True) or
            self.is_pack_screen() or
            common.element_exist("pictures/mirror/general/reward_select.png", quiet_failure=True) or
            common.element_exist("pictures/mirror/general/encounter_reward.png", quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.72, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.72, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/general/squads/clear_selection.png", quiet_failure=True)):
             self.logger.info("Detected existing run state, skipping setup.")
             return

        refill_enkephalin()

        if not (common.element_exist("pictures/general/resume.png", quiet_failure=True)
                or common.element_exist("pictures/mirror/general/md_enter.png", quiet_failure=True)):
            navigate_to_md()
        self.logger.info("Setting up Mirror Dungeon run...")

        setup_start_time = time.time()
        while time.time() - setup_start_time < 30:
            if common.element_exist("pictures/mirror/general/md_enter.png", quiet_failure=True):
                common.sleep(0.8)
                if common.click_matching("pictures/mirror/general/md_enter.png", recursive=False):
                    break

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
            deadline = time.time() + 45
            while not common.element_exist("pictures/CustomAdded1080p/general/squads/squad_select.png"):
                if time.time() > deadline:
                    self.logger.warning("setup_mirror: squad_select not found after 45s, continuing anyway")
                    break
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
        run_complete = 0
        win_flag = 0
        if (common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.72, quiet_failure=True) or 
            common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.72, quiet_failure=True) or
            common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.72, quiet_failure=True)):
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

        elif common.element_exist("pictures/battle/winrate.png") or common.element_exist("pictures/battle/winrate_wave.png"):
            self.logger.info("Battle winrate button detected")
            battle()
            check_loading()

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

        elif common.element_exist("pictures/CustomAdded1080p/mirror/general/enhance_ego_gift_page.png", quiet_failure=True):
            self.logger.info("Enhancement screen detected")
            import mirror_utils
            status = mirror_utils.get_status_gift_template(self.status)
            if status is None:
                status = "pictures/mirror/restshop/enhance/poise_enhance.png"
            self.enhance_gifts(status)

        elif self.is_pack_screen(): 
            self.logger.info("Pack selection detected")
            self.pack_selection()

        elif common.element_exist("pictures/mirror/general/event_effect.png"):
            self.logger.info("Event effect selection detected")
            found = common.match_image("pictures/mirror/general/event_select.png", no_grayscale=True)
            if found:
                x,y = common.random_choice(found)
                common.mouse_move_click(x, y)
                common.sleep(1)
                common.click_matching("pictures/general/confirm_b.png")
            else:
                self.logger.warning("event_select.png not found, skipping event effect")
            
        elif common.element_exist("pictures/general/module.png") or common.element_exist("pictures/mirror/general/md_enter.png"):
            self.logger.info("Main menu detected in loop. Forcing run completion.")
            return 0, 1, self.run_stats

        return self.check_run()

    def grace_of_stars(self):

        if not hasattr(self, '_grace_coords_cache'):
            grace_config = shared_vars.ConfigCache.get_config("grace_selection")
            grace_order = grace_config.get('order', {})
            grace_upgrades = grace_config.get('upgrades', {})
            grace_coordinates = shared_vars.ScaledCoordinates.get_scaled_coords("grace_of_stars")

            self._grace_coords_cache = []
            if grace_order:
                sorted_graces = sorted(grace_order.items(), key=lambda x: x[1])
                for name, _ in sorted_graces:
                    if name in grace_coordinates:
                        upgrade = grace_upgrades.get(name, "none")
                        upg_pos = grace_coordinates.get(f"{name}|{upgrade}") if upgrade != "none" else None
                        self._grace_coords_cache.append((grace_coordinates[name], upg_pos))

        self.logger.info(f"Selecting Grace of Stars blessings...")
        for (x, y), upg_pos in self._grace_coords_cache:
            common.mouse_move_click(x, y)
            common.sleep(0.3)
            if upg_pos:
                self.logger.info(f"Upgrading grace at {upg_pos}")
                common.mouse_move_click(*upg_pos)
                common.sleep(0.1)

        common.sleep(0.5)
        common.click_matching("pictures/CustomAdded1080p/mirror/general/Enter.png")
        common.sleep(1)
        common.click_matching("pictures/CustomAdded1080p/mirror/general/Confirm.png")
        wait_start = time.time()
        while(not common.element_exist("pictures/mirror/general/gift_select.png")):
            if time.time() - wait_start > 5:
                self.logger.warning("Timed out waiting for gift selection, assuming it was skipped because no graces were selected.")
                return
            common.sleep(0.5)
    
    def gift_selection(self):
        self.logger.info("Starting EGO gift selection")
        
        if common.click_matching("pictures/mirror/general/gift_search_enabled.png", 0.58, recursive=False, enable_scaling=True, no_grayscale=True):
            self.logger.info("Gift search was enabled, turning it off.")
        else:
            pass

        gift = mirror_utils.gift_choice(self.status)
        

        clicked_gift = False
        _matches = common.match_image(gift, 0.8)
        if _matches:
            best = min(_matches, key=lambda m: m[1])
            common.mouse_move_click(best[0], best[1])
            clicked_gift = True
        else:
            self.logger.info(f"Gift {gift} not found immediately, scrolling...")
            found = common.match_image("pictures/mirror/general/gift_select.png")
            if found:
                x,y = found[0]
                offset_x, offset_y = common.scale_offset_1440p(-1365, 50)
                common.mouse_move(x + offset_x, y + offset_y)
                

                for i in range(7):
                    common.mouse_scroll(-1000)
                    common.sleep(0.5)
                    _matches = common.match_image(gift, 0.8)
                    if _matches:
                        best = min(_matches, key=lambda m: m[1])
                        common.mouse_move_click(best[0], best[1])
                        clicked_gift = True
                        break

                if not clicked_gift:
                    self.logger.info("Gift not found after scrolling down, scrolling up...")
                    for i in range(10):
                        common.mouse_scroll(1000)
                        common.sleep(0.5)
                        _matches = common.match_image(gift, 0.8)
                        if _matches:
                            best = min(_matches, key=lambda m: m[1])
                            common.mouse_move_click(best[0], best[1])
                            clicked_gift = True
                            break

        found = common.match_image("pictures/mirror/general/gift_select.png")
        if found:
            x,y = found[0]
            _, offset_y = common.scale_offset_1440p(0, 235)
            y = y + offset_y
            _, offset1 = common.scale_offset_1440p(0, 190)
            _, offset2 = common.scale_offset_1440p(0, 380)
            gift_pos = [y, y+offset1, y+offset2]

            initial_gift_coords = gift_pos if self.status not in ["sinking", "bleed"] else [*gift_pos[1:], gift_pos[0]]

            for i in initial_gift_coords:
                scaled_x, _ = common.scale_coordinates_1440p(1640, 0)
                common.mouse_move_click(scaled_x, i)
        
        common.sleep(0.2)
        common.key_press("enter")
        wait_start = time.time()
        while not common.element_exist("pictures/mirror/general/ego_gift_get.png"):
            if time.time() - wait_start > 2.0:
                self.logger.info("Waiting for gift confirmation... Retrying selection.")
                
                if clicked_gift:
                    _matches = common.match_image(gift, 0.8)
                    if _matches:
                        best = min(_matches, key=lambda m: m[1])
                        common.mouse_move_click(best[0], best[1])

                found = common.match_image("pictures/mirror/general/gift_select.png")
                if found:
                    x,y = found[0]
                    _, offset_y = common.scale_offset_1440p(0, 235)
                    y = y + offset_y
                    _, offset1 = common.scale_offset_1440p(0, 190)
                    _, offset2 = common.scale_offset_1440p(0, 380)
                    gift_pos = [y, y+offset1, y+offset2]

                    initial_gift_coords = gift_pos if self.status not in ["sinking", "bleed"] else [*gift_pos[1:], gift_pos[0]]

                    for i in initial_gift_coords:
                        scaled_x, _ = common.scale_coordinates_1440p(1640, 0)
                        common.mouse_move_click(scaled_x, i)

                common.key_press("enter")
                wait_start = time.time()
            common.sleep(0.5)
        for i in range(3):
            if common.element_exist("pictures/mirror/general/ego_gift_get.png"): 
                common.key_press("enter")
                common.sleep(0.5)
        check_loading()

    def initial_squad_selection(self):
        self.logger.info("Performing initial squad selection")
        status = mirror_utils.squad_choice(self.status)
        if status is None:
            common.key_press("enter")
            self.status = "poise"
            while(not common.element_exist("pictures/CustomAdded1080p/mirror/general/grace_menu.png")): 
                common.click_matching("pictures/CustomAdded1080p/general/confirm.png", recursive=False, mousegoto200=True)
            return
        
        found = common.match_image("pictures/CustomAdded1080p/general/squads/squad_select.png")
        if not found:
            self.logger.warning("squad_select.png not found, skipping squad panel scroll")
            common.key_press("enter")
            while not common.element_exist("pictures/CustomAdded1080p/mirror/general/grace_menu.png"):
                common.click_matching("pictures/CustomAdded1080p/general/confirm.png", recursive=False, mousegoto200=True)
            return
        x,y = found[0]
        offset_x, offset_y = common.scale_offset_1440p(90, 90)
        common.mouse_move(x+offset_x,y+offset_y)
        if not common.click_matching(status, recursive=False):
            for _ in range(30):
                common.mouse_scroll(1000)

            
            for _ in range(4):
                if not common.element_exist(status):
                    for _ in range(7):
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
            common.sleep(0.2)
            common.click_matching("pictures/CustomAdded1080p/general/confirm.png", recursive=False, mousegoto200=True)

    def _fast_scan_packs(self, floor_char, screenshot, exception_packs, floor_priorities,
                          min_x_scaled, min_y_scaled, max_x_scaled, max_y_scaled):
        import cv2
        import numpy as np

        floor_dir = os.path.join(BASE_PATH, f"pictures/mirror/packs/f{floor_char}")
        if not os.path.exists(floor_dir):
            return [], {}, {}, [], 0

        actual_h, actual_w = screenshot.shape[:2]

        if actual_w != common.EXPECTED_WIDTH or actual_h != common.EXPECTED_HEIGHT:
            self.logger.warning(f"Screenshot size {actual_w}x{actual_h} differs from EXPECTED {common.EXPECTED_WIDTH}x{common.EXPECTED_HEIGHT}. recomputing crop bounds")
            min_y_scaled = round(100 * actual_h / 1080)
            max_y_scaled = round(980 * actual_h / 1080)
            min_x_scaled = round(50 * actual_w / 1920)
            max_x_scaled = round(1870 * actual_w / 1920)

        self.logger.debug(f"Screenshot: {actual_w}x{actual_h} | crop: x={min_x_scaled}-{max_x_scaled}, y={min_y_scaled}-{max_y_scaled}")

        base_scale = min(actual_w / 2560.0, actual_h / 1440.0)
        scale_candidates = [base_scale * adj for adj in (1.00, 1.33, 0.87)]

        crop = screenshot[min_y_scaled:max_y_scaled, min_x_scaled:max_x_scaled]
        gray_crop = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if len(crop.shape) == 3 else crop.copy()

        if shared_vars.debug_image_matches:
            debug_path = os.path.join(BASE_PATH, f"logs/pack_scan_debug_f{floor_char}.png")
            cv2.imwrite(debug_path, screenshot)
            crop_debug_path = os.path.join(BASE_PATH, f"logs/pack_scan_crop_f{floor_char}.png")
            cv2.imwrite(crop_debug_path, crop)
            self.logger.info(f"Debug screenshot saved: {debug_path} | crop saved: {crop_debug_path} | crop shape: {crop.shape}")

        best_per_coord = {}
        excepted_visible_count = 0

        all_packs = [f for f in os.listdir(floor_dir) if f.endswith(".png")]
        priority_names = set(floor_priorities.keys()) if floor_priorities else set()
        excepted_names  = set(exception_packs) if exception_packs else set()
        def _pack_sort_key(fname):
            n = fname[:-4]
            if n in priority_names: return 0
            if n in excepted_names:  return 2
            return 1
        all_packs.sort(key=_pack_sort_key)

        for pack_file in all_packs:
            pack_name = pack_file.replace(".png", "")
            pack_rel_path = f"pictures/mirror/packs/f{floor_char}/{pack_file}"
            pack_abs_path = common.resource_path(pack_rel_path)
            is_excepted = pack_name in exception_packs

            threshold_adj = common.get_total_threshold_adjustment(pack_rel_path)

            gray_key = (pack_abs_path, cv2.IMREAD_GRAYSCALE)
            tmpl_gray_orig = common._template_cache.get(gray_key)
            if tmpl_gray_orig is None:
                try:
                    with open(pack_abs_path, 'rb') as _f:
                        raw = np.frombuffer(_f.read(), dtype=np.uint8)
                    tmpl_gray_orig = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
                except Exception as e:
                    self.logger.warning(f"Failed to load template for pack '{pack_name}': {e}")
                    tmpl_gray_orig = None
                if tmpl_gray_orig is not None:
                    common._template_cache[gray_key] = tmpl_gray_orig

            if tmpl_gray_orig is None:
                self.logger.warning(f"Template returned None for pack '{pack_name}', skipping")
                continue

            def _extract_matches_scored(res, thresh, box_w, box_h):
                locs = np.where(res >= thresh)
                if not locs[0].size:
                    return []
                boxes = np.array([
                    [int(x), int(y), int(x + box_w), int(y + box_h)]
                    for x, y in zip(locs[1], locs[0])
                ])
                kept = common.non_max_suppression_fast(boxes)
                out = []
                for b in kept:
                    cx = int((b[0] + b[2]) / 2) + min_x_scaled
                    cy = int((b[1] + b[3]) / 2) + min_y_scaled
                    score = float(np.max(res[b[1]:b[3], b[0]:b[2]]))
                    out.append(((cx, cy), score))
                return out

            def _multiscale_match(tmpl_orig, search_img):
                best_res, best_score, best_th, best_tw = None, 0.0, 0, 0
                for sf in scale_candidates:
                    t = cv2.resize(tmpl_orig, None, fx=sf, fy=sf, interpolation=cv2.INTER_LINEAR) if sf != 1.0 else tmpl_orig
                    if t.shape[0] > search_img.shape[0] or t.shape[1] > search_img.shape[1]:
                        continue
                    res = cv2.matchTemplate(search_img, t, cv2.TM_CCOEFF_NORMED)
                    s = float(res.max()) if res.size > 0 else 0.0
                    if s > best_score:
                        best_score, best_res, best_th, best_tw = s, res, t.shape[0], t.shape[1]
                return best_res, best_score, best_th, best_tw

            g_res, best_score, g_th, g_tw = _multiscale_match(tmpl_gray_orig, gray_crop)
            coord_scores = []
            if g_res is not None:
                if is_excepted:
                    if _extract_matches_scored(g_res, 0.55 + threshold_adj, g_tw, g_th):
                        excepted_visible_count += 1
                        self.logger.debug(f"Excepted pack visible (score>{0.55+threshold_adj:.2f}), skipping: {pack_name}")
                    else:
                        self.logger.debug(f"Excepted pack not visible (score={best_score:.4f}), skipping: {pack_name}")
                    continue
                coord_scores = (_extract_matches_scored(g_res, 0.65 + threshold_adj, g_tw, g_th) or
                                _extract_matches_scored(g_res, 0.50 + threshold_adj, g_tw, g_th))
            elif is_excepted:
                self.logger.debug(f"Excepted pack skipped (template too large for crop): {pack_name}")
                continue

            if not coord_scores:
                self.logger.debug(f"Pack not detected: {pack_name} | score: {best_score:.4f}")
            for coord, score in coord_scores:
                existing = best_per_coord.get(coord)
                if existing is None or score > existing[0]:
                    best_per_coord[coord] = (score, pack_name)

        coords_by_score = sorted(best_per_coord.keys(), key=lambda c: -best_per_coord[c][0])
        kept = {}
        for coord in coords_by_score:
            cx, cy = coord
            if not any(abs(cx - kx) < 60 and abs(cy - ky) < 60 for kx, ky in kept):
                kept[coord] = best_per_coord[coord]
        best_per_coord = kept

        already_found_names = {v[1] for v in best_per_coord.values()}
        if shared_vars.good_pc_mode and len(best_per_coord) < 5:
            self.logger.debug(f"CCOEFF found {len(best_per_coord)} packs. Running ORB secondary scan")
            try:
                orb = cv2.ORB_create(nfeatures=500)
                bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
                kp_crop, des_crop = orb.detectAndCompute(gray_crop, None)
                if des_crop is not None:
                    orb_candidates = {}
                    crop_h, crop_w = gray_crop.shape[:2]
                    for pack_file in all_packs:
                        pack_name = pack_file.replace(".png", "")
                        if pack_name in exception_packs or pack_name in already_found_names:
                            continue
                        pack_abs_path = common.resource_path(f"pictures/mirror/packs/f{floor_char}/{pack_file}")
                        cached = _orb_descriptor_cache.get(pack_abs_path)
                        if cached is None:
                            gray_key = (pack_abs_path, cv2.IMREAD_GRAYSCALE)
                            tmpl_orb = common._template_cache.get(gray_key)
                            if tmpl_orb is None:
                                try:
                                    with open(pack_abs_path, 'rb') as _f:
                                        raw = np.frombuffer(_f.read(), dtype=np.uint8)
                                    tmpl_orb = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
                                except Exception:
                                    continue
                                if tmpl_orb is None:
                                    continue
                                common._template_cache[gray_key] = tmpl_orb
                            kp_tmpl, des_tmpl = orb.detectAndCompute(tmpl_orb, None)
                            if des_tmpl is None:
                                continue
                            tmpl_h, tmpl_w = tmpl_orb.shape[:2]
                            _orb_descriptor_cache[pack_abs_path] = (kp_tmpl, des_tmpl, tmpl_h, tmpl_w)
                            cached = (kp_tmpl, des_tmpl, tmpl_h, tmpl_w)
                        kp_tmpl, des_tmpl, tmpl_h, tmpl_w = cached
                        matches = bf.match(des_tmpl, des_crop)
                        good = [m for m in matches if m.distance < 50]
                        if len(good) < 4:
                            continue
                        pts1 = np.float32([kp_tmpl[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
                        pts2 = np.float32([kp_crop[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
                        H, mask = cv2.findHomography(pts1, pts2, cv2.RANSAC, 5.0)
                        if H is None or mask is None:
                            continue
                        inliers = int(mask.sum())
                        if inliers < 15:
                            continue
                        proj = cv2.perspectiveTransform(np.float32([[tmpl_w / 2, tmpl_h / 2]]).reshape(-1, 1, 2), H)
                        crop_px = int(proj[0][0][0])
                        crop_py = int(proj[0][0][1])
                        if not (0 <= crop_px <= crop_w and crop_h * 0.30 <= crop_py <= crop_h * 0.85):
                            continue
                        px = crop_px + min_x_scaled
                        py = crop_py + min_y_scaled
                        coord = (px, py)
                        existing = orb_candidates.get(coord)
                        if existing is None or inliers > existing[0]:
                            orb_candidates[coord] = (inliers, pack_name)

                    for coord, (inliers, pack_name) in sorted(orb_candidates.items(), key=lambda x: -x[1][0]):
                        cx, cy = coord
                        if any(abs(cx - kx) < 80 and abs(cy - ky) < 80 for kx, ky in best_per_coord):
                            continue
                        if not any(abs(cx - ox) < 80 and abs(cy - oy) < 80
                                   for ox, oy in [c for c in best_per_coord if c != coord]):
                            self.logger.debug(f"ORB detected: {pack_name} at {coord} ({inliers} inliers)")
                            best_per_coord[coord] = (inliers / 200.0, pack_name)
            except Exception as e:
                self.logger.warning(f"ORB secondary scan failed: {e}")

        has_unnamed = any(v[1] == "unknown_pack" for v in best_per_coord.values())
        if len(best_per_coord) < 5 or has_unnamed:
            self.logger.debug(f"Template+ORB found {len(best_per_coord)} packs (unnamed: {has_unnamed}). Running OCR fallback.")
            try:
                import easyocr
                from rapidfuzz import process, fuzz

                if getattr(self, '_ocr_unavailable', False):
                    raise RuntimeError("OCR previously failed to initialize, skipping")

                inpack_path = common.resource_path("pictures/CustomAdded1080p/mirror/packs/inpack.png")
                inpack_tmpl = None
                try:
                    with open(inpack_path, 'rb') as _f:
                        raw = np.frombuffer(_f.read(), dtype=np.uint8)
                    inpack_tmpl = cv2.imdecode(raw, cv2.IMREAD_GRAYSCALE)
                except Exception:
                    pass

                if inpack_tmpl is not None:
                    gray_ss = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY) if len(screenshot.shape) == 3 else screenshot
                    res_ip = cv2.matchTemplate(gray_ss, inpack_tmpl, cv2.TM_CCOEFF_NORMED)
                    ip_locs = np.where(res_ip >= 0.75)
                    if ip_locs[0].size:
                        ih, iw = inpack_tmpl.shape[:2]
                        ip_boxes = np.array([
                            [int(x), int(y), int(x + iw), int(y + ih)]
                            for x, y in zip(ip_locs[1], ip_locs[0])
                        ])
                        ip_kept = common.non_max_suppression_fast(ip_boxes)

                        actual_h, actual_w = screenshot.shape[:2]
                        name_y1 = round(660 * actual_h / 1080)
                        name_y2 = round(720 * actual_h / 1080)
                        click_y_offset = round(150 * actual_h / 1080)
                        half_ocr_w = round(200 * actual_w / 1920)

                        if not hasattr(self, '_ocr_reader') or self._ocr_reader is None:
                            self.logger.info("Initializing OCR reader (first use)")
                            try:
                                self._ocr_reader = easyocr.Reader(['en'], gpu=False, verbose=False)
                            except Exception as ocr_init_e:
                                self.logger.warning(f"OCR reader init failed, disabling for this session: {ocr_init_e}")
                                self._ocr_unavailable = True
                                raise

                        known_names = [f[:-4] for f in os.listdir(floor_dir) if f.endswith(".png")]

                        sorted_ip = sorted(ip_kept, key=lambda b: int((b[0] + b[2]) / 2))
                        ip_cxs = [int((b[0] + b[2]) / 2) for b in sorted_ip]

                        for idx, b in enumerate(sorted_ip):
                            ip_cx = ip_cxs[idx]
                            ip_cy = int((b[1] + b[3]) / 2)

                            if any(abs(ip_cx - kx) < 80 for kx, ky in best_per_coord):
                                continue

                            left_mid  = (ip_cxs[idx - 1] + ip_cx) // 2 if idx > 0 else 0
                            right_mid = (ip_cx + ip_cxs[idx + 1]) // 2 if idx < len(ip_cxs) - 1 else actual_w
                            sx1 = max(left_mid, ip_cx - half_ocr_w)
                            sx2 = min(right_mid, ip_cx + half_ocr_w)
                            strip = screenshot[name_y1:name_y2, sx1:sx2]
                            ocr_texts = self._ocr_reader.readtext(strip, detail=0)
                            raw_text = " ".join(ocr_texts).strip()

                            click_cy = ip_cy + click_y_offset
                            coord = (ip_cx, click_cy)
                            if raw_text and known_names:
                                match = process.extractOne(raw_text, known_names, scorer=fuzz.partial_ratio)
                                if match and match[1] >= 70:
                                    pack_name = match[0]
                                    if pack_name not in exception_packs:
                                        best_per_coord[coord] = (match[1] / 100.0, pack_name)
                                        self.logger.info(f"OCR detected: '{pack_name}' at x={ip_cx} ('{raw_text}', {match[1]:.0f}%)")
                                    else:
                                        self.logger.debug(f"OCR detected excepted pack '{pack_name}' at x={ip_cx}, skipping")
                                else:
                                    best_per_coord[coord] = (0.1, "unknown_pack")
                                    self.logger.info(f"OCR no match at x={ip_cx}: '{raw_text}'")
                            else:
                                best_per_coord[coord] = (0.1, "unknown_pack")
                                self.logger.info(f"OCR empty at x={ip_cx}")
            except Exception as e:
                self.logger.warning(f"OCR fallback failed: {e}")

        selectable_packs_pos = []
        pack_identities = {}
        known_pack_names = {}
        found_priority_packs = []
        for coord, (score, pack_name) in best_per_coord.items():
            selectable_packs_pos.append(coord)
            pack_identities[coord] = pack_name
            known_pack_names[coord] = pack_name
            if pack_name in floor_priorities:
                found_priority_packs.append((floor_priorities[pack_name], coord, pack_name))

        return selectable_packs_pos, pack_identities, known_pack_names, found_priority_packs, excepted_visible_count

    def pack_selection(self) -> None:
        if self.current_floor_tracker:
            last_floor_num = int(self.current_floor_tracker.replace("floor", ""))
            calc_floor_num = min(last_floor_num + 1, 5)
            self.logger.info(f"Calculated Floor: {calc_floor_num} (based on last tracked floor: {self.current_floor_tracker})")
        else:
            calc_floor_num = 1
            self.logger.info("Calculated Floor: 1 (no previous floor tracked)")
        calc_floor = f"floor{calc_floor_num}"

        visual_floor = self.floor_id()
        if visual_floor:
            floor = visual_floor
            if visual_floor != calc_floor:
                self.logger.warning(f"Visual floor ({visual_floor}) differs from calculated ({calc_floor}). Using visual (highest-confidence match).")
            else:
                self.logger.info(f"Visual floor confirmed: {visual_floor}")
        else:
            self.logger.warning(f"Visual floor detection failed falling back to calculated floor: {calc_floor}")
            floor = calc_floor

        if floor != self.current_floor_tracker:
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
            if (common.element_exist("pictures/CustomAdded1080p/mirror/packs/floor_hard.png", 0.65, quiet_failure=True) or
                common.element_exist("pictures/mirror/packs/floor_hard.png", 0.65, quiet_failure=True) or
                common.element_exist("pictures/CustomAdded1080p/mirror/packs/hard_toggle.png", 0.65, quiet_failure=True) or
                common.element_exist("pictures/mirror/packs/hard_toggle.png", 0.65, quiet_failure=True)):
                self.logger.info("Detected Hard Mode, switching to Normal Mode")
                common.sleep(2)
                if not common.click_matching("pictures/CustomAdded1080p/mirror/packs/hard_toggle.png", threshold=0.65, recursive=False, quiet_failure=True):
                    if not common.click_matching("pictures/mirror/packs/hard_toggle.png", threshold=0.65, recursive=False, quiet_failure=True):
                        self.logger.warning("Could not find hard_toggle.png. Attempting to click floor_hard.png as fallback.")
                        if not common.click_matching("pictures/CustomAdded1080p/mirror/packs/floor_hard.png", threshold=0.65, recursive=False, quiet_failure=True):
                            common.click_matching("pictures/mirror/packs/floor_hard.png", threshold=0.65, recursive=False, quiet_failure=True)

        min_y_scaled = common.scale_y_1080p(100)
        max_y_scaled = common.scale_y_1080p(980)
        min_x_scaled = common.scale_x_1080p(50)
        max_x_scaled = common.scale_x_1080p(1870)

        known_pack_names = {}
        refresh_count = 0
        MAX_REFRESHES = getattr(shared_vars, 'pack_refreshes', 7)

        retry_attempt = 10
        while retry_attempt > 0:
            retry_attempt -= 1
            
            if (common.element_exist("pictures/battle/winrate.png", quiet_failure=True) or
                common.element_exist("pictures/battle/winrate_wave.png", quiet_failure=True) or
                common.element_exist("pictures/CustomAdded1080p/battle/battle_in_progress.png", quiet_failure=True)):
                self.logger.info("Battle detected inside pack_selection loop. Aborting.")
                return

            floor_priorities = shared_vars.ConfigCache.get_config("pack_priority").get(floor, {})
            exception_packs = shared_vars.ConfigCache.get_config("pack_exceptions").get(floor, [])

            sorted_priorities_log = sorted(floor_priorities.items(), key=lambda x: x[1])
            self.logger.info(f"Pack Selection - Floor: {floor} | Priorities: {sorted_priorities_log} | Exceptions: {exception_packs}")
            
            common.mouse_move(*common.scale_coordinates_1080p(200,200))
            common.sleep(0.2)
            screenshot = common.capture_screen()

            selectable_packs_pos = []
            pack_identities = {}
            found_priority_packs = []

            excepted_visible_count = 0

            if floor:
                floor_char = floor[-1]
                (selectable_packs_pos, pack_identities, known_pack_names,
                 found_priority_packs, excepted_visible_count) = self._fast_scan_packs(
                    floor_char, screenshot, exception_packs, floor_priorities,
                    min_x_scaled, min_y_scaled, max_x_scaled, max_y_scaled
                )

            if len(selectable_packs_pos) == 0:
                if excepted_visible_count > 0:
                    if floor_priorities and refresh_count < MAX_REFRESHES:
                        self.logger.warning(f"Only excepted pack(s) detected on {floor}, but refreshes remain. Attempting refresh before giving up.")
                    else:
                        self.logger.error(f"All {excepted_visible_count} visible pack(s) on {floor} are in the exception list. Stopping macro.")
                        raise RuntimeError(f"All visible packs are excepted on {floor}. Cannot select a pack.")
                elif retry_attempt > 0:
                    logger.debug("No packs detected, retrying...")
                    common.sleep(0.5)
                    continue
            
            self.logger.debug(f"Found {len(selectable_packs_pos)} selectable packs")

            def robust_drag_pack(x, y):
                extra = 1.0 if not shared_vars.good_pc_mode else 0.0
                common.mouse_move(x, y)
                common.sleep(0.15 + extra)
                common.mouse_down()
                common.sleep(0.15 + extra)
                drag_offset = round(350 * common.EXPECTED_HEIGHT / common.REFERENCE_HEIGHT_1080P)
                dest_x, dest_y = common.get_MonCords(x, y + drag_offset)
                common._bezier_move(dest_x, dest_y, duration=0.3 + extra)
                common.sleep(0.15 + extra)
                common.mouse_up()

            def select_pack(coords, name="unknown_pack"):
                pack_name = name
                raw_name = name

                if coords in known_pack_names:
                    raw_name = known_pack_names[coords]
                    pack_name = raw_name

                if pack_name.lower().endswith('.png'):
                    pack_name = pack_name[:-4]

                detected_floor = f"Floor {floor_char}" if floor_char else "unknown_floor"
                
                self.logger.info(f"Selected Pack: {pack_name} | Location: {detected_floor}")

                x, y = coords
                robust_drag_pack(x, y)
                self.run_stats["packs_by_floor"][floor] = pack_name

                wait_start = time.time()
                selection_confirmed = False
                while time.time() - wait_start < 5:
                    if not self.is_pack_screen():
                        selection_confirmed = True
                        break
                    common.sleep(0.2)

                if selection_confirmed:
                    self.run_stats["packs"].append(pack_name)
                    self.current_floor_tracker = floor
                else:
                    self.logger.warning(f"Pack screen still visible after 5s wait. Pack selection may not have registered. NOT counting pack, will retry.")

            if found_priority_packs:
                found_priority_packs.sort(key=lambda x: x[0])

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
                    common.sleep(3.5)
                    refresh_count += 1
                    retry_attempt = 10
                    continue
                else:
                    
                    logger.warning("Refresh button not found via image. Attempting blind click.")
                    
                    common.mouse_move_click(*common.scale_coordinates_1080p(1600, 50))
                    
                    common.mouse_move(*common.scale_coordinates_1080p(200, 200))
                    common.sleep(3.5)
                    refresh_count += 1
                    retry_attempt = 10
                    continue

            if selectable_packs_pos:
                non_excepted = [
                    c for c in selectable_packs_pos
                    if pack_identities.get(c, "unknown_pack") not in exception_packs
                ]
                if not non_excepted:
                    non_excepted = selectable_packs_pos

                best_coord, best_name = self._gift_weighted_pack(non_excepted, pack_identities, screenshot)
                if best_coord:
                    select_pack(best_coord, best_name)
                    return

                import random
                logger.info("Fallback: Selecting random available pack")
                for target_coords in random.sample(non_excepted, len(non_excepted)):
                    pack_name = pack_identities.get(target_coords, "unknown_pack")
                    if pack_name != "unknown_pack":
                        logger.info(f"Identified fallback pack as: {pack_name}")
                    select_pack(target_coords, pack_name)
                    return

        if retry_attempt == 0:
            logger.error("Something went wrong, not fixable after 10 retries.")
            screenshot = common.capture_screen()
            floor_char = floor[-1] if floor else "1"
            floor_dir = os.path.join(BASE_PATH, f"pictures/mirror/packs/f{floor_char}")
            final_exception_packs = shared_vars.ConfigCache.get_config("pack_exceptions").get(floor, [])
            if os.path.exists(floor_dir):
                all_packs = [f for f in os.listdir(floor_dir) if f.endswith(".png")]
                for pack_file in all_packs:
                    pack_name = pack_file.replace(".png", "")
                    if pack_name in final_exception_packs:
                        continue
                    matches = common.match_image(f"pictures/mirror/packs/f{floor_char}/{pack_file}", 0.55, grayscale=True, screenshot=screenshot, enable_scaling=True)
                    if matches:
                        logger.info(f"Final scan found non-excepted pack: {pack_name}")
                        select_pack(matches[0], pack_name)
                        return
                self.logger.warning("Final template scan found nothing. Attempting inpack.png blind fallback.")
                inpack_matches = common.match_image(
                    "pictures/CustomAdded1080p/mirror/packs/inpack.png",
                    threshold=0.7, quiet_failure=True, screenshot=screenshot
                )
                if inpack_matches:
                    iy1 = common.scale_y_1080p(260)
                    iy2 = common.scale_y_1080p(800)
                    ix1 = common.scale_x_1080p(315)
                    ix2 = common.scale_x_1080p(1570)
                    filtered = [(x, y) for x, y in inpack_matches if iy1 <= y <= iy2 and ix1 <= x <= ix2]
                    if filtered:
                        bx, by = filtered[0]
                        self.logger.info(f"inpack fallback: dragging pack at ({bx}, {by})")
                        robust_drag_pack(bx, by)
                        return
                self.logger.error(f"inpack fallback also found nothing on {floor}. Stopping macro.")
                raise RuntimeError(f"All visible packs are excepted on {floor}. Cannot select a pack.")

    def squad_select(self):
        self.logger.info("Selecting squad members for battle")
        if not self.squad_set or not common.element_exist("pictures/CustomAdded1080p/general/squads/full_squad.png"):
            common.click_matching("pictures/CustomAdded1080p/general/squads/clear_selection.png")
            common.sleep(0.2)
            common.click_matching("pictures/general/confirm_w.png", recursive=False)
            for i in self.squad_order: 
                x,y = i
                self.logger.info(f"Clicking squad member at ({x}, {y})")
                common.mouse_move_click(x, y)
            self.squad_set = True
        
        common.mouse_move_click(*common.scale_coordinates_1080p(1722, 881))
        for i in range(20):
            if common.element_exist("pictures/battle/winrate.png") or common.element_exist("pictures/battle/winrate_wave.png"):
                logger.debug("Premature break due to winrate detected.")
                break
            if common.element_exist("pictures/events/skip.png"):
                logger.debug("Premature break due to event skip button detected")
                break
            common.sleep(0.5)
        battle()
        check_loading()

    def reward_select(self):
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

        found = common.match_image(status_effect, 0.93) or []
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
            elif len(selectable_ego_gift_matches) > 0:

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
        common.sleep(0.5)
        common.click_matching("pictures/general/confirm_b.png", recursive=False, quiet_failure=True)
        common.click_matching("pictures/general/confirm_w.png", recursive=False, quiet_failure=True)

    def encounter_reward_select(self):
        self.logger.info("Selecting encounter rewards")
        _valid = {"cost_gift", "cost", "gift", "resource", "starlight"}
        _priority = shared_vars.ConfigCache.get_config("card_priority")
        if not _priority or not isinstance(_priority, list):
            _priority = ["cost_gift", "cost", "gift", "resource", "starlight"]
        _priority = [c for c in _priority if c in _valid]
        for c in ["cost_gift", "cost", "gift", "resource", "starlight"]:
            if c not in _priority:
                _priority.append(c)
        encounter_reward = [f"pictures/mirror/encounter_reward/{c}.png" for c in _priority]
        common.sleep(0.5)

        min_x = common.scale_x_1080p(360)
        max_x = common.scale_x_1080p(1555)
        min_y = common.scale_y_1080p(225)
        max_y = common.scale_y_1080p(845)

        max_attempts = 3
        for attempt in range(max_attempts):
            clicked = False
            for rewards in encounter_reward:
                if common.click_matching(rewards, recursive=False, x1=min_x, y1=min_y, x2=max_x, y2=max_y):
                    clicked = True
                    common.click_matching("pictures/general/confirm_b.png")
                    common.sleep(1)
                    if common.element_exist("pictures/mirror/encounter_reward/prompt.png"):
                        common.click_matching("pictures/CustomAdded1080p/mirror/general/BorderedConfirm.png")
                        break
                    if common.element_exist("pictures/mirror/general/ego_gift_get.png"):
                        common.click_matching("pictures/general/confirm_b.png", recursive=False)
                    break
            if clicked:
                break
            if attempt < max_attempts - 1:
                self.logger.warning(f"encounter_reward_select: no reward found (attempt {attempt + 1}/{max_attempts}), waiting for tiles...")
                common.reset_sct()
                common.sleep(1.5)
        common.sleep(1)

    def check_nodes(self,nodes):
        screenshot = common.capture_screen()
        non_exist = [1,1,1]
        threshold = 0.75
        top = common.greyscale_match_image("pictures/mirror/general/node_1.png", threshold, screenshot=screenshot)
        top_alt = common.greyscale_match_image("pictures/mirror/general/node_1_o.png", threshold, screenshot=screenshot)
        middle = common.greyscale_match_image("pictures/mirror/general/node_2.png", threshold, screenshot=screenshot)
        middle_alt = common.greyscale_match_image("pictures/mirror/general/node_2_o.png", threshold, screenshot=screenshot)
        bottom = common.greyscale_match_image("pictures/mirror/general/node_3_o.png", threshold, screenshot=screenshot)
        bottom_alt = common.greyscale_match_image("pictures/mirror/general/node_3.png", threshold, screenshot=screenshot)
        if not top and not top_alt:
            non_exist[0] = 0
        if not middle and not middle_alt:
            non_exist[1] = 0
        if not bottom and not bottom_alt:
            non_exist[2] = 0
        result = [y for y, exists in zip(nodes, non_exist) if exists != 0]
        if not result:
            self.logger.warning("check_nodes: no nodes detected, assuming all exist as fallback")
            return nodes
        return result

    def _classify_node_at(self, cx, cy, full_screenshot):
        NAV = "pictures/mirror/navigation"
        hw = common.scale_x_1080p(140)
        hh = common.scale_y_1080p(130)
        kw = {
            "x1": max(0, cx - hw), "y1": max(0, cy - hh),
            "x2": min(full_screenshot.shape[1], cx + hw),
            "y2": min(full_screenshot.shape[0], cy + hh),
            "screenshot": full_screenshot,
            "quiet_failure": True,
            "enable_scaling": True,
        }
        def has(name, t=0.72):
            return bool(common.match_image(f"{NAV}/{name}.png", t, **kw))
        if has("boss_ark", 0.70) or has("boss0", 0.65) or has("boss1", 0.65) or has("boss_highlighted", 0.65): return "Boss"
        if has("event0") or has("event1") or has("event2"):                    return "Event"
        if has("shop0") or has("shop1") or has("shop_highlighted"):            return "Shop"
        if has("risk0", 0.65) or has("risk1", 0.65) or has("risk2", 0.65):    return "Risky"
        if has("focus0", 0.65) or has("focus1", 0.65) or has("focus2", 0.65) or has("focus3", 0.65): return "Focused"
        if has("coin", 0.70):
            return "Miniboss" if has("gift", 0.70) else "Normal"
        return None

    def _get_nav_connections(self, screenshot, x_adj=0, y_adj=0):
        import cv2
        NAV = "pictures/mirror/navigation"
        rx1 = common.scale_x_1080p(850)  + x_adj; ry1 = common.scale_y_1080p(280) + y_adj
        rx2 = common.scale_x_1080p(1460) + x_adj; ry2 = common.scale_y_1080p(710) + y_adj
        rx1 = max(0, rx1); ry1 = max(0, ry1)
        rx2 = min(screenshot.shape[1], rx2); ry2 = min(screenshot.shape[0], ry2)
        region = screenshot[ry1:ry2, rx1:rx2]
        if region.size == 0:
            return []
        rh, rw = region.shape[:2]
        ch = max(1, int(0.216 * rh))
        cw = max(1, int(0.492 * rw))
        quads = [
            region[0:ch, 0:cw],
            region[0:ch, rw-cw:rw],
            region[rh-ch:rh, 0:cw],
            region[rh-ch:rh, rw-cw:rw],
        ]
        connections = []
        for i, quad in enumerate(quads):
            for j, direction in enumerate(["up", "down"]):
                try:
                    tmpl = cv2.imread(common.resource_path(f"{NAV}/{direction}.png"), cv2.IMREAD_GRAYSCALE)
                    src  = cv2.cvtColor(quad, cv2.COLOR_BGR2GRAY) if len(quad.shape) == 3 else quad.copy()
                    if tmpl is None or tmpl.shape[0] > src.shape[0] or tmpl.shape[1] > src.shape[1]:
                        continue
                    if cv2.matchTemplate(src, tmpl, cv2.TM_CCOEFF_NORMED).max() >= 0.80:
                        connections.append(((i % 2, (i // 2) + 1 - j), (i % 2 + 1, (i // 2) + j)))
                except Exception:
                    pass
        return connections

    def _dfs_best_first_step(self, nodes, connections):
        _COSTS = {"Boss": 60, "Event": 0, "Shop": 15, "Focused": 77,
                  "Miniboss": 67, "Normal": 52, "Risky": 87, "Unknown": 52}
        L = len(nodes)
        if L == 0:
            return None, None
        adj = {}
        for i in range(L):
            for j in range(3):
                if nodes[i][j] is not None:
                    adj.setdefault((i, j), [])
        for i in range(L - 1):
            for j in range(3):
                if nodes[i][j] is not None:
                    for nj in [j - 1, j, j + 1]:
                        if 0 <= nj <= 2 and nodes[i + 1][nj] is not None:
                            adj.setdefault((i, j), []).append((i + 1, nj))
        for (a, b), (c, d) in connections:
            if 0 <= a < L and 0 <= c < L and nodes[a][b] is not None and nodes[c][d] is not None:
                if a + 1 == c:
                    adj.setdefault((a, b), []).append((c, d))
                elif c + 1 == a:
                    adj.setdefault((c, d), []).append((a, b))
        def dfs(i, j, seen):
            if (i, j) in seen:
                return float('inf')
            cost = _COSTS.get(nodes[i][j], 52)
            if i == L - 1:
                return cost
            children = [dfs(ni, nj, seen | {(i, j)}) for ni, nj in adj.get((i, j), []) if ni == i + 1]
            return cost + (min(children) if children else 0)
        best_j, best_cost = None, float('inf')
        for j in range(3):
            if nodes[0][j] is None:
                continue
            c = dfs(0, j, set())
            if c < best_cost:
                best_cost, best_j = c, j
        return best_j, (nodes[0][best_j] if best_j is not None else None)

    def _gift_weighted_pack(self, candidates, pack_identities, screenshot):
        status_sel = getattr(shared_vars, 'status_selection', None)
        if not status_sel:
            return None, None
        status = (status_sel[0] if isinstance(status_sel, list) else status_sel).lower()
        gift_path = f"pictures/mirror/gifts/{status}.png"
        gift_matches = common.match_image(gift_path, 0.7, screenshot=screenshot, quiet_failure=True) or []
        owned_matches = common.match_image("pictures/mirror/gifts/owned_small.png", 0.75, screenshot=screenshot, quiet_failure=True) or []
        owned_xs = [x for x, _ in owned_matches]
        gift_matches = [(gx, gy) for gx, gy in gift_matches if all(abs(gx - ox) >= 25 for ox in owned_xs)]
        if not gift_matches:
            self.logger.debug("EGO gift weighting: no matching gift icons found, skipping")
            return None, None
        col_half = common.scale_x_1080p(145)
        counts = {}
        for coord in candidates:
            px, _ = coord
            counts[coord] = sum(1 for gx, _ in gift_matches if abs(gx - px) < col_half)
        best_coord = max(counts, key=counts.get)
        best_count = counts[best_coord]
        if best_count == 0:
            self.logger.debug("EGO gift weighting: gift icons present but none near any pack column, skipping")
            return None, None
        best_name = pack_identities.get(best_coord, "unknown_pack")
        self.logger.info(f"EGO gift weighting: '{best_name}' scores {best_count} {status} gifts")
        return best_coord, best_name

    def _check_connections_adjust(self, connections):
        levels = [y for pair in connections for (_, y) in pair]
        has_zero = 0 in levels
        has_two  = 2 in levels
        if (has_zero and has_two) or (not has_zero and not has_two):
            return 0
        return 1 if has_zero else -1

    def navigation(self, _depth=0):
        if _depth >= 2:
            self.logger.warning("Navigation: recursion limit reached, giving up")
            return
        self.logger.info("Navigating floor nodes")
        nav_threshold = 0.65 if self.res_x < 1920 else 0.8
        nav_x1 = common.scale_x_1080p(1100)
        nav_start_time = time.time()

        if common.click_matching("pictures/mirror/general/nav_enter.png", threshold=nav_threshold, recursive=False, x1=nav_x1):
            return

        end_time = time.time() + 5
        while not (
            common.click_matching("pictures/mirror/general/danteh.png", recursive=False) or
            common.click_matching("pictures/CustomAdded1080p/mirror/general/danteh_zoomed.png", recursive=False)
        ):
            if time.time() > end_time:
                break

        while common.element_exist("pictures/general/connection_o.png"):
            pass

        if common.click_matching("pictures/mirror/general/nav_enter.png", threshold=nav_threshold, recursive=False, x1=nav_x1):
            return

        common.mouse_move(*common.scale_coordinates_1080p(200, 200))
        dante_found = common.match_image("pictures/mirror/general/danteh.png") or \
                      common.match_image("pictures/CustomAdded1080p/mirror/general/danteh_zoomed.png")
        if dante_found:
            dx, dy = dante_found[0]
            common.mouse_move(dx, dy)
            target_x, target_y = common.scale_coordinates_1080p(429, 480)
            common.mouse_drag(target_x, target_y, seconds=0.4, hold=0.3, release_hold=0.3)
            common.sleep(0.5)
            common.mouse_move_click(*common.scale_coordinates_1080p(329, 710))
            common.sleep(1.5)

        _COSTS = {"Event": 0, "Shop": 15, "Normal": 52, "Miniboss": 67,
                  "Boss": 60, "Focused": 77, "Risky": 87}

        NAV = "pictures/mirror/navigation"
        row_half = common.scale_y_1080p(120)

        def _build_coords(x_adj=0, y_adj=0):
            return (
                [common.scale_y_1080p(238)+y_adj, common.scale_y_1080p(513)+y_adj, common.scale_y_1080p(788)+y_adj],
                [
                    (common.scale_x_1080p(624)+x_adj,  common.scale_x_1080p(906)+x_adj),
                    (common.scale_x_1080p(1004)+x_adj, common.scale_x_1080p(1286)+x_adj),
                    (common.scale_x_1080p(1384)+x_adj, common.scale_x_1080p(1666)+x_adj),
                ],
                common.scale_x_1080p(765) + x_adj,
            )

        def _scan_nodes(screenshot, x_adj=0, y_adj=0):
            row_y_local, depth_x_local, _ = _build_coords(x_adj, y_adj)
            arrow_x1 = common.scale_x_1080p(350) + x_adj
            arrow_x2 = common.scale_x_1080p(906) + x_adj
            ROW_ARROW = [f"{NAV}/_up.png", f"{NAV}/_forward.png", f"{NAV}/_down.png"]
            rr = [
                i for i, (arrow_img, row_y) in enumerate(zip(ROW_ARROW, row_y_local))
                if common.match_image(arrow_img, 0.75, screenshot=screenshot,
                                      x1=arrow_x1, x2=arrow_x2,
                                      y1=row_y - row_half, y2=row_y + row_half,
                                      quiet_failure=True)
            ]
            if not rr:
                rr = [0, 1, 2]

            def _classify_at(x_min, x_max, row_y, scr):
                kw = dict(screenshot=scr, x1=x_min, x2=x_max,
                          y1=row_y - row_half, y2=row_y + row_half, quiet_failure=True)
                kw_gray = dict(**kw, grayscale=True)
                def has(paths, t, gray=False):
                    kws = kw_gray if gray else kw
                    return any(common.match_image(p, t, **kws) for p in paths)
                if has([f"{NAV}/boss_ark.png", f"{NAV}/boss0.png", f"{NAV}/boss1.png", f"{NAV}/boss_highlighted.png"], 0.65): return "Boss"
                if has([f"{NAV}/event_node.png"], 0.65, gray=True) or \
                   has([f"{NAV}/event0.png", f"{NAV}/event1.png", f"{NAV}/event2.png"], 0.72): return "Event"
                if has([f"{NAV}/shop0.png",    f"{NAV}/shop1.png",    f"{NAV}/shop_highlighted.png", f"{NAV}/super0.png",   f"{NAV}/super1.png"], 0.65): return "Shop"
                if has([f"{NAV}/risk0.png",    f"{NAV}/risk1.png",    f"{NAV}/risk2.png"],    0.65): return "Risky"
                if has([f"{NAV}/focus0.png",   f"{NAV}/focus1.png",   f"{NAV}/focus2.png",   f"{NAV}/focus3.png"], 0.65): return "Focused"
                if has([f"{NAV}/coin.png"],                                                    0.80): return "Normal"
                return None

            nd = [[None] * 3 for _ in range(3)]
            for depth in range(3):
                x_min, x_max = depth_x_local[depth]
                rows = range(3)
                for row in rows:
                    nd[depth][row] = _classify_at(x_min, x_max, row_y_local[row], screenshot)
            return nd, rr

        nav_screenshot = common.capture_screen()

        x_adj = y_adj = 0
        dante_in_nav = (
            common.match_image("pictures/mirror/general/danteh.png", screenshot=nav_screenshot, quiet_failure=True) or
            common.match_image("pictures/CustomAdded1080p/mirror/general/danteh_zoomed.png", screenshot=nav_screenshot, quiet_failure=True)
        )
        if dante_in_nav:
            ax, ay = dante_in_nav[0]
            x_adj = ax - common.scale_x_1080p(429)
            y_adj = ay - common.scale_y_1080p(480)
            if abs(x_adj) > 10 or abs(y_adj) > 10:
                self.logger.info(f"Camera drift: Dante at ({ax},{ay}), adjusting coords by ({x_adj},{y_adj})")

        ROW_Y, _, FALLBACK_X = _build_coords(x_adj, y_adj)

        connections = self._get_nav_connections(nav_screenshot, x_adj, y_adj)
        self.logger.info(f"Connections detected: {connections}")

        nodes, reachable_rows = _scan_nodes(nav_screenshot, x_adj, y_adj)
        self.logger.info(f"Node matrix: {nodes}")

        if all(n is None for n in nodes[0]):
            self.logger.warning("Depth-0 all None, retrying scan after 1s")
            common.sleep(1.0)
            nav_screenshot = common.capture_screen()
            nodes, reachable_rows = _scan_nodes(nav_screenshot, x_adj, y_adj)
            self.logger.info(f"Retry node matrix: {nodes}")

        best_row, best_type = self._dfs_best_first_step(nodes, connections)
        if best_row is not None:
            classified = [((FALLBACK_X, ROW_Y[best_row]), best_type)]
            self.logger.info(f"DFS best path: row {best_row} ({best_type})")
        else:
            classified = [
                ((FALLBACK_X, ROW_Y[r]), nodes[0][r])
                for r in reachable_rows
                if nodes[0][r] is not None
            ]
            classified.sort(key=lambda item: _COSTS.get(item[1], 52))
            self.logger.warning(f"DFS found no path, falling back to cost sort: {classified}")

        while not common.element_exist("pictures/mirror/general/nav_enter.png", threshold=nav_threshold, x1=nav_x1):
            if time.time() - nav_start_time > 180:
                self.logger.warning("Navigation timed out")
                return
            if (common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.72, quiet_failure=True) or
                    common.element_exist("pictures/general/victory.png", quiet_failure=True)):
                return

            nav_found = False
            for (x, y), _ in classified:
                common.mouse_move_click(x, y)
                common.sleep(1.5)
                if common.element_exist("pictures/mirror/general/nav_enter.png", threshold=nav_threshold, x1=nav_x1):
                    nav_found = True
                    break

            if not nav_found:
                self.logger.warning("Nav click failed, trying blind click fallback")
                for row_y in ROW_Y:
                    common.mouse_move_click(FALLBACK_X, row_y)
                    common.sleep(1.5)
                    if common.element_exist("pictures/mirror/general/nav_enter.png", threshold=nav_threshold, x1=nav_x1):
                        nav_found = True
                        break

            if not nav_found:
                nav_screenshot = common.capture_screen()
                renodes, reachable_rows = _scan_nodes(nav_screenshot, x_adj, y_adj)
                re_row, re_type = self._dfs_best_first_step(renodes, connections)
                if re_row is not None:
                    classified = [((FALLBACK_X, ROW_Y[re_row]), re_type)]
                    self.logger.info(f"Re-scan DFS: row {re_row} ({re_type})")
                else:
                    self.logger.warning("Re-scan found no path, recursing")
                    self.navigation(_depth=_depth + 1)
                    return

        common.sleep(0.4)
        for _ in range(3):
            if common.click_matching("pictures/mirror/general/nav_enter.png", threshold=nav_threshold, recursive=False, x1=nav_x1):
                break
            common.sleep(0.3)

    def sell_gifts(self):
        for _ in range(3):
            common.sleep(1)
            if common.click_matching("pictures/mirror/restshop/market/vestige_2.png", recursive=False):
                common.click_matching("pictures/mirror/restshop/market/sell_b.png")
                common.click_matching("pictures/general/confirm_w.png")

            if common.click_matching("pictures/mirror/restshop/scroll_bar.png", recursive=False):
                for _ in range(5):
                    common.mouse_scroll(-1000)
    
    def fuse(self):

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
        common.sleep(0.2)

        if common.element_exist("pictures/mirror/general/ego_gift_get.png"):
             common.key_press("enter")
             
        return True

    def find_gifts(self, statuses, excluded_statuses=None):
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

            threshold = 0.65
            if i == "blunt":
                threshold = 0.75
            
            status_coords = common.ifexist_match(status, threshold, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, no_grayscale=True)
            if status_coords:
                self.logger.info(f"find_gifts: Detected {len(status_coords)} '{i}' gifts at {status_coords}")
                fusion_gifts += status_coords
                for coord in status_coords:
                    if coord not in gift_types: gift_types[coord] = []
                    gift_types[coord].append(i)
            
            market_status = mirror_utils.market_choice(i)
            if market_status:
                market_coords = common.ifexist_match(market_status, threshold, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, no_grayscale=True)
                if market_coords:
                    self.logger.info(f"find_gifts: Detected {len(market_coords)} '{i}' market gifts at {market_coords}")
                    fusion_gifts += market_coords
                    for coord in market_coords:
                        if coord not in gift_types: gift_types[coord] = []
                        gift_types[coord].append(f"{i}_market")

        if excluded_statuses:
            for i in excluded_statuses:
                status = mirror_utils.get_status_gift_template(i)
                excluded_coords = common.ifexist_match(status, 0.6, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, quiet_failure=True, no_grayscale=True)
                if excluded_coords:
                    self.logger.info(f"find_gifts: Detected {len(excluded_coords)} excluded '{i}' gifts, removing overlaps.")
                    to_remove = common.proximity_check(fusion_gifts, excluded_coords, common.scale_x_1080p(70))
                    fusion_gifts = [g for g in fusion_gifts if g not in to_remove]

        fusion_gifts = list(dict.fromkeys(fusion_gifts))

        for gift in fusion_gifts:
            types = gift_types.get(gift, ["unknown"])
            self.logger.info(f"Candidate gift at {gift} identified as: {', '.join(types)}")

        self.logger.debug("Checking for fully upgraded (++) gifts...")
        fully_upgraded_coords = common.ifexist_match("pictures/CustomAdded1080p/mirror/general/fully_upgraded.png", 0.6, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, enable_scaling=True, no_grayscale=True)
        fully_upgraded_coords_2 = common.ifexist_match("pictures/mirror/restshop/enhance/fully_upgraded.png", 0.6, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, enable_scaling=True, quiet_failure=True, no_grayscale=True)
        if fully_upgraded_coords_2:
            fully_upgraded_coords.extend(fully_upgraded_coords_2)

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
                    if common.ifexist_match(gift_img, 0.7, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot, no_grayscale=True):
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
        exception_gifts = []
        
        try:
            exceptions_data = shared_vars.ConfigCache.get_config("fusion_exceptions")

            if isinstance(exceptions_data, list):
                for name in exceptions_data:
                    
                    folder_path = os.path.join(BASE_PATH, "pictures", "CustomFuse", name)
                    if os.path.isdir(folder_path):
                        
                        for file in os.listdir(folder_path):
                            if file.lower().endswith('.png'):
                                exception_gifts.append(f"pictures/CustomFuse/{name}/{file}")
                    else:
                        found_file = False
                        for ext in ['.png']:
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
        self.logger.info("Starting gift fusion")

        def exit_fusion():
            if not common.click_matching("pictures/mirror/restshop/close.png", recursive=False):
                common.sleep(1)
                if not common.click_matching("pictures/mirror/restshop/close.png", recursive=False):
                    common.key_press("esc")
            common.sleep(0.5)

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
        duration = 5
        while not (common.element_exist("pictures/mirror/restshop/fusion/fuse_menu.png") or
                   common.element_exist("pictures/mirror/restshop/fusion/fuse_b.png")):
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
            time.sleep(1)

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
                for _ in range(5):
                    common.mouse_scroll(1000)
                common.sleep(0.5)
                
            selected_gifts_coords = []
            scroll_attempts = 0
            max_scroll_attempts = 8

            while len(selected_gifts_coords) < 3 and scroll_attempts < max_scroll_attempts:
                current_screen_gifts = self.find_gifts(statuses, excluded_statuses)
                self.logger.info(f"fuse_gifts: Loop start. Found {len(current_screen_gifts)} gifts on screen.")

                current_screen_gifts.sort(key=lambda p: p[1], reverse=True)
                
                new_gifts_on_screen = current_screen_gifts

                self.logger.info(f"fuse_gifts: {len(new_gifts_on_screen)} new gifts available to click.")
                for x, y in new_gifts_on_screen:
                    if len(selected_gifts_coords) < 3:
                        self.logger.info(f"Clicking EGO gift at ({x}, {y}). Selected {len(selected_gifts_coords) + 1}/3.")
                        common.mouse_move_click(x, y)
                        common.sleep(0.2)
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
                    common.sleep(0.5)
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
                    common.sleep(0.5)
                    continue
            else:
                self.logger.info(f"Could not find 3 EGO gifts for fusion (found {len(selected_gifts_coords)}). Exiting fusion menu.")
                break
        
        exit_fusion()
                
    def rest_shop(self):
        self.logger.info("Entering rest shop logic")
        def leave_restshop():
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
            if (common.element_exist("pictures/mirror/restshop/fusion/fuse_menu.png", quiet_failure=True) or
                    common.element_exist("pictures/mirror/restshop/fusion/fuse_b.png", quiet_failure=True)):
                self.logger.warning("Fuse dialog still open after fusion, closing")
                common.key_press("esc")
                common.sleep(1)

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
                wait_start = time.time()
                while time.time() - wait_start < 3:
                    if common.click_matching("pictures/mirror/restshop/leave.png", recursive=False):
                        break
                    common.sleep(0.1)
                else:
                    common.click_matching("pictures/mirror/restshop/return.png")

            if not shared_vars.skip_ego_enhancing:
                self.logger.info("Attempting enhancing")
                status = mirror_utils.get_status_gift_template(self.status)
                if status is None:
                    status = "pictures/mirror/restshop/enhance/poise_enhance.png"
                common.click_matching("pictures/mirror/restshop/enhance/enhance.png")
                if not common.click_matching("pictures/CustomAdded1080p/mirror/general/fully_scrolled_up.png", threshold=0.95, recursive=False) and common.click_matching("pictures/mirror/restshop/scroll_bar.png", recursive=False):
                    for _ in range(5):
                        common.mouse_scroll(1000)
                self.enhance_gifts(status)
                _close_end = time.time() + 15
                _esc_time = time.time() + 4
                _esc_pressed = False
                while not common.click_matching("pictures/mirror/restshop/close.png", recursive=False):
                    if time.time() > _close_end:
                        self.logger.warning("Timed out waiting for enhance close button")
                        break
                    if not _esc_pressed and time.time() > _esc_time:
                        if common.element_exist("pictures/CustomAdded1080p/mirror/general/enhancement_tier.png", quiet_failure=True):
                            self.logger.warning("Enhancement screen still open after 4s, pressing ESC to exit")
                            common.key_press("esc")
                            _esc_pressed = True
                    common.mouse_move(*common.scale_coordinates_1080p(50, 50))
                    time.sleep(0.5)

            if not shared_vars.skip_ego_buying:
                self.logger.info("Selling vestiges before buying")
                self.sell_gifts()
                self.logger.info("Attempting buying")
                status = mirror_utils.market_choice(self.status)
                if status is None:
                    status = "pictures/mirror/restshop/market/poise_market.png"
                for _ in range(2):  
                    if common.click_matching("pictures/mirror/restshop/shop_scroll_up.png", recursive=False):  
                        for _ in range(45): 
                            common.mouse_scroll(1000)
                    for _ in range(3):
                        screenshot = common.capture_screen()
                        market_gifts = common.match_image(status, screenshot=screenshot) or []
                        if market_gifts:
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
                                while time.time() - wait_start_time < 1:
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

                        if market_gifts:
                            common.sleep(0.3)
                        if common.click_matching("pictures/mirror/restshop/shop_scroll_down.png", recursive=False):
                            for _ in range(15):
                                common.mouse_scroll(-1000)
                        else:
                            break
                    if common.element_exist("pictures/mirror/restshop/small_not.png"):
                        break
                    common.mouse_move_click(*common.scale_coordinates_1080p(50, 50))
                    common.sleep(0.3)
                    common.click_matching("pictures/mirror/restshop/market/refresh.png", recursive=False, quiet_failure=True)
                    common.sleep(0.8)

        leave_restshop()

    def upgrade(self, gifts):
        for x,y in gifts:
            common.sleep(0.3)
            common.mouse_move_click(x, y)
            for _ in range(2):
                common.sleep(0.2)
                common.click_matching("pictures/mirror/restshop/enhance/power_up.png")
                if common.element_exist("pictures/mirror/restshop/enhance/more.png"):
                    common.click_matching("pictures/mirror/restshop/enhance/cancel.png")
                    return False
                confirm_done = False
                wait_start = time.time()
                while time.time() - wait_start < 2:
                    if common.click_matching("pictures/general/confirm_b.png", recursive=False):
                        confirm_done = True
                        break
                    common.click_matching("pictures/mirror/restshop/enhance/confirm.png", recursive=False)
                    common.sleep(0.2)
                if not confirm_done:
                    common.click_matching("pictures/mirror/restshop/enhance/cancel.png", recursive=False, quiet_failure=True)
                    self.logger.warning("Enhancement confirm timed out (insufficient cost?), cancelling")
                    break
                common.sleep(0.2)
        return True

    def enhance_gifts(self,status):
        self.logger.info("Starting gift enhancement")

        x1, y1 = common.scale_coordinates_1080p(900, 300)
        x2, y2 = common.scale_coordinates_1080p(1700, 800)

        attempted_gifts = []
        enhance_deadline = time.time() + 180

        while(True):
            if time.time() > enhance_deadline:
                self.logger.warning("Enhancement timeout (3 min), pressing ESC to exit")
                common.key_press("esc")
                common.sleep(0.5)
                common.click_matching("pictures/mirror/restshop/close.png", recursive=False, quiet_failure=True)
                break
            screenshot = common.capture_screen()
            raw_gifts = common.ifexist_match(status, threshold=0.6, x1=x1, y1=y1, x2=x2, y2=y2, no_grayscale=True, screenshot=screenshot)
            gifts = raw_gifts
            if gifts:
                gifts = [i for i in gifts if i[0] > common.scale_x(1200)]

                fully_upgraded_coords = common.ifexist_match("pictures/CustomAdded1080p/mirror/general/fully_upgraded.png", 0.6, x1=x1, y1=y1, x2=x2, y2=y2, no_grayscale=True, screenshot=screenshot)
                fully_upgraded_coords_2 = common.ifexist_match("pictures/mirror/restshop/enhance/fully_upgraded.png", 0.6, x1=x1, y1=y1, x2=x2, y2=y2, quiet_failure=True, no_grayscale=True, screenshot=screenshot)
                if fully_upgraded_coords_2:
                    fully_upgraded_coords.extend(fully_upgraded_coords_2)

                if fully_upgraded_coords:
                    
                    expand_scaled = common.scale_x_1080p(75)
                    
                    gifts = [gift for gift in gifts if not common.enhanced_proximity_check(fully_upgraded_coords,
                                                                                         [gift], 
                                                                                         expand_left=expand_scaled, 
                                                                                         expand_right=expand_scaled,
                                                                                         expand_above=expand_scaled,
                                                                                         expand_below=expand_scaled,
                                                                                         use_bounding_box=False, return_bool=True)]
                
                if attempted_gifts:
                    gifts = [g for g in gifts if not common.proximity_check([g], attempted_gifts, common.scale_x_1080p(30))]

                if len(gifts):
                    if not self.upgrade(gifts):
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
                    if not self.upgrade(wordless_gifts):
                        break  
                    attempted_gifts.extend(wordless_gifts)

            scrolled = False
            if common.element_exist("pictures/mirror/restshop/scroll_bar.png") and not common.element_exist("pictures/CustomAdded1080p/mirror/general/fully_scrolled.png"):
                common.click_matching("pictures/mirror/restshop/scroll_bar.png")
                for _ in range(5):
                    common.mouse_scroll(-1000)
                scrolled = True
                attempted_gifts = []

            if not scrolled and not gifts and not wordless_gifts:
                break

    def event_choice(self):
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
                if common.element_exist("pictures/events/select_gain.png") or common.element_exist("pictures/events/select_right.png"):
                    self.logger.info("Event: Second choice screen detected, selecting again")
                    common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
                if common.click_matching("pictures/events/proceed.png", recursive=False):
                    break
                if common.click_matching("pictures/events/continue.png", recursive=False):
                    break
            common.sleep(1)
            if common.element_exist("pictures/mirror/general/ego_gift_get.png"):
                common.key_press("enter")

        elif common.click_matching("pictures/events/gain_check.png", recursive=False):
            self.logger.info("Event: Gain Check")
            skill_check()

        elif common.click_matching("pictures/events/gain_check_o.png", recursive=False):
            self.logger.info("Event: Gain Check (Alt)")
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
                if common.element_exist("pictures/events/select_gain.png") or common.element_exist("pictures/events/select_right.png"):
                    self.logger.info("Event: Second choice screen detected, selecting again")
                    common.mouse_move_click(*common.scale_coordinates_1440p(1193, 623))
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

        elif common.click_matching("pictures/CustomAdded1080p/mirror/events/amberchoice.png", recursive=False):
            self.logger.info("Event: Amber - Disciplinary Team choice")
            common.wait_skip("pictures/events/proceed.png")
            if common.element_exist("pictures/events/skip.png"):
                common.click_skip(15)
                self.event_choice()

        elif common.click_matching("pictures/CustomAdded1080p/mirror/events/lcbchoice.png", recursive=False):
            self.logger.info("Event: LCB - Force the door open")
            common.wait_skip("pictures/events/proceed.png")
            if common.element_exist("pictures/events/skip.png"):
                common.click_skip(15)
                self.event_choice()

        elif common.click_matching("pictures/CustomAdded1080p/mirror/events/amberchoice2.png", recursive=False):
            self.logger.info("Event: Amber 2 - Repression Work choice")
            common.wait_skip("pictures/events/proceed.png")
            if common.element_exist("pictures/events/skip.png"):
                common.click_skip(15)
                self.event_choice()

        elif common.click_matching("pictures/events/proceed.png", recursive=False):
            pass

        elif common.click_matching("pictures/events/continue.png", recursive=False):
            pass

        elif not battle_check():
            battle()
            check_loading()

    def victory(self):
        common.click_matching("pictures/general/confirm_w.png", recursive=False)
        common.click_matching("pictures/general/beeg_confirm.png")
        common.mouse_move(*common.scale_coordinates_1080p(200,200))
        common.click_matching("pictures/general/claim_rewards.png")
        common.sleep(1)
        common.click_matching("pictures/general/md_claim.png")
        common.sleep(1)
        common.click_matching("pictures/general/confirm_b.png", recursive=False, quiet_failure=True)
        common.sleep(0.5)
        if common.click_matching("pictures/general/confirm_w.png", recursive=False):
            _wait_end = time.time() + 30
            while True:
                if time.time() > _wait_end:
                    self.logger.warning("Timed out waiting for pass_level screen after victory")
                    break
                if common.element_exist("pictures/mirror/general/weekly_reward.png"):
                    common.key_press("enter")
                if common.element_exist("pictures/mirror/general/pass_level.png"):
                    common.key_press("enter")
                    break
                common.sleep(0.3)
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
        self.logger.info("Defeat detected. Checking for retry or forfeit options...")
        while True:
            retry_img = None
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.72, quiet_failure=True):
                retry_img = "pictures/CustomAdded1080p/mirror/general/retrystage.png"
            if retry_img:
                retry_limit = getattr(shared_vars, 'retry_count', 0)
                if self.retries_used < retry_limit:
                    self.logger.info(f"Retry stage button detected. Retrying ({self.retries_used + 1}/{retry_limit})...")

                    retry_start = time.time()
                    while time.time() - retry_start < 15:
                        if common.click_matching(retry_img, threshold=0.72, quiet_failure=True):
                            
                            wait_start = time.time()
                            while time.time() - wait_start < 4:
                                if common.click_matching("pictures/general/confirm_w.png", threshold=0.72, quiet_failure=True):
                                    self.retries_used += 1
                                    common.sleep(3) 
                                    return False 
                                common.sleep(0.2)
                        common.sleep(0.5)        
                else:
                    self.logger.debug("Retry button found but retries exhausted/disabled.")
                    pass
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/battle_defeat.png", threshold=0.72, quiet_failure=True):
                self.logger.info("Battle defeat detected. Proceeding to forfeit...")
                break 
            if common.element_exist("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.72, quiet_failure=True):
                self.logger.info("Accept defeat detected. Proceeding to forfeit...")
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
            if common.click_matching("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.7, quiet_failure=True, recursive=False, grayscale=True):
                self.logger.info("Clicked acceptdefeat button (PNG)")
                accept_clicked = True
            else:
                
                matches = common.match_image("pictures/CustomAdded1080p/mirror/general/acceptdefeat.png", threshold=0.4, quiet_failure=True, enable_scaling=True, grayscale=True)
                if matches:
                    common.mouse_move_click(matches[0][0], matches[0][1])
                    self.logger.info("Clicked acceptdefeat button (scaled)")
                    accept_clicked = True
                else:
                    
                    retry_matches = common.match_image("pictures/CustomAdded1080p/mirror/general/retrystage.png", threshold=0.5, quiet_failure=True, enable_scaling=True, grayscale=True)
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
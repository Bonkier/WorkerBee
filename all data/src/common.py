import os
import sys
import json

if getattr(sys, 'frozen', False):
    _torch_lib = os.path.join(sys._MEIPASS, 'torch', 'lib')
    if os.path.isdir(_torch_lib):
        os.add_dll_directory(_torch_lib)
import math
import time
import ctypes
import logging
import secrets
import platform
from logging.handlers import RotatingFileHandler
import threading
import inspect
from functools import partial
from ctypes import wintypes
import cv2
import numpy as np
import random
import interception
try:
    interception.auto_capture_devices(keyboard=True, mouse=True)
except AttributeError:
    raise RuntimeError("Wrong interception package installed. Run: pip install interception-python")
from mss import mss
from mss.tools import to_png
from PIL import ImageGrab
import shared_vars

def _cursor_pos():
    class _POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = _POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return pt.x, pt.y

try:
    from pathgenerator import PDPathGenerator as _PDPathGenerator
    _pdgen = _PDPathGenerator()
    _PDPATH_AVAILABLE = True
except Exception:
    _pdgen = None
    _PDPATH_AVAILABLE = False

import profiles as _profiles

def _wind_mouse_fallback(tx, ty, G=9.0, W=3.0, M=15.0, D=12.0):
    sx, sy = _cursor_pos()
    dist = math.hypot(tx - sx, ty - sy)
    if dist < 2:
        return []
    cx, cy = float(sx), float(sy)
    vx = vy = wx = wy = 0.0
    pts = []
    max_steps = max(100, int(dist / 3))
    for _ in range(max_steps):
        remaining = math.hypot(tx - cx, ty - cy)
        if remaining < 1:
            break
        w_mag = min(W, remaining)
        if remaining >= D:
            wx = wx / math.sqrt(3) + (random.random() * 2 - 1) * w_mag / math.sqrt(5)
            wy = wy / math.sqrt(3) + (random.random() * 2 - 1) * w_mag / math.sqrt(5)
        else:
            wx /= math.sqrt(3)
            wy /= math.sqrt(3)
        vx = (vx + G * (tx - cx) / remaining + wx) / math.sqrt(2)
        vy = (vy + G * (ty - cy) / remaining + wy) / math.sqrt(2)
        speed = math.hypot(vx, vy)
        if speed > M:
            cap = M / 2 + random.random() * M / 2
            vx = vx / speed * cap
            vy = vy / speed * cap
        cx += vx
        cy += vy
        pts.append((int(cx), int(cy)))
    pts.append((tx, ty))
    return pts

def _generate_path(tx, ty):
    sx, sy = _cursor_pos()
    if math.hypot(tx - sx, ty - sy) < 2:
        return []

    if not _PDPATH_AVAILABLE:
        return _wind_mouse_fallback(tx, ty)

    prof = _profiles.get_profile()
    jitter = prof["endpoint_jitter_px"]
    ex = tx + random.randint(-jitter, jitter)
    ey = ty + random.randint(-jitter, jitter)
    try:
        path, _, _, _ = _pdgen.generate_path(
            sx, sy, ex, ey,
            canvas_width=EXPECTED_WIDTH or 1920,
            canvas_height=EXPECTED_HEIGHT or 1080,
            mouse_velocity=prof["mouse_velocity"],
            noise=prof["noise"],
            arc_strength=prof["arc_strength"],
            overshoot_prob=prof["overshoot_prob"],
            variance=prof["variance"],
        )
        pts = [(int(p[0]), int(p[1])) for p in path]
        if not pts or pts[-1] != (tx, ty):
            pts.append((tx, ty))
        return pts
    except Exception:
        return _wind_mouse_fallback(tx, ty)

def _bezier_move(tx, ty, duration=None):
    sx, sy = _cursor_pos()
    dist = math.hypot(tx - sx, ty - sy)
    if dist < 2:
        return
    prof = _profiles.get_profile()
    if duration is None:
        dlo, dhi = prof.get("move_duration", (0.07, 0.16))
        duration = random.uniform(dlo, dhi)
    jlo, jhi = prof["step_delay_jitter"]
    duration *= random.uniform(jlo, jhi)
    pts = _generate_path(tx, ty)
    if not pts:
        interception.move_to(tx, ty)
        return
    delay = min(duration / len(pts), 0.006)
    for px, py in pts:
        interception.move_to(px, py)
        time.sleep(delay * random.uniform(0.6, 1.4))

REFERENCE_WIDTH_1440P = 2560
REFERENCE_HEIGHT_1440P = 1440
REFERENCE_WIDTH_1080P = 1920
REFERENCE_HEIGHT_1080P = 1080
REFERENCE_ASPECT_RATIO = 16/9

CLEAN_LOGS_ENABLED = True

MONITOR_WIDTH: int | None = None
MONITOR_HEIGHT: int | None = None
EXPECTED_WIDTH: int | None = None
EXPECTED_HEIGHT: int | None = None
IS_NON_STANDARD_RATIO: bool | None = None 

_thread_local = threading.local()
_sct_instances = {}
_sct_lock = threading.Lock()
_capture_heartbeat = {}

def get_sct():
    tid = threading.current_thread().ident
    with _sct_lock:
        if tid not in _sct_instances:
            _sct_instances[tid] = mss()
        return _sct_instances[tid]

def reset_sct(target_thread_id=None):
    tid = target_thread_id if target_thread_id is not None else threading.current_thread().ident
    try:
        with _sct_lock:
            sct = _sct_instances.pop(tid, None)
        if sct is not None:
            try:
                sct.close()
            except Exception:
                pass
        _template_cache.clear()
        logger.info("Screen capture and template cache reset")
    except Exception as e:
        logger.error(f"Error resetting SCT: {e}")

_template_cache = {}

def get_base_path():
    if getattr(sys, 'frozen', False):
        return sys._MEIPASS
    else:
        folder_path = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(folder_path) == 'src':
            return os.path.dirname(folder_path)
        return folder_path

BASE_PATH = get_base_path()

def resource_path(relative_path):
    base_path = BASE_PATH
    return os.path.join(base_path, relative_path)

class NoMillisecondsFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(record.created))
    
    def format(self, record):
        formatted = super().format(record)
        if hasattr(record, 'dirty') and record.dirty:
            formatted += " | DIRTY"
        return formatted

LOG_DIR = os.path.join(BASE_PATH, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILENAME = os.path.join(LOG_DIR, "Logs.log")

handler = RotatingFileHandler(LOG_FILENAME, maxBytes=1*1024*1024, backupCount=1, encoding='utf-8')
formatter = NoMillisecondsFormatter(
    fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
    datefmt='%d/%m/%Y %H:%M:%S'
)
handler.setFormatter(formatter)

class DirtyLogger(logging.Logger):
    def _log(self, level, msg, args, exc_info=None, extra=None, stack_info=False, dirty=False):
        if extra is None:
            extra = {}
        extra['dirty'] = dirty
        super()._log(level, msg, args, exc_info, extra, stack_info)
    
    def debug(self, msg, *args, dirty=False, **kwargs):
        if self.isEnabledFor(logging.DEBUG):
            self._log(logging.DEBUG, msg, args, dirty=dirty, **kwargs)
    
    def info(self, msg, *args, dirty=False, **kwargs):
        if self.isEnabledFor(logging.INFO):
            self._log(logging.INFO, msg, args, dirty=dirty, **kwargs)
    
    def warning(self, msg, *args, dirty=False, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log(logging.WARNING, msg, args, dirty=dirty, **kwargs)
    
    def error(self, msg, *args, dirty=False, **kwargs):
        if self.isEnabledFor(logging.ERROR):
            self._log(logging.ERROR, msg, args, dirty=dirty, **kwargs)
    
    def critical(self, msg, *args, dirty=False, **kwargs):
        if self.isEnabledFor(logging.CRITICAL):
            self._log(logging.CRITICAL, msg, args, dirty=dirty, **kwargs)

try:
    from logger import AsyncDirtyLogger, start_async_logging, set_logging_enabled, is_logging_enabled
    ASYNC_LOGGING_AVAILABLE = True
except ImportError:
    ASYNC_LOGGING_AVAILABLE = False

if ASYNC_LOGGING_AVAILABLE:
    logging.setLoggerClass(AsyncDirtyLogger)
else:
    logging.setLoggerClass(DirtyLogger)

logging.getLogger().handlers.clear()
logging.basicConfig(
    level=logging.DEBUG,
    handlers=[handler],
    force=True
)

logger = logging.getLogger(__name__)

def initialize_async_logging():
    if ASYNC_LOGGING_AVAILABLE:
        try:
            start_async_logging(LOG_FILENAME)
            return True
        except Exception as e:
            logger.warning(f"Failed to initialize async logging: {e}")
            return False
    return False

def detect_monitor_resolution():
    global MONITOR_WIDTH, MONITOR_HEIGHT, IS_NON_STANDARD_RATIO, EXPECTED_WIDTH, EXPECTED_HEIGHT

    monitor_index = getattr(shared_vars, 'game_monitor', 1)
    
    try:
        monitors = get_sct().monitors
        if monitor_index >= len(monitors):
            logger.warning(f"Monitor index {monitor_index} invalid. Defaulting to primary.")
            monitor_index = 1
            
        monitor = monitors[monitor_index]
        MONITOR_WIDTH = monitor['width']
        MONITOR_HEIGHT = monitor['height']
        
        logger.info(f"Detected montior size: {MONITOR_WIDTH}x{MONITOR_HEIGHT}")

        aspect_ratio = MONITOR_WIDTH / MONITOR_HEIGHT
        IS_NON_STANDARD_RATIO = not(abs(aspect_ratio - REFERENCE_ASPECT_RATIO) < 0.0001)

        EXPECTED_WIDTH = MONITOR_WIDTH
        EXPECTED_HEIGHT = MONITOR_HEIGHT
        if IS_NON_STANDARD_RATIO:
            if aspect_ratio > REFERENCE_ASPECT_RATIO:
                EXPECTED_WIDTH = round(MONITOR_HEIGHT * REFERENCE_ASPECT_RATIO)
            else:
                EXPECTED_HEIGHT = round(MONITOR_WIDTH / REFERENCE_ASPECT_RATIO)
            logger.info(f"Non-standard monitor ratio detected (expect {EXPECTED_WIDTH}x{EXPECTED_HEIGHT} instead)")

        return MONITOR_WIDTH, MONITOR_HEIGHT
    except Exception as e:
        logger.error(f"Error detecting monitor resolution: {e}")
        MONITOR_WIDTH = 1920
        MONITOR_HEIGHT = 1080
        EXPECTED_WIDTH = 1920
        EXPECTED_HEIGHT = 1080
        IS_NON_STANDARD_RATIO = False
        return 1920, 1080

detect_monitor_resolution()

def random_choice(list):
    return secrets.choice(list)

def sleep(x):
    time.sleep(x)

def mouse_scroll(amount):
    interception.scroll(amount)

def _validate_monitor_index(monitor_index, fallback=1):
    if monitor_index >= len(get_sct().monitors):
        logger.warning(f"Monitor index {monitor_index} out of range")
        return fallback
    return monitor_index

def get_monitor_info(monitor_index=None):
    mon_idx = monitor_index if monitor_index is not None else shared_vars.game_monitor
    mon_idx = _validate_monitor_index(mon_idx)
    return get_sct().monitors[mon_idx]

def get_MonCords(x, y):
    mon = get_monitor_info()
    return mon['left'] + x, mon['top'] + y

def mouse_move(x, y):
    real_x, real_y = get_MonCords(x, y)
    _bezier_move(real_x, real_y)

def mouse_click():
    if logger.isEnabledFor(logging.DEBUG):
        caller_info = _get_caller_info()
        cx, cy = _cursor_pos()
        logger.debug(f"Mouse click at ({cx}, {cy}) - {caller_info}", dirty=True)
    interception.click()

def mouse_hold():
    interception.mouse_down("left")
    sleep(2)
    interception.mouse_up("left")

def mouse_down():
    interception.mouse_down("left")

def mouse_up():
    interception.mouse_up("left")

def mouse_move_click(x, y, log_click=True):
    if log_click and logger.isEnabledFor(logging.DEBUG):
        caller_info = _get_caller_info()
        logger.debug(f"Mouse move and click to ({x}, {y}) - {caller_info}", dirty=True)
    prof = _profiles.get_profile()
    real_x, real_y = get_MonCords(x, y)
    real_x += random.randint(-3, 3)
    real_y += random.randint(-3, 3)

    pause, drift = _profiles.rhythm_tick()
    if pause > 0:
        if drift != (0, 0):
            interception.move_to(
                max(0, real_x + drift[0]),
                max(0, real_y + drift[1]),
            )
        time.sleep(pause)

    if random.random() < prof["overshoot_prob"]:
        ox = real_x + random.randint(6, 14) * random.choice([-1, 1])
        oy = real_y + random.randint(6, 14) * random.choice([-1, 1])
        _bezier_move(ox, oy)
        time.sleep(random.lognormvariate(
            prof["lognorm_pre_move_mu"], prof["lognorm_pre_move_sig"]
        ))

    _bezier_move(real_x, real_y)
    time.sleep(random.lognormvariate(
        prof["lognorm_pre_click_mu"], prof["lognorm_pre_click_sig"]
    ))
    interception.mouse_down("left")
    time.sleep(random.uniform(0.04, 0.09))
    interception.mouse_up("left")

def mouse_drag(x, y, seconds=1, hold=0.06, release_hold=0.06):
    if logger.isEnabledFor(logging.DEBUG):
        caller_info = _get_caller_info()
        logger.debug(f"Mouse drag to ({x}, {y}) over {seconds}s - {caller_info}", dirty=True)
    real_x, real_y = get_MonCords(x, y)
    interception.mouse_down("left")
    time.sleep(hold)
    _bezier_move(real_x, real_y, duration=seconds * random.uniform(0.9, 1.1))
    time.sleep(release_hold)
    interception.mouse_up("left")

def key_press(Key, presses=1):
    for _ in range(presses):
        interception.press(Key)

def capture_screen(monitor_index=None):
    mon_idx = monitor_index if monitor_index is not None else shared_vars.game_monitor
    mon_idx = _validate_monitor_index(mon_idx)

    monitor = get_sct().monitors[mon_idx]

    screenshot = get_sct().grab(monitor)
    img = np.array(screenshot)

    img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    _capture_heartbeat[threading.current_thread().ident] = time.time()
    return img

def save_match_screenshot(screenshot, top_left, bottom_right, template_path, match_index):
    match_region = screenshot[top_left[1]:bottom_right[1], top_left[0]:bottom_right[0]]

    output_path = os.path.join(BASE_PATH, "higher_res", template_path)
    output_dir = os.path.dirname(output_path)
    os.makedirs(output_dir, exist_ok=True)

    output_path = os.path.splitext(output_path)[0]  
    output_path = f"{output_path}.png"  
    if os.path.exists(output_path):
        return
    cv2.imwrite(output_path, match_region)

def is_custom_1080p_image(template_path):
    return "CustomAdded1080p" in template_path

def is_custom_fuse_image(template_path):
    return "CustomFuse" in template_path

def get_template_reference_resolution(template_path):
    if is_custom_1080p_image(template_path):
        return REFERENCE_WIDTH_1080P, REFERENCE_HEIGHT_1080P
    elif "/1366/" in template_path or "\\1366\\" in template_path:
        return 1366, 768
    elif "mirror/navigation" in template_path or "mirror\\navigation" in template_path:
        return REFERENCE_WIDTH_1080P, REFERENCE_HEIGHT_1080P
    else:
        return REFERENCE_WIDTH_1440P, REFERENCE_HEIGHT_1440P

def _extract_coordinates(filtered_boxes, area="center", crop_offset_x=0, crop_offset_y=0):
    found_elements = []
    for (x1, y1, x2, y2) in filtered_boxes:
        x1 += crop_offset_x
        y1 += crop_offset_y
        x2 += crop_offset_x
        y2 += crop_offset_y
        
        if area == "all":
            top_x, top_y = (x1 + x2) // 2, y1
            left_x, left_y = x1, (y1 + y2) // 2
            right_x, right_y = x2, (y1 + y2) // 2
            bottom_x, bottom_y = (x1 + x2) // 2, y2
            center_x, center_y = (x1 + x2) // 2, (y1 + y2) // 2
            found_elements.append({
                'top': (top_x, top_y),
                'left': (left_x, left_y),
                'right': (right_x, right_y),
                'bottom': (bottom_x, bottom_y),
                'center': (center_x, center_y)
            })
        elif area == "bottom":
            x = (x1 + x2) // 2
            y = y2
            found_elements.append((x, y))
        elif area == "top":
            x = (x1 + x2) // 2
            y = y1
            found_elements.append((x, y))
        elif area == "left":
            x = x1
            y = (y1 + y2) // 2
            found_elements.append((x, y))
        elif area == "right":
            x = x2
            y = (y1 + y2) // 2
            found_elements.append((x, y))
        else: 
            x = (x1 + x2) // 2
            y = (y1 + y2) // 2
            found_elements.append((x, y))
    
    return found_elements if found_elements else []

def _get_caller_info():
    try:
        stack = inspect.stack()
        for frame_info in stack:
            filename = frame_info.filename
            if not filename.endswith('common.py'):
                module_name = os.path.splitext(os.path.basename(filename))[0]
                function_name = frame_info.function
                line_number = frame_info.lineno
                return f"{module_name}.{function_name}:{line_number}"
    except Exception:
        pass
    return "unknown"

def _base_match_template(template_path, threshold=0.8, grayscale=False,no_grayscale=False, debug=False, area="center", quiet_failure=False, x1=None, y1=None, x2=None, y2=None, screenshot=None, enable_scaling=False):
    
    full_template_path = resource_path(template_path)
        
    if screenshot is None:
        screenshot = capture_screen()
    original_screenshot_height, original_screenshot_width = screenshot.shape[:2]

    crop_offset_x = 0
    crop_offset_y = 0
    if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
        x1 = max(0, min(x1, original_screenshot_width))
        y1 = max(0, min(y1, original_screenshot_height))
        x2 = max(x1, min(x2, original_screenshot_width))
        y2 = max(y1, min(y2, original_screenshot_height))

        screenshot = screenshot[y1:y2, x1:x2]
        crop_offset_x = x1
        crop_offset_y = y1

    screenshot_height, screenshot_width = original_screenshot_height, original_screenshot_width

    if not no_grayscale and (grayscale or shared_vars.convert_images_to_grayscale):
        screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    
    base_width, base_height = get_template_reference_resolution(full_template_path)
    
    scale_factor_x = EXPECTED_WIDTH / base_width
    scale_factor_y = EXPECTED_HEIGHT / base_height
    scale_factor = min(scale_factor_x, scale_factor_y)

    if no_grayscale:
        color_flag = cv2.IMREAD_COLOR
    else:
        color_flag = cv2.IMREAD_GRAYSCALE if (grayscale or shared_vars.convert_images_to_grayscale) else cv2.IMREAD_COLOR

    cache_key = (full_template_path, color_flag)
    if cache_key in _template_cache:
        original_template = _template_cache[cache_key]
    else:
        try:
            raw = np.fromfile(full_template_path, dtype=np.uint8)
            original_template = cv2.imdecode(raw, color_flag)
        except Exception:
            original_template = None
        if original_template is None:
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(f"Image file missing: {template_path} | File Exists: False", dirty=True)
            if quiet_failure:
                return []
            raise FileNotFoundError(f"Template image '{full_template_path}' not found.")
        _template_cache[cache_key] = original_template

    if enable_scaling:
        scales_to_test = [x / 100.0 for x in range(80, 121, 4)]
    else:
        scales_to_test = [1.0]

    best_max_val = -1.0
    best_result = None
    best_template_dims = (0, 0)
    best_scale_found = 1.0

    for scale_adj in scales_to_test:
        if is_custom_fuse_image(full_template_path):
            effective_scale = scale_adj
        else:
            effective_scale = scale_factor * scale_adj

        if effective_scale != 1.0:
            curr_template = cv2.resize(original_template, None, fx=effective_scale, fy=effective_scale, interpolation=cv2.INTER_LINEAR)
        else:
            curr_template = original_template

        if no_grayscale:
            if len(screenshot.shape) == 2: screenshot = cv2.cvtColor(screenshot, cv2.COLOR_GRAY2BGR)
            if len(curr_template.shape) == 2: curr_template = cv2.cvtColor(curr_template, cv2.COLOR_GRAY2BGR)
        else:
            if (grayscale or shared_vars.convert_images_to_grayscale):
                if len(screenshot.shape) == 3: screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
                if len(curr_template.shape) == 3: curr_template = cv2.cvtColor(curr_template, cv2.COLOR_BGR2GRAY)

        if curr_template.shape[0] > screenshot.shape[0] or curr_template.shape[1] > screenshot.shape[1]:
            continue

        res = cv2.matchTemplate(screenshot, curr_template, cv2.TM_CCOEFF_NORMED)
        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

        if best_result is None or max_val > best_max_val:
            best_max_val = max_val
            best_result = res
            best_template_dims = curr_template.shape[:2]
            best_scale_found = scale_adj

    result = best_result
    template_height, template_width = best_template_dims

    if enable_scaling and (debug or shared_vars.debug_image_matches):
        logger.debug(f"Multi-scale match for {os.path.basename(template_path)}: Best Scale={best_scale_found:.2f}, Confidence={best_max_val:.4f}", dirty=True)
    
    if scale_factor > 1.8:
        threshold = threshold - 0.03
    total_adjustment = get_total_threshold_adjustment(template_path)
    threshold = threshold + total_adjustment
    
    locations = np.where(result >= threshold)
    
    boxes = []
    match_scores = []
    
    for pt in zip(*locations[::-1]):
        top_left = pt
        bottom_right = (top_left[0] + template_width, top_left[1] + template_height)
        boxes.append([top_left[0], top_left[1], bottom_right[0], bottom_right[1]])
        match_scores.append(result[top_left[1], top_left[0]])
    
    boxes = np.array(boxes)
    filtered_boxes = non_max_suppression_fast(boxes)
    
    if not quiet_failure:
        if logger.isEnabledFor(logging.DEBUG):
            caller_info = _get_caller_info()
            highest_match_rate = result.max() if result.size > 0 else 0.0
            if len(filtered_boxes) > 0:
                locations = []
                for box in filtered_boxes:
                    center_x = int((box[0] + box[2]) / 2) + crop_offset_x
                    center_y = int((box[1] + box[3]) / 2) + crop_offset_y
                    locations.append(f"({center_x},{center_y})")
                locations_str = ", ".join(locations)
                logger.debug(f"Match found: {template_path} | Confidence: {highest_match_rate:.4f} | File Exists: True | Locations: {locations_str} | Caller: {caller_info}", dirty=True)
            else:
                logger.debug(f"Match not found: {template_path} | Confidence: {highest_match_rate:.4f} | File Exists: True | Caller: {caller_info}", dirty=True)
    
    if (debug or shared_vars.debug_image_matches) and len(filtered_boxes) > 0:
        
        def draw_debug_rectangle(x, y, width, height, duration=1.0):
            
            if platform.system() != 'Windows':
                return
                
            def draw_and_erase():
                try:
                    user32 = ctypes.windll.user32
                    gdi32 = ctypes.windll.gdi32
                    
                    mon = get_monitor_info()
                    x_int = int(mon['left'] + x)
                    y_int = int(mon['top'] + y)
                    w_int = int(width)
                    h_int = int(height)
                    
                    desktop_dc = user32.GetDC(0)
                    
                    pen = gdi32.CreatePen(0, 4, 0x05B0FE)
                    old_pen = gdi32.SelectObject(desktop_dc, pen)
                    old_brush = gdi32.SelectObject(desktop_dc, gdi32.GetStockObject(5))
                    
                    gdi32.Rectangle(desktop_dc, x_int, y_int, x_int + w_int, y_int + h_int)
                    
                    time.sleep(duration)
                    
                    rect = wintypes.RECT(x_int - 5, y_int - 5, x_int + w_int + 5, y_int + h_int + 5)
                    user32.InvalidateRect(0, ctypes.byref(rect), 1)
                    
                    gdi32.SelectObject(desktop_dc, old_pen)
                    gdi32.SelectObject(desktop_dc, old_brush)
                    gdi32.DeleteObject(pen)
                    user32.ReleaseDC(0, desktop_dc)
                    
                except Exception as e:
                    print(f"Debug rectangle error: {e}")
            
            threading.Thread(target=draw_and_erase, daemon=True).start()
        
        for (x1, y1, x2, y2) in filtered_boxes:
            padding = 8
            draw_debug_rectangle(
                x1 - padding, 
                y1 - padding, 
                (x2 - x1) + (padding * 2), 
                (y2 - y1) + (padding * 2), 
                2.0
            )
    
    return _extract_coordinates(filtered_boxes, area, crop_offset_x, crop_offset_y)

def get_total_threshold_adjustment(template_path):
    config = shared_vars.image_threshold_config

    global_adj = config.get("global_adjustment", 0.0)
    folder_adj = get_folder_specific_adjustment(template_path)
    path_adj = get_path_specific_adjustment(template_path)
    apply_global_to_modified = config.get("apply_global_to_modified", True)

    total_specific_adj = folder_adj + path_adj
    
    if total_specific_adj != 0.0: 
        if apply_global_to_modified:
            return global_adj + total_specific_adj 
        else:
            return total_specific_adj 
    else: 
        return global_adj 

def get_folder_specific_adjustment(template_path):
    config = shared_vars.image_threshold_config
    folder_adjustments = config.get("folder_adjustments", {})

    folder_path = os.path.dirname(template_path)
    return folder_adjustments.get(folder_path, 0.0)

def get_path_specific_adjustment(template_path):
    config = shared_vars.image_threshold_config
    image_adjustments = config.get("image_adjustments", {})
    return image_adjustments.get(template_path, 0.0)

def match_image(template_path, threshold=0.8, area="center",mousegoto200=False, grayscale=False, no_grayscale=False, debug=False, quiet_failure=False, x1=None, y1=None, x2=None, y2=None, screenshot=None, enable_scaling=False):
    if mousegoto200:
        mouse_move(*scale_coordinates_1080p(200, 200))
    return _base_match_template(template_path, threshold, grayscale, no_grayscale, debug, area, quiet_failure, x1, y1, x2, y2, screenshot, enable_scaling=enable_scaling)

def greyscale_match_image(template_path, threshold=0.75, area="center", no_grayscale=False, debug=False, quiet_failure=False, x1=None, y1=None, x2=None, y2=None, screenshot=None):
    return _base_match_template(template_path, threshold, grayscale=True, no_grayscale=no_grayscale, debug=debug, area=area, quiet_failure=quiet_failure, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot)

def debug_match_image(template_path, threshold=0.8, area="center", grayscale=False, no_grayscale=False, x1=None, y1=None, x2=None, y2=None, screenshot=None):
    return _base_match_template(template_path, threshold, grayscale=grayscale, no_grayscale=no_grayscale, debug=True, area=area, x1=x1, y1=y1, x2=x2, y2=y2, screenshot=screenshot)

def proximity_check(list1, list2, threshold):
    close_pairs = set() 
    for coord1 in list1:
        for coord2 in list2:
            distance = np.sqrt((coord1[0] - coord2[0]) ** 2 + (coord1[1] - coord2[1]) ** 2)
            if distance < threshold:
                close_pairs.add(coord1)
    return close_pairs

def proximity_check_fuse(list1, list2, x_threshold ,threshold):
    close_pairs = set()
    for coord1 in list1:
        for coord2 in list2:
            x_difference = abs(coord1[0] - coord2[0])
            if x_difference < x_threshold: 
                y_difference = abs(coord1[1] - coord2[1])
                if y_difference < threshold: 
                    close_pairs.add(coord1)
    return close_pairs

def enhanced_proximity_check(container_input, content_input, 
                           expand_left=0, expand_right=0, 
                           expand_above=0, expand_below=0, 
                           threshold=0.8, use_bounding_box=True, return_bool=False):
    if isinstance(container_input, str):
        if use_bounding_box:
            container_data = ifexist_match(container_input, threshold, area="all")
        else:
            container_data = ifexist_match(container_input, threshold)
        if not container_data:
            return False if return_bool else []
    elif isinstance(container_input, list):
        container_data = container_input
        if not container_data:
            return False if return_bool else []
    else:
        return False if return_bool else []

    if isinstance(content_input, str):
        content_coords = ifexist_match(content_input, threshold)
        if not content_coords:
            return False if return_bool else []
    elif isinstance(content_input, list):
        content_coords = content_input
        if not content_coords:
            return False if return_bool else []
    else:
        return False if return_bool else []
    
    matching_coords = []

    for content_x, content_y in content_coords:
        found_match = False
        
        for container_item in container_data:
            if use_bounding_box and isinstance(container_item, dict):
                base_x_min = container_item['left'][0]
                base_x_max = container_item['right'][0]
                base_y_min = container_item['top'][1]
                base_y_max = container_item['bottom'][1]

                x_min = base_x_min - expand_left
                x_max = base_x_max + expand_right
                y_min = base_y_min - expand_above
                y_max = base_y_max + expand_below
                
            elif not use_bounding_box and isinstance(container_item, tuple):
                center_x, center_y = container_item
                x_min = center_x - expand_left
                x_max = center_x + expand_right
                y_min = center_y - expand_above
                y_max = center_y + expand_below
                
            else:
                continue

            if (x_min <= content_x <= x_max and y_min <= content_y <= y_max):
                matching_coords.append((content_x, content_y))
                found_match = True
                break  

        if return_bool and found_match:
            return True
                
    return bool(matching_coords) if return_bool else matching_coords

def get_resolution(monitor_index=None):
    mon = get_monitor_info(monitor_index)
    return mon['width'], mon['height']

def non_max_suppression_fast(boxes, overlapThresh=0.5):
    if len(boxes) == 0:
        return []

    if boxes.dtype.kind == "i":
        boxes = boxes.astype("float")

    pick = []

    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    x2 = boxes[:, 2]
    y2 = boxes[:, 3]

    area = (x2 - x1 + 1) * (y2 - y1 + 1)
    idxs = np.argsort(y2)

    while len(idxs) > 0:
        last = len(idxs) - 1
        i = idxs[last]
        pick.append(i)

        xx1 = np.maximum(x1[i], x1[idxs[:last]])
        yy1 = np.maximum(y1[i], y1[idxs[:last]])
        xx2 = np.minimum(x2[i], x2[idxs[:last]])
        yy2 = np.minimum(y2[i], y2[idxs[:last]])

        w = np.maximum(0, xx2 - xx1 + 1)
        h = np.maximum(0, yy2 - yy1 + 1)

        overlap = (w * h) / area[idxs[:last]]

        idxs = np.delete(idxs, np.concatenate(([last], np.where(overlap > overlapThresh)[0])))

    return boxes[pick].astype("int")

def get_aspect_ratio(monitor_index=None):
    width, height = get_resolution(monitor_index)
    if (width / 4) * 3 == height:
        return "4:3"
    if (width / 16) * 9 == height:
        return "16:9"
    if (width / 16) * 10 == height:
        return "16:10"
    else:
        return None

def _uniform_scale_coordinates(x, y, reference_width, reference_height, use_uniform=True):
    scale_factor_x = MONITOR_WIDTH / reference_width
    scale_factor_y = MONITOR_HEIGHT / reference_height

    x_offset = shared_vars.x_offset
    y_offset = shared_vars.y_offset
    
    if use_uniform:
        scale_factor = min(scale_factor_x, scale_factor_y)
        scaled_x = round(x * scale_factor) + x_offset
        scaled_y = round(y * scale_factor) + y_offset
    else:
        scaled_x = round(x * scale_factor_x) + x_offset
        scaled_y = round(y * scale_factor_y) + y_offset
    
    return scaled_x, scaled_y

def _scale_single_coordinate(coord, reference_dimension, actual_dimension, offset=0):
    return round(coord * actual_dimension / reference_dimension) + offset

def padding_none_16_9_monitor(x: int, y: int) -> tuple[int, int]:
    if IS_NON_STANDARD_RATIO:
        x_offset = (MONITOR_WIDTH - EXPECTED_WIDTH)//2
        y_offset = (MONITOR_HEIGHT - EXPECTED_HEIGHT)//2
        return x + x_offset, y + y_offset
    return x, y

def scale_x(x: int, *, padding: bool = True) -> int:
    _x = _scale_single_coordinate(x, REFERENCE_WIDTH_1440P, EXPECTED_WIDTH, shared_vars.x_offset)
    if padding:
        _x, _ = padding_none_16_9_monitor(_x, 0)
    return _x

def scale_y(y: int, *, padding: bool = True) -> int:
    _y = _scale_single_coordinate(y, REFERENCE_HEIGHT_1440P, EXPECTED_HEIGHT, shared_vars.y_offset)
    if padding:
        _, _y = padding_none_16_9_monitor(0, _y)
    return _y

def scale_x_1080p(x: int, *, padding: bool = True) -> int:
    _x = _scale_single_coordinate(x, REFERENCE_WIDTH_1080P, EXPECTED_WIDTH, shared_vars.x_offset)
    if padding:
        _x, _ = padding_none_16_9_monitor(_x, 0)
    return _x

def scale_y_1080p(y: int, *, padding: bool = True) -> int:
    _y = _scale_single_coordinate(y, REFERENCE_HEIGHT_1080P, EXPECTED_HEIGHT, shared_vars.y_offset)
    if padding:
        _, _y = padding_none_16_9_monitor(0, _y)
    return _y

def uniform_scale_single(coord):
    scale_factor_x = EXPECTED_WIDTH / REFERENCE_WIDTH_1440P
    scale_factor_y = EXPECTED_HEIGHT / REFERENCE_HEIGHT_1440P
    scale_factor = min(scale_factor_x, scale_factor_y)
    return round(scale_factor * coord)

def uniform_scale_coordinates(x, y):
    return scale_coordinates_1440p(x, y)

def uniform_scale_coordinates_1080p(x, y):
    return scale_coordinates_1080p(x, y)

def scale_coordinates_1440p(x, y):
    return scale_x(x), scale_y(y)

def scale_coordinates_1080p(x, y):
    return scale_x_1080p(x), scale_y_1080p(y)

def scale_offset_1440p(x: int, y: int) -> tuple[int, int]:
    return scale_x(x, padding=False), scale_y(y, padding=False)

def scale_offset_1080p(x: int, y: int) -> tuple[int, int]:
    return scale_x_1080p(x, padding=False), scale_y_1080p(y, padding=False)

def click_skip(times):
    mouse_move_click(*scale_coordinates_1080p(895, 465))
    for i in range(times):
        mouse_click()

def wait_skip(img_path, threshold=0.8):
    mouse_move_click(*scale_coordinates_1080p(895, 465))

    if element_exist(img_path, threshold):
        click_matching(img_path, threshold)
        return

    while not element_exist(img_path, threshold):
        mouse_click()
        mouse_click()
        
    click_matching(img_path, threshold)

def click_matching(image_path, threshold=0.8, area="center", mousegoto200=False, grayscale=False, no_grayscale=False, debug=False, recursive=True, x1=None, y1=None, x2=None, y2=None, screenshot=None, quiet_failure=False, enable_scaling=False):

    if quiet_failure and recursive:
        full_path = resource_path(image_path)
        if not os.path.exists(full_path):
            return False

    while True:
        found = ifexist_match(image_path, threshold, area, mousegoto200, grayscale, no_grayscale, debug, x1, y1, x2, y2, screenshot, quiet_failure=quiet_failure, enable_scaling=enable_scaling)
        if found:
            x, y = found[0]
            mouse_move_click(x, y, log_click=False)
            delay = shared_vars.click_delay.value if hasattr(shared_vars.click_delay, 'value') else shared_vars.click_delay
            time.sleep(delay)
            return True
        
        if not recursive:
            return False

        screenshot = None
        time.sleep(0.05)
    
def element_exist(img_path, threshold=0.8, area="center",mousegoto200=False, grayscale=False, no_grayscale=False, debug=False, quiet_failure=False, x1=None, y1=None, x2=None, y2=None, screenshot=None):
    result = match_image(img_path, threshold, area, mousegoto200, grayscale, no_grayscale, debug, quiet_failure, x1, y1, x2, y2, screenshot)
    return result

def ifexist_match(img_path, threshold=0.8, area="center",mousegoto200=False, grayscale=False, no_grayscale=False, debug=False, x1=None, y1=None, x2=None, y2=None, screenshot=None, quiet_failure=False, enable_scaling=False):
    result = match_image(img_path, threshold, area,mousegoto200, grayscale, no_grayscale, debug, quiet_failure, x1, y1, x2, y2, screenshot, enable_scaling=enable_scaling)
    return result

def squad_order(status):
    squads = shared_vars.ConfigCache.get_config("squad_order")
    squad = squads.get(status, {})

    character_positions = {
        "yisang": (580, 500),
        "faust": (847, 500),
        "donquixote": (1113, 500),
        "ryoshu": (1380, 500),
        "meursault": (1647, 500),
        "honglu": (1913, 500),
        "heathcliff": (580, 900),
        "ishmael": (847, 900),
        "rodion": (1113, 900),
        "sinclair": (1380, 900),
        "outis": (1647, 900),
        "gregor": (1913, 900)
    }
    
    position_to_char = {pos: name for name, pos in squad.items()}
    
    sinner_order = []
    for i in range(1, 13):
        char_name = position_to_char.get(i)
        if char_name and char_name in character_positions:
            base_x, base_y = character_positions[char_name]
            scaled_x, scaled_y = scale_coordinates_1440p(base_x, base_y)
            sinner_order.append((scaled_x, scaled_y))
    
    return sinner_order

def luminence(x,y, screenshot=None):
    if screenshot is None:
        screenshot = capture_screen()
    pixel_image = screenshot[y, x]
    coeff = (int(pixel_image[0]) + int(pixel_image[1]) + int(pixel_image[2])) / 3
    return coeff

def error_screenshot():
    error_dir = os.path.join(BASE_PATH, "error")
    os.makedirs(error_dir, exist_ok=True)
    monitor = get_sct().monitors[shared_vars.game_monitor]  
    screenshot = get_sct().grab(monitor)
    png = to_png(screenshot.rgb, screenshot.size)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    with open(os.path.join(error_dir, timestamp + ".png"), "wb") as f:
        f.write(png)

def set_game_monitor(monitor_index):
    if monitor_index < 1 or monitor_index >= len(get_sct().monitors):
        logger.warning(f"Invalid monitor index {monitor_index} (valid: 1-{len(get_sct().monitors)-1})")
        shared_vars.game_monitor = 1
    else:
        shared_vars.game_monitor = monitor_index

    detect_monitor_resolution()
    return shared_vars.game_monitor

def list_available_monitors():
    monitors = []
    for i, monitor in enumerate(get_sct().monitors):
        if i == 0:  
            continue
        monitors.append({
            "index": i,
            "left": monitor["left"],
            "top": monitor["top"],
            "width": monitor["width"],
            "height": monitor["height"]
        })
    return monitors

def get_monitor_resolution():
    return MONITOR_WIDTH, MONITOR_HEIGHT

def check_internet_connection(timeout=5):
    import urllib.request
    import urllib.error
    
    try:
        urllib.request.urlopen('https://www.google.com', timeout=timeout)
        return True
    except (urllib.error.URLError, OSError):
        return False

def draw_debug_rect(x, y, width, height, duration=2):
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    desktop_dc = user32.GetDC(0)
    pen = gdi32.CreatePen(0, 4, 0x05B0FE)
    old_pen = gdi32.SelectObject(desktop_dc, pen)
    old_brush = gdi32.SelectObject(desktop_dc, gdi32.GetStockObject(5))
    
    gdi32.Rectangle(desktop_dc, int(x), int(y), int(x + width), int(y + height))
    
    time.sleep(duration)
    
    rect = wintypes.RECT(int(x) - 5, int(y) - 5, int(x + width) + 5, int(y + height) + 5)
    user32.InvalidateRect(0, ctypes.byref(rect), 1)
    
    gdi32.SelectObject(desktop_dc, old_pen)
    gdi32.SelectObject(desktop_dc, old_brush)
    gdi32.DeleteObject(pen)
    user32.ReleaseDC(0, desktop_dc)

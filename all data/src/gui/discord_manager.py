"""Ties the Discord bot to the main app.

Loads settings from config['Discord'], wires callbacks to process_handler,
reads stats/screenshots for periodic updates, and exposes stuck notification.
"""

import os
import io
import json
import logging
import threading

logger = logging.getLogger(__name__)

_bot = None
_bot_lock = threading.Lock()
_shared_vars_ref = None
_base_path = None
_log_handler = None
_last_stuck_alert = 0


class _DiscordStuckHandler(logging.Handler):
    """Forwards ERROR/CRITICAL log records to the Discord bot.

    Rate-limited to one alert per 60 seconds to avoid spam.
    """
    def __init__(self):
        super().__init__(level=logging.ERROR)

    def emit(self, record):
        global _last_stuck_alert
        try:
            import time as _time
            now = _time.time()
            if now - _last_stuck_alert < 60:
                return
            _last_stuck_alert = now
            msg = self.format(record)
            notify_stuck(msg[:300])
        except Exception:
            pass


def _get_stats():
    try:
        if not _base_path:
            return {}
        stats_path = os.path.join(_base_path, 'config', 'stats.json')
        if not os.path.exists(stats_path):
            return {'Status': 'No stats yet'}
        with open(stats_path, 'r', encoding='utf-8') as f:
            data = json.load(f) or {}
        md = data.get('mirror', {})
        runs = md.get('runs', 0)
        wins = md.get('wins', 0)
        losses = md.get('losses', 0)
        rate = f"{(wins/runs*100):.1f}%" if runs else "-"
        return {
            'MD Runs': runs,
            'Wins': wins,
            'Losses': losses,
            'Win Rate': rate,
            'Exp Runs': data.get('exp', {}).get('runs', 0),
            'Thread Runs': data.get('threads', {}).get('runs', 0),
            'Status': _current_status(),
        }
    except Exception as e:
        logger.error(f"_get_stats failed: {e}")
        return {'Error': str(e)}


def _current_status():
    try:
        from src.gui import process_handler
        name = process_handler.get_running_process_name()
        return f"Running: {name}" if name else "Idle"
    except Exception:
        return "Unknown"


def _get_screenshot():
    try:
        import common
        img = common.capture_screen()
        import cv2
        ok, buf = cv2.imencode('.png', img)
        if ok:
            return buf.tobytes()
    except Exception as e:
        logger.error(f"Discord screenshot failed: {e}")
    return None


class _StubVar:
    def __init__(self, val):
        self._val = val
    def get(self):
        return self._val


def _build_chain_context():
    """Build a minimal ui_context so chain_automation can run without tkinter widgets."""
    cfg = {}
    try:
        if _base_path:
            import json
            path = os.path.join(_base_path, 'config', 'gui_config.json')
            if os.path.exists(path):
                with open(path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f) or {}
    except Exception:
        cfg = {}

    chain_cfg = cfg.get('Chain', {}) if isinstance(cfg, dict) else {}

    return {
        'chain_threads_entry':  _StubVar(str(chain_cfg.get('threads_runs', 3))),
        'chain_exp_entry':      _StubVar(str(chain_cfg.get('exp_runs', 1))),
        'chain_mirror_entry':   _StubVar(str(chain_cfg.get('mirror_runs', 1))),
        'launch_game_var':      _StubVar(bool(chain_cfg.get('launch_game', True))),
        'collect_rewards_var':  _StubVar(bool(chain_cfg.get('collect_rewards', False))),
    }


def _check_busy():
    """Return (busy_bool, message) — True if anything is already running."""
    from src.gui import chain_automation, process_handler
    if chain_automation.chain_running:
        return True, "Chain already running"
    name = process_handler.get_running_process_name()
    if name:
        return True, f"Already running: {name}"
    return False, None


def _start_mirror():
    if _shared_vars_ref is None:
        return False, "shared_vars not registered"
    try:
        busy, reason = _check_busy()
        if busy:
            return False, reason
        from src.gui import process_handler
        ok = process_handler.start_mirror_dungeon(_shared_vars_ref)
        return (True, "Mirror Dungeon started") if ok else (False, "Failed to start Mirror Dungeon")
    except Exception as e:
        logger.error(f"Discord start_mirror failed: {e}")
        return False, f"Error: {e}"


def _start_exp():
    if _shared_vars_ref is None:
        return False, "shared_vars not registered"
    try:
        busy, reason = _check_busy()
        if busy:
            return False, reason
        from src.gui import process_handler
        ok = process_handler.start_exp_luxcavation(_shared_vars_ref)
        return (True, "Exp Luxcavation started") if ok else (False, "Failed to start Exp")
    except Exception as e:
        logger.error(f"Discord start_exp failed: {e}")
        return False, f"Error: {e}"


def _start_threads():
    if _shared_vars_ref is None:
        return False, "shared_vars not registered"
    try:
        busy, reason = _check_busy()
        if busy:
            return False, reason
        from src.gui import process_handler
        ok = process_handler.start_thread_luxcavation(_shared_vars_ref)
        return (True, "Thread Luxcavation started") if ok else (False, "Failed to start Threads")
    except Exception as e:
        logger.error(f"Discord start_threads failed: {e}")
        return False, f"Error: {e}"


def _start_chain():
    if _shared_vars_ref is None:
        return False, "shared_vars not registered"
    try:
        busy, reason = _check_busy()
        if busy:
            return False, reason
        from src.gui import chain_automation
        ctx = _build_chain_context()
        chain_automation.start_chain_automation(ctx, _shared_vars_ref)
        if chain_automation.chain_running:
            return True, "Chain Automation started"
        return False, "Chain failed to start (check config)"
    except Exception as e:
        logger.error(f"Discord start_chain failed: {e}")
        return False, f"Error: {e}"


def _stop_all():
    try:
        from src.gui import chain_automation, process_handler
        was_running = (chain_automation.chain_running or
                       process_handler.is_any_process_running())
        if chain_automation.chain_running:
            chain_automation.stop_chain_automation(None)
        else:
            process_handler.cleanup_processes()
        return (True, "All macros stopped") if was_running else (True, "Nothing was running")
    except Exception as e:
        logger.error(f"Discord stop_all failed: {e}")
        return False, f"Error: {e}"


def get_callbacks():
    """Returns the dict of callbacks passed to the bot."""
    return {
        'start_mirror':  _start_mirror,
        'start_exp':     _start_exp,
        'start_threads': _start_threads,
        'start_chain':   _start_chain,
        'stop_all':      _stop_all,
    }


def register_shared_vars(shared_vars, base_path):
    global _shared_vars_ref, _base_path
    _shared_vars_ref = shared_vars
    _base_path = base_path


def start(config):
    global _bot, _log_handler
    with _bot_lock:
        if _bot is not None and _bot.is_running():
            return True

        from src.discord_integration import DiscordBot

        d = config.get('Discord', {}) or {}
        if not d.get('enabled'):
            return False

        log_path = os.path.join(_base_path, 'logs', 'Logs.log') if _base_path else ''

        _bot = DiscordBot(
            token=d.get('bot_token', ''),
            channel_id=d.get('channel_id', ''),
            update_interval_minutes=int(d.get('update_interval_minutes', 15)),
            callbacks=get_callbacks(),
            get_stats_callback=_get_stats,
            get_screenshot_callback=_get_screenshot,
            log_path=log_path,
        )
        ok = _bot.start()

        if ok and _log_handler is None:
            _log_handler = _DiscordStuckHandler()
            _log_handler.setFormatter(logging.Formatter('%(name)s: %(message)s'))
            logging.getLogger().addHandler(_log_handler)
        return ok


def stop():
    global _bot, _log_handler
    with _bot_lock:
        if _log_handler is not None:
            try:
                logging.getLogger().removeHandler(_log_handler)
            except Exception:
                pass
            _log_handler = None
        if _bot is not None:
            _bot.stop()
            _bot = None


def notify_stuck(reason):
    with _bot_lock:
        if _bot is not None and _bot.is_running():
            _bot.notify_stuck(reason)


def notify_event(title, description, color=0x3498db):
    with _bot_lock:
        if _bot is not None and _bot.is_running():
            _bot.notify_event(title, description, color)


def is_running():
    with _bot_lock:
        return _bot is not None and _bot.is_running()

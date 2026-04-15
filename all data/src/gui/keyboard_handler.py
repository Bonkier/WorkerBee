import threading
import time
import logging

logger = logging.getLogger("gui_launcher")

try:
    from pynput import keyboard as _pynput_kbd
    _PYNPUT_AVAILABLE = True
except Exception:
    _PYNPUT_AVAILABLE = False
    logger.warning("pynput not available – global hotkeys disabled")


def _to_pynput_hotkey(hotkey_str):
    """Convert 'ctrl+q' / 'F1' style strings to pynput GlobalHotKeys format."""
    parts = hotkey_str.strip().split('+')
    result = []
    for part in parts:
        part = part.strip().lower()
        if part in ('ctrl', 'alt', 'shift', 'cmd', 'win', 'super',
                    'f1','f2','f3','f4','f5','f6','f7','f8',
                    'f9','f10','f11','f12',
                    'enter','space','escape','esc','tab',
                    'backspace','delete','insert',
                    'up','down','left','right',
                    'home','end','page_up','page_down',
                    'print_screen','pause','caps_lock',
                    'num_lock','scroll_lock'):
            result.append(f'<{part}>')
        else:
            result.append(part)
    return '+'.join(result)


class KeyboardHandler(threading.Thread):
    def __init__(self, callbacks, config):
        super().__init__()
        self.callbacks = callbacks
        self.config = config
        self.running = True
        self.daemon = True
        self._listener = None

    def run(self):
        self.register_shortcuts()
        while self.running:
            time.sleep(0.5)

    def register_shortcuts(self):
        if not _PYNPUT_AVAILABLE:
            return
        try:
            if self._listener is not None:
                try:
                    self._listener.stop()
                except Exception:
                    pass
                self._listener = None

            hotkeys = {}

            if 'toggle_mirror' in self.callbacks:
                hotkeys['<f1>'] = self.callbacks['toggle_mirror']
            if 'stop_all' in self.callbacks:
                hotkeys['<f2>'] = self.callbacks['stop_all']

            shortcuts = self.config.get('Shortcuts', {})
            mapping = {
                'mirror_dungeon':    'toggle_mirror',
                'exp':               'toggle_exp',
                'threads':           'toggle_threads',
                'chain_automation':  'toggle_chain',
                'call_function':     'call_function',
                'terminate_functions': 'terminate_functions',
            }

            for key, callback_name in mapping.items():
                hotkey = shortcuts.get(key)
                if hotkey and callback_name in self.callbacks:
                    try:
                        pynput_key = _to_pynput_hotkey(hotkey)
                        hotkeys[pynput_key] = self.callbacks[callback_name]
                    except Exception as e:
                        logger.error(f"Failed to register hotkey {hotkey} for {key}: {e}")

            if hotkeys:
                self._listener = _pynput_kbd.GlobalHotKeys(hotkeys)
                self._listener.start()

        except Exception as e:
            logger.error(f"Failed to register keyboard shortcuts: {e}")

    def stop(self):
        self.running = False
        if self._listener is not None:
            try:
                self._listener.stop()
            except Exception:
                pass
            self._listener = None

    def update_shortcuts(self):
        self.register_shortcuts()

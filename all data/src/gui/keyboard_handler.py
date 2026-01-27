import threading
import time
import keyboard
import logging

logger = logging.getLogger("gui_launcher")

class KeyboardHandler(threading.Thread):
    def __init__(self, callbacks, config):
        super().__init__()
        self.callbacks = callbacks
        self.config = config
        self.running = True
        self.daemon = True

    def run(self):
        self.register_shortcuts()
        while self.running:
            time.sleep(0.5)

    def register_shortcuts(self):
        """Register global hotkeys from config"""
        try:
            keyboard.unhook_all()
            
            # Default hardcoded for safety/fallback if config missing
            # F1 to Start/Stop Mirror Dungeon (Toggle)
            if 'toggle_mirror' in self.callbacks:
                 keyboard.add_hotkey('F1', self.callbacks['toggle_mirror'])
            
            # F2 to Stop All
            if 'stop_all' in self.callbacks:
                keyboard.add_hotkey('F2', self.callbacks['stop_all'])

            # Configurable shortcuts
            shortcuts = self.config.get('Shortcuts', {})
            
            mapping = {
                'mirror_dungeon': 'toggle_mirror',
                'exp': 'toggle_exp',
                'threads': 'toggle_threads',
                'chain_automation': 'toggle_chain',
                'call_function': 'call_function',
                'terminate_functions': 'terminate_functions'
            }

            for key, callback_name in mapping.items():
                hotkey = shortcuts.get(key)
                if hotkey and callback_name in self.callbacks:
                    try:
                        keyboard.add_hotkey(hotkey, self.callbacks[callback_name])
                    except Exception as e:
                        logger.error(f"Failed to register hotkey {hotkey} for {key}: {e}")

        except Exception as e:
            logger.error(f"Failed to register keyboard shortcuts: {e}")

    def stop(self):
        self.running = False
        keyboard.unhook_all()

    def update_shortcuts(self):
        self.register_shortcuts()
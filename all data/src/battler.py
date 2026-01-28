import sys
import logging
import os

def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    else:
        folder_path = os.path.dirname(os.path.abspath(__file__))
        if os.path.basename(folder_path) == 'src':
            return os.path.dirname(folder_path)
        return folder_path
BASE_PATH = get_base_path()

sys.path.append(os.path.join(BASE_PATH, 'src'))

import common

logger = logging.getLogger("battler")

def main():
    """Run the battle function and exit immediately"""
    try:
        try:
            import core

            core.battle()
            
        except AttributeError:
            logger.error("Function 'battle' not found in module 'core'")
        except Exception as e:
            logger.error(f"Error running battle function: {e}")
            
    except Exception as e:
        logger.error(f"Unexpected error in battler.py: {e}")
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()

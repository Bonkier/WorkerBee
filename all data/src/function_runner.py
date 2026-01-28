import sys
import importlib
import logging
import time
import traceback
import ast
import re
import threading
import signal
import os

def get_base_path():
    """Get the base directory path"""
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

logger = logging.getLogger(__name__)

lock = threading.Lock()
is_running = False
running = True

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global running
    running = False
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)
if hasattr(signal, 'SIGBREAK'):  
    signal.signal(signal.SIGBREAK, signal_handler)

def parse_function_call(function_string):
    """Parse a function call string like 'module.func(arg1, arg2)' into module, function name, and args"""
    pattern = r"([^\(\)]+)(?:\((.*)\))?"
    match = re.match(pattern, function_string)
    
    if not match:
        return None, None, []
    
    full_function_name = match.group(1).strip()
    args_str = match.group(2) if match.group(2) else ""

    if '.' not in full_function_name:
        module_name = "__builtin__"
        function_name = full_function_name
    else:
        parts = full_function_name.split('.')
        function_name = parts[-1]
        module_name = '.'.join(parts[:-1])

    args = []
    kwargs = {}
    
    if args_str:
        try:
            args_code = f"[{args_str}]"
            args = ast.literal_eval(args_code)
        except (SyntaxError, ValueError) as e:
            logger.warning(f"Could not parse arguments '{args_str}': {e}")
            try:
                args = [eval(arg.strip()) for arg in args_str.split(',') if arg.strip()]
            except Exception as e:
                    logger.error(f"Failed to parse arguments: {e}")
    
    return module_name, function_name, args

def call_function(function_string):
    """Call a function by its module path, function name, and arguments"""
    global is_running
    
    with lock:
        is_running = True
    
    try:
        module_name, function_name, args = parse_function_call(function_string)
        
        if not module_name or not function_name:
            logger.error(f"Invalid function format: {function_string}")
            with lock:
                is_running = False
            return False

        try:
            if module_name == "__builtin__":
                import builtins as module
            else:
                module = importlib.import_module(module_name)

            try:
                func = getattr(module, function_name)
            except AttributeError:
                if module_name == "mirror":
                    try:
                        mirror_class = getattr(module, "Mirror")
                        if hasattr(mirror_class, function_name):
                            default_status = "poise"
                            status = default_status
                            method_args = args
                            
                            mirror_instance = mirror_class(status)
                            func = getattr(mirror_instance, function_name)
                            args = method_args
                        else:
                            raise AttributeError(f"Method {function_name} not found in Mirror class")
                    except Exception as e:
                        logger.error(f"Mirror class error: {e}")
                        return False
                else:
                    raise 

            result = func(*args)
            return True
            
        except ImportError:
            logger.error(f"Module {module_name} not found")
            return False
        except AttributeError:
            logger.error(f"Function {function_name} not found in module {module_name}")
            return False
        
    except Exception as e:
        logger.error(f"Error calling function {function_string}: {e}")
        logger.error(traceback.format_exc())
        return False
    finally:
        with lock:
            is_running = False

def run_function_in_thread(function_string):
    """Run the function in a separate thread"""
    thread = threading.Thread(target=call_function, args=(function_string,), daemon=True)
    thread.start()
    return thread

def main():
    """Main function to handle function calls from command line"""
    global running
    
    if len(sys.argv) < 2:
        logger.error("No function specified - Usage: python function_runner.py <module.function>")
        return
    
    function_string = sys.argv[1]

    thread = run_function_in_thread(function_string)
    
    try:
        while running:
            time.sleep(0.1)
                
    except KeyboardInterrupt:
        running = False
    except Exception as e:
        logger.error(f"Unexpected error in main loop: {e}")
        running = False
    finally:
        sys.exit(0)

if __name__ == "__main__":
    main()
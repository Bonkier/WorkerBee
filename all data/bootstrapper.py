import sys
import subprocess
import importlib.util
import os
import time

def check_and_install():
    dependencies = {
        "customtkinter": "customtkinter",
        "cv2": "opencv-python",
        "PIL": "Pillow",
        "keyboard": "keyboard",
        "mss": "mss",
        "pyautogui": "PyAutoGUI"
    }
    
    missing = [pkg for import_name, pkg in dependencies.items() if importlib.util.find_spec(import_name) is None]

    if missing:
        print(f"Missing libraries found: {', '.join(missing)}")
        print("Installing requirements...")

        req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")

        try:
            if os.path.exists(req_file):
                with open(req_file, 'rb') as f:
                    content = f.read()
                if b'\x00' in content:
                    print("Detected corrupted requirements.txt, sanitizing...")
                    clean_content = content.replace(b'\x00', b'')
                    with open(req_file, 'wb') as f:
                        f.write(clean_content)
        except Exception as e:
            print(f"Warning: Failed to sanitize requirements.txt: {e}")

        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("Installation complete!")
        except subprocess.CalledProcessError:
            print("Failed to install requirements. Please check your internet connection.")
            input("Press Enter to exit...")
            sys.exit(1)
        except Exception as e:
            print(f"Error installing requirements: {e}")
            input("Press Enter to exit...")
            sys.exit(1)

def launch_main_app():
    main_script = os.path.join(os.path.dirname(__file__), "gui_launcher.py")
    
    if not os.path.exists(main_script):
        print(f"Error: gui_launcher.py not found at {main_script}")
        input("Press Enter to exit...")
        sys.exit(1)

    print(f"Launching {main_script}...")
    try:
        ret_code = subprocess.call([sys.executable, main_script])
        if ret_code != 0:
            print(f"\nApplication exited with error code {ret_code}")
            input("Press Enter to exit...")
    except Exception as e:
        print(f"\nFailed to launch application: {e}")
        input("Press Enter to exit...")

if __name__ == "__main__":
    try:
        check_and_install()
        launch_main_app()
    except Exception as e:
        print(f"Bootstrapper error: {e}")
        input("Press Enter to exit...")
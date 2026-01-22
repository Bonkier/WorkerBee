import sys
import subprocess
import importlib.util
import os

def check_and_install():
    # If this is missing, we assume we need to install everything.
    package_name = "customtkinter"
    
    spec = importlib.util.find_spec(package_name)
    
    if spec is None:
        print(f"{package_name} not found. Installing requirements...")
        
        # Get the path to requirements.txt (assumed to be in the same folder)
        req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
        
        try:
            # Run pip install automatically
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", req_file])
            print("Installation complete!")
        except subprocess.CalledProcessError:
            print("Failed to install requirements. Please check your internet connection.")
            input("Press Enter to exit...")
            sys.exit(1)

def launch_main_app():
    # Run the main GUI launcher
    main_script = os.path.join(os.path.dirname(__file__), "gui_launcher.py")
    
    # We use subprocess to run it so it starts with a fresh environment
    subprocess.call([sys.executable, main_script])

if __name__ == "__main__":
    check_and_install()
    launch_main_app()
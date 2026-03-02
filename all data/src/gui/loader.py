import tkinter as tk
from tkinter import ttk
import sys
import os

def main():
    if sys.platform == 'win32':
        try:
            import ctypes
            myappid = 'bonkier.workerbee.gui.2.0'
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
        except:
            pass

    root = tk.Tk()
    root.overrideredirect(True)
    
    width = 300
    height = 120
    
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    
    root.geometry(f'{width}x{height}+{x}+{y}')
    root.configure(bg='#1C1C1C')

    try:
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        icon_path = os.path.join(base_dir, "app_icon.ico")
        if os.path.exists(icon_path):
            root.wm_iconbitmap(default=icon_path)
            root.iconbitmap(icon_path)
    except:
        pass

    frame = tk.Frame(root, bg='#1C1C1C', highlightbackground='#333333', highlightthickness=1)
    frame.pack(fill='both', expand=True)
    
    label = tk.Label(frame, text="WorkerBee", font=("Segoe UI", 16, "bold"), fg="#E0E0E0", bg='#1C1C1C')
    label.pack(pady=(25, 5))
    
    sub = tk.Label(frame, text="Initializing...", font=("Segoe UI", 10), fg="#888888", bg='#1C1C1C')
    sub.pack(pady=(0, 15))
    
    style = ttk.Style()
    style.theme_use('default')
    style.configure("Horizontal.TProgressbar", background="#EAEAEA", troughcolor="#2A2A2A", bordercolor="#1C1C1C", thickness=4)
    
    pb = ttk.Progressbar(frame, orient="horizontal", length=240, mode="indeterminate", style="Horizontal.TProgressbar")
    pb.pack(pady=0)
    pb.start(15)

    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)
    
    root.mainloop()

if __name__ == "__main__":
    main()
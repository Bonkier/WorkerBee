import tkinter as tk
import sys
import os


def main():
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('bonkier.workerbee.gui.2.0')
        except Exception:
            pass

    BG     = '#050505'
    CARD   = '#111111'
    BORDER = '#262626'
    ACCENT = '#FFFFFF'
    TEXT   = '#E0E0E0'
    MUTED  = '#888888'
    SEP    = '#1F1F1F'

    W, H = 420, 200

    root = tk.Tk()
    root.overrideredirect(True)

    sw = root.winfo_screenwidth()
    sh = root.winfo_screenheight()
    root.geometry(f'{W}x{H}+{(sw - W) // 2}+{(sh - H) // 2}')
    root.configure(bg=BORDER)

    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )

    icon_path = os.path.join(base_dir, 'app_icon.ico')

    try:
        if os.path.exists(icon_path):
            root.wm_iconbitmap(default=icon_path)
    except Exception:
        pass

    card = tk.Frame(root, bg=CARD)
    card.place(x=1, y=1, width=W - 2, height=H - 2)

    tk.Frame(card, bg=ACCENT, height=2).pack(fill='x', side='top')

    version = ''
    try:
        ver_path = os.path.join(base_dir, 'version.json')
        if os.path.exists(ver_path):
            with open(ver_path, 'r', encoding='utf-8') as f:
                version = f.read().strip()
    except Exception:
        pass

    icon_photo = None
    try:
        from PIL import Image, ImageTk
        if os.path.exists(icon_path):
            img = Image.open(icon_path)
            img = img.resize((36, 36), Image.LANCZOS)
            icon_photo = ImageTk.PhotoImage(img)
    except Exception:
        pass

    header = tk.Frame(card, bg=CARD)
    header.pack(fill='x', padx=28, pady=(20, 0))

    if icon_photo:
        lbl_icon = tk.Label(header, image=icon_photo, bg=CARD)
        lbl_icon.image = icon_photo
        lbl_icon.pack(side='left', padx=(0, 14))

    title_block = tk.Frame(header, bg=CARD)
    title_block.pack(side='left', fill='y', expand=True)

    tk.Label(
        title_block, text='WorkerBee',
        font=('Segoe UI', 18, 'bold'), fg=TEXT, bg=CARD, anchor='w'
    ).pack(anchor='w')

    tk.Label(
        title_block, text='Limbus Company Automation',
        font=('Segoe UI', 9), fg=MUTED, bg=CARD, anchor='w'
    ).pack(anchor='w', pady=(2, 0))

    if version:
        tk.Label(
            header, text=version,
            font=('Segoe UI', 9), fg=MUTED, bg=CARD
        ).pack(side='right', anchor='n', pady=(4, 0))

    tk.Frame(card, bg=SEP, height=1).pack(fill='x', padx=28, pady=(14, 0))

    status_var = tk.StringVar(value='Initializing...')
    tk.Label(
        card, textvariable=status_var,
        font=('Segoe UI', 10), fg=MUTED, bg=CARD, anchor='w'
    ).pack(fill='x', padx=28, pady=(10, 8))

    BAR_H   = 3
    PAD     = 28
    bar_cv  = tk.Canvas(card, height=BAR_H, bg=SEP, bd=0, highlightthickness=0)
    bar_cv.pack(fill='x', padx=PAD, pady=(0, 20))

    bar_x   = [-(W - PAD * 2) * 0.32]
    SEG_PCT = 0.32
    SPEED   = 10

    def _tick():
        track_w = bar_cv.winfo_width() or (W - PAD * 2)
        seg     = int(track_w * SEG_PCT)
        x1      = int(bar_x[0])
        x0      = x1 - seg
        bar_cv.delete('bar')
        if x1 > 0 and x0 < track_w:
            bar_cv.create_rectangle(
                max(0, x0), 0, min(track_w, x1), BAR_H,
                fill=ACCENT, outline='', tags='bar'
            )
        bar_x[0] += SPEED
        if bar_x[0] > track_w + seg:
            bar_x[0] = -seg
        root.after(16, _tick)

    root.after(50, _tick)
    root.after(60_000, root.destroy)

    root.lift()
    root.attributes('-topmost', True)
    root.after_idle(root.attributes, '-topmost', False)

    root.mainloop()


if __name__ == '__main__':
    main()

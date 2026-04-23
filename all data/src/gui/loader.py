import tkinter as tk
import sys
import os
import threading
import logging

_logger = logging.getLogger(__name__)


class LoaderWindow:
    BG     = '#050505'
    CARD   = '#111111'
    BORDER = '#262626'
    ACCENT = '#FFFFFF'
    TEXT   = '#E0E0E0'
    MUTED  = '#888888'
    SEP    = '#1F1F1F'
    W, H   = 420, 210

    def __init__(self):
        self._animating = True
        # result is set before close() is called:
        # None       = update triggered (app will os._exit)
        # 'skip'     = user skipped update, proceed to main UI
        # 'no_ask'   = user said don't ask again, proceed to main UI
        self.result = None

        if sys.platform == 'win32':
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    'bonkier.workerbee.gui.2.0'
                )
            except Exception:
                pass

        self.root = tk.Tk()
        self.root.overrideredirect(True)

        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        self.root.geometry(
            f'{self.W}x{self.H}+{(sw - self.W) // 2}+{(sh - self.H) // 2}'
        )
        self.root.configure(bg=self.BORDER)

        if getattr(sys, 'frozen', False):
            base_dir = sys._MEIPASS
        else:
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            )

        icon_path = os.path.join(base_dir, 'app_icon.ico')

        try:
            if os.path.exists(icon_path):
                if sys.platform == 'win32':
                    self.root.wm_iconbitmap(default=icon_path)
                else:
                    import tkinter as _tk
                    _img = _tk.PhotoImage(file=icon_path) if icon_path.endswith('.png') else None
                    if _img:
                        self.root.iconphoto(True, _img)
        except Exception as e:
            _logger.debug(f"Could not set window icon: {e}")

        card = tk.Frame(self.root, bg=self.CARD)
        card.place(x=1, y=1, width=self.W - 2, height=self.H - 2)
        self._card = card

        tk.Frame(card, bg=self.ACCENT, height=2).pack(fill='x', side='top')

        version = ''
        try:
            ver_path = os.path.join(base_dir, 'version.json')
            if os.path.exists(ver_path):
                with open(ver_path, 'r', encoding='utf-8') as f:
                    version = f.read().strip()
        except Exception as e:
            _logger.debug(f"Could not read version.json: {e}")

        icon_photo = None
        try:
            from PIL import Image, ImageTk
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                img = img.resize((36, 36), Image.LANCZOS)
                icon_photo = ImageTk.PhotoImage(img)
        except Exception as e:
            _logger.debug(f"Could not load icon image: {e}")

        header = tk.Frame(card, bg=self.CARD)
        header.pack(fill='x', padx=28, pady=(20, 0))

        if icon_photo:
            lbl_icon = tk.Label(header, image=icon_photo, bg=self.CARD)
            lbl_icon.image = icon_photo
            lbl_icon.pack(side='left', padx=(0, 14))

        title_block = tk.Frame(header, bg=self.CARD)
        title_block.pack(side='left', fill='y', expand=True)

        tk.Label(
            title_block, text='WorkerBee',
            font=('Segoe UI', 18, 'bold'), fg=self.TEXT, bg=self.CARD, anchor='w'
        ).pack(anchor='w')

        tk.Label(
            title_block, text='Limbus Company Automation',
            font=('Segoe UI', 9), fg=self.MUTED, bg=self.CARD, anchor='w'
        ).pack(anchor='w', pady=(2, 0))

        if version:
            tk.Label(
                header, text=version,
                font=('Segoe UI', 9), fg=self.MUTED, bg=self.CARD
            ).pack(side='right', anchor='n', pady=(4, 0))

        tk.Frame(card, bg=self.SEP, height=1).pack(fill='x', padx=28, pady=(14, 0))

        self._status_var = tk.StringVar(value='Checking for updates...')
        tk.Label(
            card, textvariable=self._status_var,
            font=('Segoe UI', 10), fg=self.MUTED, bg=self.CARD, anchor='w'
        ).pack(fill='x', padx=28, pady=(10, 6))

        # Bottom area: holds animated bar, progress bar, or buttons
        self._bottom = tk.Frame(card, bg=self.CARD)
        self._bottom.pack(fill='x', padx=28, pady=(0, 18))

        # Animated indeterminate bar (default state)
        self._bar_cv = tk.Canvas(
            self._bottom, height=3, bg=self.SEP, bd=0, highlightthickness=0
        )
        self._bar_cv.pack(fill='x')

        self._bar_x = [-(self.W - 56) * 0.32]
        self._tick_id = self.root.after(50, self._tick)
        self.root.after(60_000, self.close)

        self.root.lift()
        self.root.attributes('-topmost', True)
        self.root.after_idle(self.root.attributes, '-topmost', False)

    # ------------------------------------------------------------------
    # Internal

    def _tick(self):
        if not self._animating:
            return
        track_w = self._bar_cv.winfo_width() or (self.W - 56)
        seg = int(track_w * 0.32)
        x1 = int(self._bar_x[0])
        x0 = x1 - seg
        self._bar_cv.delete('bar')
        if x1 > 0 and x0 < track_w:
            self._bar_cv.create_rectangle(
                max(0, x0), 0, min(track_w, x1), 3,
                fill=self.ACCENT, outline='', tags='bar'
            )
        self._bar_x[0] += 10
        if self._bar_x[0] > track_w + seg:
            self._bar_x[0] = -seg
        self._tick_id = self.root.after(16, self._tick)

    def _clear_bottom(self):
        self._animating = False
        for w in self._bottom.winfo_children():
            w.destroy()

    # ------------------------------------------------------------------
    # Public API  (all thread-safe via root.after)

    def set_status(self, text):
        self.root.after(0, lambda: self._status_var.set(text))

    def show_update_available(self, version, on_yes, on_no, on_no_ask):
        """Replace progress bar with the 3-button update prompt."""
        def _build():
            self._clear_bottom()
            self._status_var.set(f'Update available: {version}')

            btn_row = tk.Frame(self._bottom, bg=self.CARD)
            btn_row.pack(anchor='w', pady=(6, 0))

            def _btn(text, cmd, primary=False):
                fg = self.ACCENT if primary else '#888888'
                b = tk.Button(
                    btn_row, text=text, command=cmd,
                    bg='#1d1d1d', fg=fg,
                    relief='flat', bd=0,
                    font=('Segoe UI', 9, 'bold' if primary else 'normal'),
                    padx=14, pady=5,
                    cursor='hand2',
                    activebackground='#252525', activeforeground=fg,
                    highlightthickness=0
                )
                b.pack(side='left', padx=(0, 8))

            _btn('Update now', on_yes, primary=True)
            _btn('Skip', on_no)
            _btn("Don't ask again", on_no_ask)

        self.root.after(0, _build)

    def show_progress(self, done, total):
        """Switch to a static progress bar and update it."""
        def _update(done=done, total=total):
            if not hasattr(self, '_prog_cv'):
                self._clear_bottom()
                self._prog_cv = tk.Canvas(
                    self._bottom, height=3, bg=self.SEP, bd=0, highlightthickness=0
                )
                self._prog_cv.pack(fill='x')

            track_w = self._prog_cv.winfo_width() or (self.W - 56)
            pct = done / total if total > 0 else 0
            fill_w = int(track_w * pct)
            self._prog_cv.delete('bar')
            if fill_w > 0:
                self._prog_cv.create_rectangle(
                    0, 0, fill_w, 3, fill=self.ACCENT, outline='', tags='bar'
                )
            self._status_var.set(f'Downloading... {int(pct * 100)}%')

        try:
            self.root.after(0, _update)
        except Exception:
            pass

    def _do_close(self):
        self._animating = False
        try:
            if hasattr(self, '_tick_id') and self._tick_id:
                self.root.after_cancel(self._tick_id)
        except Exception:
            pass
        try:
            self.root.quit()
            self.root.destroy()
        except Exception:
            pass

    def close(self):
        # Safe to call from any thread (schedules _do_close on the main thread)
        try:
            self.root.after(0, self._do_close)
        except Exception:
            pass

    def run(self):
        self.root.mainloop()


# ---------------------------------------------------------------------------
# Legacy entry point kept for --loader subprocess fallback (not used by default)

def main():
    loader = LoaderWindow()
    loader.run()


if __name__ == '__main__':
    main()

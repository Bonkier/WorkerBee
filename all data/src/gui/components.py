import customtkinter as ctk
from .styles import UIStyle

class SidebarNavigation:
    def __init__(self, sidebar_frame, content_frame, shared_vars=None):
        self.sidebar_frame = sidebar_frame
        self.content_frame = content_frame
        self.shared_vars = shared_vars
        self.pages = {}
        self.buttons = {}
        self.current_page = None
        self._animation_id = None

    def add_page(self, name):
        frame = ctk.CTkFrame(self.content_frame, corner_radius=0, fg_color="transparent")
        frame.place(relx=0, rely=0, relwidth=1, relheight=1)
        self.pages[name] = frame
        
        btn = ctk.CTkButton(self.sidebar_frame, text=name, 
                            command=lambda n=name: self.show_page(n),
                            fg_color="transparent", 
                            text_color=UIStyle.TEXT_SECONDARY_COLOR,
                            hover_color=UIStyle.BUTTON_HOVER_COLOR, 
                            anchor="w",
                            height=40, font=UIStyle.BODY_FONT,
                            corner_radius=UIStyle.CORNER_RADIUS)
        btn.pack(fill="x", pady=2, padx=5)
        self.buttons[name] = btn
        return frame

    def show_page(self, name):
        if self.current_page == name:
            return

        if self._animation_id:
            try:
                self.content_frame.after_cancel(self._animation_id)
            except: pass
            self._animation_id = None

        if self.current_page:
            self.buttons[self.current_page].configure(
                fg_color="transparent", 
                text_color=UIStyle.TEXT_SECONDARY_COLOR, 
                border_width=0
            )
            
        self.buttons[name].configure(
            fg_color=UIStyle.BUTTON_COLOR, 
            text_color=UIStyle.TEXT_COLOR,
            border_width=1, 
            border_color=UIStyle.BUTTON_BORDER_COLOR
        )
        self.current_page = name
        
        new_page = self.pages[name]

        use_animation = True
        if self.shared_vars and hasattr(self.shared_vars, 'enable_animations'):
            use_animation = self.shared_vars.enable_animations.value

        if not use_animation:
            new_page.place(relx=0, rely=0, relwidth=1, relheight=1)
            new_page.lift()
            return

        new_page.place(relx=0, rely=0.02, relwidth=1, relheight=1)
        new_page.lift()

        def animate(step, total_steps=5):
            if step > total_steps:
                new_page.place(relx=0, rely=0, relwidth=1, relheight=1)
                self._animation_id = None
                return

            progress = step / total_steps
            current_y = 0.02 * (1 - progress)

            new_page.place(relx=0, rely=current_y, relwidth=1, relheight=1)
            # 33ms = ~30fps, smooth enough for fade without hammering lower-end
            # CPUs at 66fps which spiked tk scheduling overhead.
            self._animation_id = self.content_frame.after(33, lambda: animate(step + 1, total_steps))

        animate(0)

class CardFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            fg_color=UIStyle.CARD_COLOR, 
            corner_radius=UIStyle.CORNER_RADIUS,
            border_width=1,
            border_color=UIStyle.BORDER_COLOR
        )

class ModernEntry(ctk.CTkEntry):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(
            height=UIStyle.ENTRY_HEIGHT,
            font=UIStyle.BODY_FONT,
            corner_radius=UIStyle.CORNER_RADIUS,
            fg_color=UIStyle.INPUT_BG_COLOR,
            border_color=UIStyle.BORDER_COLOR,
            border_width=1,
            text_color=UIStyle.TEXT_COLOR
        )

class ToolTip:
    def __init__(self, widget, text):
        self.widget = widget
        self.text = text
        self.tooltip_window = None
        self.widget.bind("<Enter>", self.show_tooltip)
        self.widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.text:
            return
        x, y, _, _ = self.widget.bbox("insert")
        x += self.widget.winfo_rootx() + 25
        y += self.widget.winfo_rooty() + 25
        self.tooltip_window = ctk.CTkToplevel(self.widget)
        self.tooltip_window.wm_overrideredirect(True)
        self.tooltip_window.wm_geometry(f"+{x}+{y}")
        label = ctk.CTkLabel(self.tooltip_window, text=self.text, corner_radius=5, fg_color="gray20", text_color="white")
        label.pack()

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

def animate_expand(widget, pack_kwargs):
    widget.pack(**pack_kwargs)


def animate_collapse(widget):
    widget.pack_forget()
import customtkinter as ctk
from .styles import UIStyle

class SidebarNavigation:
    def __init__(self, sidebar_frame, content_frame):
        self.sidebar_frame = sidebar_frame
        self.content_frame = content_frame
        self.pages = {}
        self.buttons = {}
        self.current_page = None

    def add_page(self, name):
        frame = ctk.CTkFrame(self.content_frame, corner_radius=0, fg_color="transparent")
        self.pages[name] = frame
        
        btn = ctk.CTkButton(self.sidebar_frame, text=name, 
                            command=lambda n=name: self.show_page(n),
                            fg_color="transparent", text_color=("gray10", "gray90"),
                            hover_color=("gray70", "gray30"), anchor="w",
                            height=40, font=UIStyle.BODY_FONT)
        btn.pack(fill="x", pady=2, padx=5)
        self.buttons[name] = btn
        return frame

    def show_page(self, name):
        if self.current_page:
            self.pages[self.current_page].pack_forget()
            self.buttons[self.current_page].configure(fg_color="transparent")
            
        self.pages[name].pack(fill="both", expand=True)
        self.buttons[name].configure(fg_color=("gray75", "gray25"))
        self.current_page = name

class CardFrame(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.configure(fg_color=UIStyle.CARD_COLOR, corner_radius=UIStyle.CORNER_RADIUS)

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
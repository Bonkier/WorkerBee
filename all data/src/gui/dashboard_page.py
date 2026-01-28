import customtkinter as ctk
from src.gui.styles import UIStyle
from src.gui.components import CardFrame

def load_dashboard_tab(parent, sidebar, callbacks, ui_context):
    """Load and render the Dashboard tab"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    welcome_card = CardFrame(scroll_frame)
    welcome_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(welcome_card, text="Welcome to WorkerBee", font=UIStyle.HEADER_FONT).pack(pady=(20, 5), padx=20, anchor="w")
    ctk.CTkLabel(welcome_card, text="Your automated assistant for Limbus Company.", font=UIStyle.BODY_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR).pack(pady=(0, 20), padx=20, anchor="w")

    actions_card = CardFrame(scroll_frame)
    actions_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(actions_card, text="Quick Actions", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10), padx=20, anchor="w")

    actions_grid = ctk.CTkFrame(actions_card, fg_color="transparent")
    actions_grid.pack(fill="x", padx=20, pady=(0, 20))

    ctk.CTkButton(actions_grid, text="Go to Mirror Dungeon", command=lambda: sidebar.show_page("Mirror Dungeon"), height=40, font=UIStyle.BODY_FONT).pack(side="left", expand=True, fill="x", padx=5)
    ctk.CTkButton(actions_grid, text="Go to Exp Luxcavation", command=lambda: sidebar.show_page("Exp"), height=40, font=UIStyle.BODY_FONT).pack(side="left", expand=True, fill="x", padx=5)
    ctk.CTkButton(actions_grid, text="Go to Thread Luxcavation", command=lambda: sidebar.show_page("Threads"), height=40, font=UIStyle.BODY_FONT).pack(side="left", expand=True, fill="x", padx=5)

    status_card = CardFrame(scroll_frame)
    status_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(status_card, text="System Status", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10), padx=20, anchor="w")
    
    status_label = ctk.CTkLabel(status_card, text="Idle", font=UIStyle.BODY_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
    status_label.pack(pady=(0, 20), padx=20, anchor="w")
    ui_context['status_label'] = status_label
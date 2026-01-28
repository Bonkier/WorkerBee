import os
import customtkinter as ctk
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import load_json_data, save_json_data
from src.gui.constants import TEAM_ORDER

def load_threads_tab(parent, config, shared_vars, callbacks, ui_context, base_path, save_callback):
    """Load and render the Thread Luxcavation tab"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    run_card = CardFrame(scroll_frame)
    run_card.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(run_card, text="Run Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

    input_row = ctk.CTkFrame(run_card, fg_color="transparent")
    input_row.pack(pady=(0, 10))

    ctk.CTkLabel(input_row, text="Number of Runs:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
    entry = ctk.CTkEntry(input_row, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT, width=80)
    entry.pack(side="left")
    entry.insert(0, str(config.get('Settings', {}).get('threads_runs', 1)))
    ui_context['threads_runs_entry'] = entry

    ctk.CTkLabel(run_card, text="Choose Difficulty:", font=UIStyle.BODY_FONT).pack(pady=(10, 5))
    
    diff_var = ctk.StringVar(value=str(config.get('Settings', {}).get('threads_difficulty', '40')))
    diff_dropdown = ctk.CTkOptionMenu(
        master=run_card,
        variable=diff_var,
        values=["20", "30", "40", "50", "latest"],
        width=200,
        height=UIStyle.ENTRY_HEIGHT,
        font=UIStyle.BODY_FONT,
        dropdown_font=UIStyle.BODY_FONT
    )
    diff_dropdown.pack(pady=(0, 10))
    ui_context['threads_difficulty_var'] = diff_var

    def start_threads_wrapper():
        try:
            runs = int(entry.get())
            shared_vars.threads_runs.value = runs
            diff_val = diff_var.get()
            if diff_val != "latest":
                shared_vars.threads_difficulty.value = int(diff_val)

            config['Settings']['threads_runs'] = runs
            config['Settings']['threads_difficulty'] = diff_val
            save_callback()
            
            callbacks['start_threads']()
        except ValueError:
            pass

    start_button = ctk.CTkButton(run_card, text="Start", command=start_threads_wrapper, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    start_button.pack(pady=(10, 20))
    ui_context['threads_start_button'] = start_button

    settings_card = CardFrame(scroll_frame)
    settings_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(settings_card, text="Advanced Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))

    ctk.CTkLabel(settings_card, text="Your Team", font=UIStyle.SUBHEADER_FONT).pack(pady=(10, 5))
    team_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
    team_frame.pack(pady=5)
    
    status_path = os.path.join(base_path, "config", "threads_team_selection.json")
    saved_team = set()
    if os.path.exists(status_path):
        try:
            data = load_json_data(status_path)
            saved_team = set(data.values())
        except: pass
        
    for name, row, col in TEAM_ORDER:
        var = ctk.BooleanVar(value=name in saved_team)
        chk = ctk.CTkCheckBox(team_frame, text=name.capitalize(), variable=var, 
                              command=lambda n=name, v=var: update_threads_team(base_path, n, v.get()), font=UIStyle.BODY_FONT)
        chk.grid(row=row, column=col, padx=10, pady=5, sticky="w")

def update_threads_team(base_path, name, is_checked):
    path = os.path.join(base_path, "config", "threads_team_selection.json")
    data = load_json_data(path)
    current_list = [data[str(i)] for i in sorted([int(k) for k in data.keys()])] if data else []
    if is_checked and name not in current_list: current_list.append(name)
    elif not is_checked and name in current_list: current_list.remove(name)
    save_json_data(path, {str(i+1): s for i, s in enumerate(current_list)})
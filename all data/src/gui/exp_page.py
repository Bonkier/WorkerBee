import os
import customtkinter as ctk
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import load_json_data, save_json_data
from src.gui.constants import TEAM_ORDER

def load_exp_tab(parent, config, shared_vars, callbacks, ui_context, base_path, save_callback):
    """Load and render the Exp Luxcavation tab"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)
    
    # Run Configuration Card
    run_card = CardFrame(scroll_frame)
    run_card.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(run_card, text="Run Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

    # Input row
    input_row = ctk.CTkFrame(run_card, fg_color="transparent")
    input_row.pack(pady=(0, 10))

    ctk.CTkLabel(input_row, text="Number of Runs:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
    entry = ctk.CTkEntry(input_row, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT, width=80)
    entry.pack(side="left")
    entry.insert(0, str(config.get('Settings', {}).get('exp_runs', 1)))
    ui_context['exp_runs_entry'] = entry

    ctk.CTkLabel(run_card, text="Choose Stage:", font=UIStyle.BODY_FONT).pack(pady=(10, 5))
    
    stage_var = ctk.StringVar(value=str(config.get('Settings', {}).get('exp_stage', '6')))
    stage_dropdown = ctk.CTkOptionMenu(
        master=run_card,
        variable=stage_var,
        values=["1", "2", "3", "4", "5", "6", "7", "latest"],
        width=200,
        height=UIStyle.ENTRY_HEIGHT,
        font=UIStyle.BODY_FONT,
        dropdown_font=UIStyle.BODY_FONT
    )
    stage_dropdown.pack(pady=(0, 10))
    ui_context['exp_stage_var'] = stage_var

    def start_exp_wrapper():
        try:
            runs = int(entry.get())
            shared_vars.exp_runs.value = runs
            stage_val = stage_var.get()
            if stage_val != "latest":
                shared_vars.exp_stage.value = int(stage_val)
            
            # Save to config
            config['Settings']['exp_runs'] = runs
            config['Settings']['exp_stage'] = stage_val
            save_callback()
            
            callbacks['start_exp']()
        except ValueError:
            pass

    start_button = ctk.CTkButton(run_card, text="Start", command=start_exp_wrapper, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    start_button.pack(pady=(10, 20))
    ui_context['exp_start_button'] = start_button

    # Advanced Settings
    settings_card = CardFrame(scroll_frame)
    settings_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(settings_card, text="Advanced Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))
    
    # Team Selection
    ctk.CTkLabel(settings_card, text="Your Team", font=UIStyle.SUBHEADER_FONT).pack(pady=(10, 5))
    team_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
    team_frame.pack(pady=5)
    
    status_path = os.path.join(base_path, "config", "exp_team_selection.json")
    saved_team = set()
    if os.path.exists(status_path):
        try:
            data = load_json_data(status_path)
            saved_team = set(data.values())
        except: pass
        
    for name, row, col in TEAM_ORDER:
        var = ctk.BooleanVar(value=name in saved_team)
        chk = ctk.CTkCheckBox(team_frame, text=name.capitalize(), variable=var, 
                              command=lambda n=name, v=var: update_exp_team(base_path, n, v.get()), font=UIStyle.BODY_FONT)
        chk.grid(row=row, column=col, padx=10, pady=5, sticky="w")

def update_exp_team(base_path, name, is_checked):
    path = os.path.join(base_path, "config", "exp_team_selection.json")
    data = load_json_data(path)
    # Convert to list to manipulate
    current_list = [data[str(i)] for i in sorted([int(k) for k in data.keys()])] if data else []
    if is_checked and name not in current_list: current_list.append(name)
    elif not is_checked and name in current_list: current_list.remove(name)
    save_json_data(path, {str(i+1): s for i, s in enumerate(current_list)})
import customtkinter as ctk
from src.gui.styles import UIStyle
from src.gui.components import CardFrame

def load_others_tab(parent, config, callbacks, ui_context):
    """Load and render the Others tab (Chain Automation & Function Runner)"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    chain_card = CardFrame(scroll_frame)
    chain_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(chain_card, text="Chain Automation", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))
    
    ctk.CTkLabel(chain_card, text="Run automations in sequence: Threads → Exp → Mirror. Enter 0 to skip.", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=(0, 10))
    
    chain_grid = ctk.CTkFrame(chain_card, fg_color="transparent")
    chain_grid.pack(pady=10)

    ctk.CTkLabel(chain_grid, text="Threads Runs:", font=UIStyle.BODY_FONT).grid(row=0, column=0, padx=5, pady=5)
    chain_threads_entry = ctk.CTkEntry(chain_grid, width=60)
    chain_threads_entry.grid(row=0, column=1, padx=5, pady=5)
    chain_threads_entry.insert(0, str(config.get("Settings", {}).get("chain_threads_runs", 3)))
    ui_context['chain_threads_entry'] = chain_threads_entry

    ctk.CTkLabel(chain_grid, text="EXP Runs:", font=UIStyle.BODY_FONT).grid(row=0, column=2, padx=5, pady=5)
    chain_exp_entry = ctk.CTkEntry(chain_grid, width=60)
    chain_exp_entry.grid(row=0, column=3, padx=5, pady=5)
    chain_exp_entry.insert(0, str(config.get("Settings", {}).get("chain_exp_runs", 2)))
    ui_context['chain_exp_entry'] = chain_exp_entry

    ctk.CTkLabel(chain_grid, text="Mirror Runs:", font=UIStyle.BODY_FONT).grid(row=0, column=4, padx=5, pady=5)
    chain_mirror_entry = ctk.CTkEntry(chain_grid, width=60)
    chain_mirror_entry.grid(row=0, column=5, padx=5, pady=5)
    chain_mirror_entry.insert(0, str(config.get("Settings", {}).get("chain_mirror_runs", 1)))
    ui_context['chain_mirror_entry'] = chain_mirror_entry
    
    def save_chain_settings():
        try:
            config['Settings']['chain_threads_runs'] = int(chain_threads_entry.get())
            config['Settings']['chain_exp_runs'] = int(chain_exp_entry.get())
            config['Settings']['chain_mirror_runs'] = int(chain_mirror_entry.get())
            config['Settings']['launch_game_before_runs'] = launch_game_var.get()
            config['Settings']['collect_rewards_when_finished'] = collect_rewards_var.get()
            callbacks['save_settings']()
        except ValueError:
            pass

    def start_chain_wrapper():
        save_chain_settings()
        callbacks['start_chain']()

    launch_game_var = ctk.BooleanVar(value=config.get("Settings", {}).get("launch_game_before_runs", False))
    ctk.CTkCheckBox(chain_card, text="Launch Game First", variable=launch_game_var, command=save_chain_settings).pack(pady=5)
    ui_context['launch_game_var'] = launch_game_var
    
    collect_rewards_var = ctk.BooleanVar(value=config.get("Settings", {}).get("collect_rewards_when_finished", False))
    ctk.CTkCheckBox(chain_card, text="Collect Rewards When Finished", variable=collect_rewards_var, command=save_chain_settings).pack(pady=5)
    ui_context['collect_rewards_var'] = collect_rewards_var
    
    chain_start_button = ctk.CTkButton(chain_card, text="Start Chain", command=start_chain_wrapper, height=UIStyle.BUTTON_HEIGHT)
    chain_start_button.pack(pady=10)
    ui_context['chain_start_button'] = chain_start_button
    
    chain_status_label = ctk.CTkLabel(chain_card, text="Chain Status: Ready", font=UIStyle.SMALL_FONT, text_color="gray")
    chain_status_label.pack(pady=(0, 15))
    ui_context['chain_status_label'] = chain_status_label

    function_card = CardFrame(scroll_frame)
    function_card.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(function_card, text="Call a function:", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))
    ctk.CTkLabel(function_card, text="Type any function from any module, e.g., core.battle or time.sleep(1)", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=(0, 10))
    
    function_entry = ctk.CTkEntry(function_card, width=300, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT)
    function_entry.pack(pady=(0, 5))
    ui_context['function_entry'] = function_entry

    function_call_button = ctk.CTkButton(function_card, text="Call", command=callbacks['call_function'], width=150, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    function_call_button.pack(pady=(0, 5))
    
    function_terminate_button = ctk.CTkButton(function_card, text="Terminate All", command=callbacks['terminate_functions'], width=150, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT, state="disabled")
    function_terminate_button.pack(pady=(0, 20))
    ui_context['function_terminate_button'] = function_terminate_button
import os
import logging
import customtkinter as ctk
from tkinter import messagebox
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import format_log_line_with_time_ago
from src.gui.log_handler import OptimizedLogHandler
import common

def load_logs_tab(parent, log_filename, log_modules, config, save_callback, root):
    """Load and render the logs tab"""
    for widget in parent.winfo_children():
        widget.destroy()

    # Filter Card
    filter_card = CardFrame(parent)
    filter_card.pack(fill="x", padx=10, pady=(10, 5))

    # Filter header
    filter_header = ctk.CTkFrame(filter_card, fg_color="transparent")
    filter_header.pack(fill="x", pady=(10, 5), padx=10)
    
    ctk.CTkLabel(filter_header, text="Log Filters", font=UIStyle.SUBHEADER_FONT).pack(side="left")

    # Toggles
    toggles = ctk.CTkFrame(filter_header, fg_color="transparent")
    toggles.pack(side="right", padx=10)
    
    # Clean Logs Toggle
    clean_logs_var = ctk.BooleanVar(value=config['Settings'].get('clean_logs', True))
    
    def toggle_clean_logs():
        config['Settings']['clean_logs'] = clean_logs_var.get()
        common.CLEAN_LOGS_ENABLED = clean_logs_var.get()
        save_callback()
        load_log_file(reload_all=True)

    ctk.CTkLabel(toggles, text="Clean Logs", font=UIStyle.SMALL_FONT).grid(row=0, column=0, padx=(0,2), sticky="e")
    ctk.CTkSwitch(toggles, text="", variable=clean_logs_var, command=toggle_clean_logs, font=UIStyle.SMALL_FONT).grid(row=0, column=1, padx=(0,10))
    
    # Do Not Log Toggle
    logging_enabled_var = ctk.BooleanVar(value=not config['Settings'].get('logging_enabled', True))
    
    def toggle_logging():
        enabled = not logging_enabled_var.get()
        config['Settings']['logging_enabled'] = enabled
        
        if hasattr(common, 'set_logging_enabled'):
            common.set_logging_enabled(enabled)
            
        save_callback()
        
        # Visual feedback
        if enabled:
            log_text.configure(state="normal")
            log_text.insert("end", f"\n--- LOGGING ENABLED ---\n")
            log_text.configure(state="disabled")
        else:
            log_text.configure(state="normal")
            log_text.insert("end", f"\n--- LOGGING DISABLED ---\n")
            log_text.configure(state="disabled")
        log_text.see("end")

    ctk.CTkLabel(toggles, text="Do Not Log", font=UIStyle.SMALL_FONT).grid(row=0, column=2, padx=(0,2), sticky="e") 
    ctk.CTkSwitch(toggles, text="", variable=logging_enabled_var, command=toggle_logging, font=UIStyle.SMALL_FONT).grid(row=0, column=3, padx=0)

    # Filters Frame
    filters_main_frame = ctk.CTkFrame(filter_card, fg_color="transparent")
    filters_main_frame.pack(fill="x", expand=True, padx=10, pady=(0, 10))

    # Level Filters
    levels_frame = ctk.CTkFrame(filters_main_frame, fg_color="transparent")
    levels_frame.pack(side="left", fill="y", padx=(5, 2))
    
    ctk.CTkLabel(levels_frame, text="Log Levels:", font=UIStyle.SMALL_FONT).pack(pady=(5, 0))

    log_filters = {}
    module_filters = {}

    def apply_filter():
        # Update config
        if 'LogFilters' not in config: config['LogFilters'] = {}
        if 'ModuleFilters' not in config: config['ModuleFilters'] = {}
        
        for level, var in log_filters.items():
            config['LogFilters'][level.lower()] = var.get()
            
        for module, var in module_filters.items():
            key = module.lower().replace(' ', '_')
            config['ModuleFilters'][key] = var.get()
            
        save_callback()
        load_log_file(reload_all=True)

    level_grid_frame = ctk.CTkFrame(levels_frame, fg_color="transparent")
    level_grid_frame.pack(fill="x", padx=5, pady=5)

    levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    for i, level in enumerate(levels):
        default = config.get('LogFilters', {}).get(level.lower(), False if level in ["DEBUG", "INFO"] else True)
        var = ctk.BooleanVar(value=default)
        log_filters[level] = var
        
        chk = ctk.CTkCheckBox(
            master=level_grid_frame,
            text=level,
            variable=var,
            command=apply_filter,
            font=(UIStyle.FONT_FAMILY, 10)
        )
        row = i % 3
        col = i // 3
        chk.grid(row=row, column=col, sticky="w", padx=2, pady=1)

    # Module Filters
    modules_frame = ctk.CTkFrame(filters_main_frame, fg_color="transparent")
    modules_frame.pack(side="left", fill="both", expand=True, padx=(2, 5))
    
    ctk.CTkLabel(modules_frame, text="Modules:", font=UIStyle.SMALL_FONT).pack(pady=(5, 0))

    module_scroll_frame = ctk.CTkScrollableFrame(modules_frame, height=60)
    module_scroll_frame.pack(fill="both", expand=True, padx=5, pady=5)

    # Create module checkboxes
    modules_per_column = max(3, len(log_modules) // 4)
    
    for i, module in enumerate(log_modules):
        col = i // modules_per_column
        row = i % modules_per_column
        
        # Load saved state or default to True
        key = module.lower().replace(' ', '_')
        default_val = config.get('ModuleFilters', {}).get(key, True)
        
        var = ctk.BooleanVar(value=default_val)
        module_filters[module] = var
        
        chk = ctk.CTkCheckBox(
            master=module_scroll_frame,
            text=module,
            variable=var,
            command=apply_filter,
            font=(UIStyle.FONT_FAMILY, 10)
        )
        chk.grid(row=row, column=col, sticky="w", padx=2, pady=1)
    
    # Add "Other" filter
    module_filters["Other"] = ctk.BooleanVar(value=True)

    # Log Display Card
    log_card = CardFrame(parent)
    log_card.pack(fill="both", expand=True, padx=10, pady=(5, 10))

    log_text = ctk.CTkTextbox(log_card, font=("Consolas", 12), state="disabled")
    log_text.pack(fill="both", expand=True, padx=5, pady=5)

    # Log Control Buttons
    button_frame = ctk.CTkFrame(log_card, fg_color="transparent")
    button_frame.pack(fill="x", padx=10, pady=(0, 10))

    def clear_gui_logs():
        log_text.configure(state="normal")
        log_text.delete("1.0", "end")
        log_text.configure(state="disabled")

    def clear_log_file():
        try:
            with open(log_filename, 'w') as f:
                f.write("")
            load_log_file(reload_all=True)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to clear log file: {e}")

    ctk.CTkButton(button_frame, text="Clear GUI", command=clear_gui_logs, width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="left", padx=5, pady=5)
    ctk.CTkButton(button_frame, text="Clear File", command=clear_log_file, width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="left", padx=5, pady=5)
    ctk.CTkButton(button_frame, text="Reload", command=lambda: load_log_file(reload_all=True), width=100, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(side="left", padx=5, pady=5)

    auto_reload_var = ctk.BooleanVar(value=True)
    ctk.CTkSwitch(button_frame, text="Auto-reload", variable=auto_reload_var, font=UIStyle.BODY_FONT).pack(side="right", padx=5, pady=5)

    # Log Loading Logic
    last_file_position = 0

    def should_display_line(line):
        # Check module filters
        for module, pattern in log_modules.items():
            if f" | {pattern} | " in line:
                if not module_filters[module].get():
                    return False
                break
        else:
            if not module_filters["Other"].get():
                return False
        
        # Check clean logs
        if " | DIRTY" in line and clean_logs_var.get():
            return False
            
        return True

    def load_log_file(reload_all=False):
        nonlocal last_file_position
        try:
            if not os.path.exists(log_filename): return
            
            current_size = os.path.getsize(log_filename)
            if reload_all or current_size < last_file_position:
                log_text.configure(state="normal")
                log_text.delete("1.0", "end")
                last_file_position = 0
            
            if current_size > last_file_position:
                with open(log_filename, 'r', encoding='utf-8', errors='replace') as f:
                    f.seek(last_file_position)
                    new_lines = f.readlines()
                last_file_position = current_size
                
                if new_lines:
                    log_text.configure(state="normal")
                    batch_text = "".join([format_log_line_with_time_ago(line) for line in new_lines if should_display_line(line)])
                    if batch_text:
                        log_text.insert("end", batch_text)
                        log_text.see("end")
                    log_text.configure(state="disabled")
        except Exception:
            pass

    def check_log_file_changes():
        if auto_reload_var.get():
            try:
                if os.path.exists(log_filename):
                    load_log_file(reload_all=False)
            except Exception:
                pass
        root.after(200, check_log_file_changes)

    load_log_file(reload_all=True)
    check_log_file_changes()
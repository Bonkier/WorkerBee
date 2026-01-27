import os
import json
import shutil
import time
import subprocess
import sys
import tkinter as tk
import platform
from tkinter import messagebox
import customtkinter as ctk

from src.gui.styles import UIStyle
from src.gui.components import CardFrame, ToolTip
from src.gui.utils import load_json_data, save_json_data
from src.gui.constants import STATUS_COLUMNS, SINNER_LIST, TEAM_ORDER
from src.gui.themes import load_available_themes
import src.shared_vars as sv
import common

# Global state for this module
squad_data = {}
dropdown_vars = {}
expand_frames = {}
settings_ui_vars = {}

def get_config_path(base_path):
    return os.path.join(base_path, "config", "gui_config.json")

def get_squad_json_path(base_path):
    return os.path.join(base_path, "config", "squad_order.json")

def get_slow_squad_json_path(base_path):
    return os.path.join(base_path, "config", "delayed_squad_order.json")

def sinner_key(name):
    """Convert a sinner name to a standardized key"""
    return name.lower().replace(" ", "").replace("ō", "o").replace("ū", "u")

def load_settings_tab(parent, config, shared_vars, save_callback, base_path, root_ref, restart_callback=None, update_shortcuts_callback=None):
    """Populate the settings tab"""
    # Clear existing
    for widget in parent.winfo_children():
        widget.destroy()

    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    ctk.CTkLabel(scroll_frame, text="Settings", font=UIStyle.HEADER_FONT).pack(pady=(20, 10), anchor="w", padx=20)

    _setup_profiles(scroll_frame, base_path, save_callback)
    _setup_sinner_assignment(scroll_frame, base_path)
    _setup_display_settings(scroll_frame, shared_vars, save_callback)
    _setup_mouse_offsets(scroll_frame, shared_vars, save_callback, root_ref)
    _setup_misc_settings(scroll_frame, shared_vars, save_callback, config)
    _setup_image_thresholds(scroll_frame, base_path)
    _setup_automation_settings(scroll_frame, shared_vars, save_callback)
    _setup_shortcuts(scroll_frame, config, save_callback, root_ref, update_shortcuts_callback)
    _setup_theme(scroll_frame, config, save_callback, base_path, root_ref, restart_callback)
    _setup_danger_zone(scroll_frame, base_path)

def _setup_profiles(parent, base_path, save_callback):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Configuration Profiles", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    profiles_dir = os.path.join(base_path, "profiles")
    os.makedirs(profiles_dir, exist_ok=True)
    
    profiles_frame = ctk.CTkScrollableFrame(card, height=150, fg_color="transparent")
    profiles_frame.pack(fill="x", padx=10, pady=(0, 10))
    
    selected_profile = ctk.StringVar()
    
    def refresh_profiles():
        for widget in profiles_frame.winfo_children():
            widget.destroy()
            
        profiles = [d for d in os.listdir(profiles_dir) if os.path.isdir(os.path.join(profiles_dir, d))]
        
        if not profiles:
            ctk.CTkLabel(profiles_frame, text="No profiles found", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=10)
            return
            
        for prof in profiles:
            rb = ctk.CTkRadioButton(
                profiles_frame, 
                text=prof, 
                variable=selected_profile, 
                value=prof,
                font=UIStyle.BODY_FONT
            )
            rb.pack(anchor="w", pady=2, padx=5)
    
    refresh_profiles()
    
    actions_frame = ctk.CTkFrame(card, fg_color="transparent")
    actions_frame.pack(fill="x", padx=10, pady=(0, 15))
    
    new_profile_entry = ctk.CTkEntry(actions_frame, placeholder_text="New Profile Name", height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT)
    new_profile_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
    
    def save_profile():
        name = new_profile_entry.get().strip()
        if not name:
            messagebox.showerror("Error", "Please enter a profile name")
            return
        
        name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        target_dir = os.path.join(profiles_dir, name)
        os.makedirs(target_dir, exist_ok=True)
        
        save_callback() # Save current state first
        
        config_dir = os.path.join(base_path, "config")
        count = 0
        for filename in os.listdir(config_dir):
            if filename.endswith(".json"):
                shutil.copy2(os.path.join(config_dir, filename), os.path.join(target_dir, filename))
                count += 1
        
        messagebox.showinfo("Success", f"Profile '{name}' saved with {count} files.")
        new_profile_entry.delete(0, 'end')
        refresh_profiles()

    def load_profile():
        name = selected_profile.get()
        if not name:
            messagebox.showerror("Error", "Please select a profile")
            return
            
        target_dir = os.path.join(profiles_dir, name)
        if not messagebox.askyesno("Confirm", f"Load profile '{name}'? Current settings will be overwritten."):
            return
            
        config_dir = os.path.join(base_path, "config")
        for filename in os.listdir(target_dir):
            if filename.endswith(".json"):
                shutil.copy2(os.path.join(target_dir, filename), os.path.join(config_dir, filename))
        
        messagebox.showinfo("Success", "Profile loaded. Please restart application.")

    ctk.CTkButton(actions_frame, text="Save", command=save_profile, width=80).pack(side="left", padx=5)
    ctk.CTkButton(actions_frame, text="Load", command=load_profile, width=80).pack(side="left", padx=5)

def _setup_sinner_assignment(parent, base_path):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Assign Sinners to Team", font=UIStyle.SUBHEADER_FONT).pack(anchor="center", pady=(15, 10))
    
    container = ctk.CTkFrame(card, fg_color="transparent")
    container.pack(pady=(0, 15))
    
    global squad_data
    squad_data = load_json_data(get_squad_json_path(base_path))
    
    for col_idx, group in enumerate(STATUS_COLUMNS):
        col = ctk.CTkFrame(container, fg_color="transparent")
        col.grid(row=0, column=col_idx, padx=15, sticky="n")
        
        for row_idx, status in enumerate(group):
            wrapper = ctk.CTkFrame(col, fg_color="transparent")
            wrapper.grid(row=row_idx, column=0, sticky="nw")
            
            arrow_var = ctk.StringVar(value="▶")
            
            def make_toggle(stat=status, arrow=arrow_var, btn_ref=None):
                def toggle():
                    if expand_frames[stat].winfo_ismapped():
                        expand_frames[stat].pack_forget()
                        arrow.set("▶")
                    else:
                        _populate_sinner_dropdowns(expand_frames[stat], stat, base_path)
                        expand_frames[stat].pack(pady=(2, 8), fill="x")
                        arrow.set("▼")
                    if btn_ref: btn_ref.configure(text=f"{arrow.get()} {stat.capitalize()}")
                return toggle
            
            btn = ctk.CTkButton(wrapper, text=f"▶ {status.capitalize()}", width=200, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.SUBHEADER_FONT, anchor="w")
            btn.configure(command=make_toggle(status, arrow_var, btn))
            btn.pack(anchor="w", pady=(0, 6))
            
            frame = ctk.CTkFrame(wrapper, fg_color="transparent", corner_radius=0)
            expand_frames[status] = frame
            frame.pack_forget()
            dropdown_vars[status] = []

def _populate_sinner_dropdowns(frame, status, base_path):
    if len(frame.winfo_children()) > 0: return
    
    default_order = squad_data.get(status, {})
    reverse_map = {v: k for k, v in default_order.items()}
    
    for i in range(12):
        row = ctk.CTkFrame(frame, fg_color="transparent")
        row.pack(pady=1, anchor="w")
        
        ctk.CTkLabel(row, text=f"{i+1}.", width=30, anchor="e", font=UIStyle.BODY_FONT, text_color="#b0b0b0").pack(side="left", padx=(0, 10))
        
        var = ctk.StringVar()
        raw_name = reverse_map.get(i + 1)
        pretty = next((x for x in SINNER_LIST if sinner_key(x) == raw_name), "None") if raw_name else "None"
        var.set(pretty)
        
        def callback(s=status, idx=i, v=var):
            _dropdown_callback(s, idx, base_path)
            
        dropdown = ctk.CTkOptionMenu(row, variable=var, values=SINNER_LIST + ["None"], width=180, command=lambda _: callback())
        dropdown.pack(side="left")
        dropdown_vars[status].append(var)

def _dropdown_callback(status, index, base_path):
    try:
        new_val = dropdown_vars[status][index].get()
        if new_val != "None":
            for i, var in enumerate(dropdown_vars[status]):
                if i != index and var.get() == new_val:
                    # Try to find the old key for the current index to swap
                    old_key = next((k for k, v in squad_data.get(status, {}).items() if v == index + 1), None)
                    pretty_old = next((x for x in SINNER_LIST if sinner_key(x) == old_key), "None") if old_key else "None"
                    var.set(pretty_old)
                    break
        
        entries = dropdown_vars[status]
        updated = {}
        for i, var in enumerate(entries):
            val = var.get()
            if val != "None":
                updated[sinner_key(val)] = i + 1
        
        squad_data[status] = updated
        save_json_data(get_squad_json_path(base_path), squad_data)
        save_json_data(get_slow_squad_json_path(base_path), squad_data)
        
    except Exception as e:
        print(f"Error in dropdown callback: {e}")

def _setup_display_settings(parent, shared_vars, save_callback):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(card, text="Display Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    frame = ctk.CTkFrame(card, fg_color="transparent")
    frame.pack(pady=(0, 15))
    
    ctk.CTkLabel(frame, text="Game Monitor:", font=UIStyle.BODY_FONT).pack(side="left", padx=10)
    
    try:
        monitors = common.list_available_monitors()
        options = [f"Monitor {m['index']} ({m['width']}x{m['height']})" for m in monitors]
    except:
        options = ["Monitor 1"]
        
    current = shared_vars.game_monitor.value
    default_val = next((o for o in options if f"Monitor {current}" in o), options[0] if options else "")
    
    var = ctk.StringVar(value=default_val)
    
    def update_monitor(choice):
        try:
            idx = int(choice.split()[1])
            shared_vars.game_monitor.value = idx
            common.set_game_monitor(idx)
            save_callback()
        except:
            pass
            
    ctk.CTkOptionMenu(frame, variable=var, values=options, command=update_monitor, width=200).pack(side="left")

def _setup_mouse_offsets(parent, shared_vars, save_callback, root):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(card, text="Mouse Offsets", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    frame = ctk.CTkFrame(card, fg_color="transparent")
    frame.pack(padx=20, pady=(0, 15))
    
    def add_offset_entry(label, var_name):
        row = ctk.CTkFrame(frame)
        row.pack(pady=5)
        ctk.CTkLabel(row, text=label, width=100, anchor="e").pack(side="left", padx=10)
        entry = ctk.CTkEntry(row, width=100)
        entry.pack(side="left", padx=10)
        
        val = getattr(shared_vars, var_name).value
        entry.insert(0, str(val))
        
        def save(event=None):
            try:
                new_val = int(entry.get())
                getattr(shared_vars, var_name).value = new_val
                save_callback()
            except:
                pass
        
        entry.bind("<FocusOut>", save)
        entry.bind("<Return>", save)
        
    add_offset_entry("X Offset:", "x_offset")
    add_offset_entry("Y Offset:", "y_offset")
    
    ctk.CTkLabel(frame, text="Positive values move right/down, negative left/up.", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=5)

def _setup_misc_settings(parent, shared_vars, save_callback, config):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(card, text="Misc Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    frame = ctk.CTkFrame(card, fg_color="transparent")
    frame.pack(pady=(0, 15), padx=20, fill="x")
    
    def add_bool(label, var_name):
        val = getattr(shared_vars, var_name).value
        var = ctk.BooleanVar(value=val)
        def cmd():
            getattr(shared_vars, var_name).value = var.get()
            save_callback()
        ctk.CTkCheckBox(frame, text=label, variable=var, command=cmd).pack(anchor="w", pady=5)
        
    add_bool("Debug Image Matches", "debug_image_matches")
    add_bool("Convert to Grayscale (Speed Boost)", "convert_images_to_grayscale")
    add_bool("Reconnect only when Internet Reachable", "reconnect_when_internet_reachable")
    
    # Auto update
    auto_upd = ctk.BooleanVar(value=config.get("Settings", {}).get("auto_update", False))
    def toggle_upd():
        config["Settings"]["auto_update"] = auto_upd.get()
        save_callback()
    ctk.CTkCheckBox(frame, text="Auto Update on Startup", variable=auto_upd, command=toggle_upd).pack(anchor="w", pady=5)
    
    # Reconnection delay
    row = ctk.CTkFrame(frame, fg_color="transparent")
    row.pack(fill="x", pady=5)
    ctk.CTkLabel(row, text="Reconnection Delay (s):", width=200, anchor="w").pack(side="left")
    rec_entry = ctk.CTkEntry(row, width=80)
    rec_entry.pack(side="left")
    rec_entry.insert(0, str(shared_vars.reconnection_delay.value))
    
    def save_rec(e=None):
        try:
            val = int(rec_entry.get())
            if val < 1: val = 1
            shared_vars.reconnection_delay.value = val
            save_callback()
        except: pass
    rec_entry.bind("<FocusOut>", save_rec)
    
    # Click delay
    row2 = ctk.CTkFrame(frame, fg_color="transparent")
    row2.pack(fill="x", pady=5)
    ctk.CTkLabel(row2, text="Click Delay (s):", width=200, anchor="w").pack(side="left")
    click_entry = ctk.CTkEntry(row2, width=80)
    click_entry.pack(side="left")
    click_entry.insert(0, str(shared_vars.click_delay.value))
    
    def save_click(e=None):
        try:
            val = float(click_entry.get())
            if val < 0: val = 0
            shared_vars.click_delay.value = val
            save_callback()
        except: pass
    click_entry.bind("<FocusOut>", save_click)

def _setup_image_thresholds(parent, base_path):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Image Threshold Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))
    
    # Global threshold adjustment
    global_row = ctk.CTkFrame(card, fg_color="transparent")
    global_row.pack(pady=5, fill="x", padx=20)
    
    ctk.CTkLabel(global_row, text="Global Adjustment:", width=150, anchor="w", font=UIStyle.BODY_FONT).pack(side="left")
    global_entry = ctk.CTkEntry(global_row, width=80, font=UIStyle.BODY_FONT)
    global_entry.pack(side="left", padx=(0, 10))
    
    apply_global_var = ctk.BooleanVar()
    ctk.CTkSwitch(global_row, text="Don't apply to modified", variable=apply_global_var, font=UIStyle.BODY_FONT).pack(side="left", padx=10)
    
    # Load initial values
    threshold_config = sv.image_threshold_config
    global_entry.insert(0, str(threshold_config.get("global_adjustment", 0.0)))
    apply_global_var.set(not threshold_config.get("apply_global_to_modified", True))
    
    def save_global(*args):
        try:
            val = float(global_entry.get())
            config = sv.ConfigCache.get_config("image_thresholds")
            config["global_adjustment"] = val
            config["apply_global_to_modified"] = not apply_global_var.get()
            
            save_json_data(os.path.join(base_path, "config", "image_thresholds.json"), config)
            sv.ConfigCache.reload_config("image_thresholds")
            sv.image_threshold_config = sv.ConfigCache.get_config("image_thresholds")
        except ValueError: pass

    global_entry.bind('<FocusOut>', save_global)
    global_entry.bind('<Return>', save_global)
    apply_global_var.trace("w", save_global)
    
    # Tree View
    tree_frame = ctk.CTkFrame(card, fg_color="transparent")
    tree_frame.pack(pady=5, fill="both", expand=True, padx=10)
    ctk.CTkLabel(tree_frame, text="Image-Specific Adjustments:", font=UIStyle.BODY_FONT).pack(pady=(5, 0), anchor="w", padx=10)
    
    content_area = ctk.CTkFrame(tree_frame, fg_color="transparent")
    content_area.pack(fill="both", expand=True)

    def folder_has_images(path):
        for root, _, files in os.walk(path):
            if any(f.lower().endswith(('.png', '.jpg')) for f in files): return True
        return False

    def create_folder_node(parent_frame, folder_name, rel_path, level):
        full_path = os.path.join(base_path, rel_path)
        if not os.path.exists(full_path): return

        wrapper = ctk.CTkFrame(parent_frame, fg_color="transparent")
        wrapper.pack(fill="x", pady=1, padx=(level*20, 0))
        
        header = ctk.CTkFrame(wrapper, fg_color="transparent")
        header.pack(fill="x")
        
        is_expanded = ctk.BooleanVar(value=False)
        children_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
        
        def toggle():
            if is_expanded.get():
                children_frame.pack_forget()
                btn.configure(text="▶")
                is_expanded.set(False)
            else:
                children_frame.pack(fill="x")
                btn.configure(text="▼")
                is_expanded.set(True)
                if not children_frame.winfo_children():
                    load_children(children_frame, rel_path, level + 1)

        btn = ctk.CTkButton(header, text="▶", width=20, height=20, command=toggle, fg_color="transparent", text_color="gray")
        btn.pack(side="left")
        
        lbl = ctk.CTkLabel(header, text=f"📁 {folder_name}", font=UIStyle.SMALL_FONT, cursor="hand2")
        lbl.pack(side="left", padx=5)
        
        def open_folder(e):
            try:
                if platform.system() == "Windows": os.startfile(full_path)
                elif platform.system() == "Darwin": subprocess.run(["open", full_path])
                else: subprocess.run(["xdg-open", full_path])
            except: pass
        lbl.bind("<Double-Button-1>", open_folder)

        # Folder threshold
        # Only show if direct images exist
        has_direct = any(f.lower().endswith(('.png', '.jpg')) for f in os.listdir(full_path) if os.path.isfile(os.path.join(full_path, f)))
        if has_direct:
            f_entry = ctk.CTkEntry(header, width=60, placeholder_text="0.0", font=UIStyle.SMALL_FONT)
            f_entry.pack(side="left", padx=10)
            
            curr = sv.image_threshold_config.get("folder_adjustments", {}).get(rel_path, 0.0)
            if curr != 0.0: f_entry.insert(0, str(curr))
            
            def save_folder(*args):
                try:
                    val = float(f_entry.get()) if f_entry.get() else 0.0
                    cfg = sv.ConfigCache.get_config("image_thresholds")
                    if "folder_adjustments" not in cfg: cfg["folder_adjustments"] = {}
                    
                    if val != 0.0: cfg["folder_adjustments"][rel_path] = val
                    elif rel_path in cfg["folder_adjustments"]: del cfg["folder_adjustments"][rel_path]
                    
                    save_json_data(os.path.join(base_path, "config", "image_thresholds.json"), cfg)
                    sv.ConfigCache.reload_config("image_thresholds")
                    sv.image_threshold_config = sv.ConfigCache.get_config("image_thresholds")
                except ValueError: pass
            
            f_entry.bind('<FocusOut>', save_folder)
            f_entry.bind('<Return>', save_folder)

    def create_image_node(parent_frame, image_name, rel_path, level):
        wrapper = ctk.CTkFrame(parent_frame, fg_color="transparent")
        wrapper.pack(fill="x", pady=1, padx=(level*20, 0))
        
        lbl = ctk.CTkLabel(wrapper, text=f"🖼️ {image_name}", font=UIStyle.SMALL_FONT)
        lbl.pack(side="left", padx=25)
        
        i_entry = ctk.CTkEntry(wrapper, width=60, placeholder_text="0.0", font=UIStyle.SMALL_FONT)
        i_entry.pack(side="left", padx=10)
        
        curr = sv.image_threshold_config.get("image_adjustments", {}).get(rel_path, 0.0)
        if curr != 0.0: i_entry.insert(0, str(curr))
        
        def save_img(*args):
            try:
                val = float(i_entry.get()) if i_entry.get() else 0.0
                cfg = sv.ConfigCache.get_config("image_thresholds")
                if "image_adjustments" not in cfg: cfg["image_adjustments"] = {}
                
                if val != 0.0: cfg["image_adjustments"][rel_path] = val
                elif rel_path in cfg["image_adjustments"]: del cfg["image_adjustments"][rel_path]
                
                save_json_data(os.path.join(base_path, "config", "image_thresholds.json"), cfg)
                sv.ConfigCache.reload_config("image_thresholds")
                sv.image_threshold_config = sv.ConfigCache.get_config("image_thresholds")
            except ValueError: pass
            
        i_entry.bind('<FocusOut>', save_img)
        i_entry.bind('<Return>', save_img)

    def load_children(parent_frame, current_path, level):
        full_path = os.path.join(base_path, current_path)
        try:
            items = sorted(os.listdir(full_path))
            folders = []
            images = []
            
            for item in items:
                item_path = os.path.join(full_path, item)
                if os.path.isdir(item_path):
                    # Check if folder has images recursively
                    rel = f"{current_path}/{item}" if current_path else item
                    if folder_has_images(item_path):
                        folders.append((item, rel))
                elif item.lower().endswith(('.png', '.jpg')):
                    rel = f"{current_path}/{item}" if current_path else item
                    images.append((item, rel))
            
            for name, rel in folders:
                create_folder_node(parent_frame, name, rel, level)
            for name, rel in images:
                create_image_node(parent_frame, name, rel, level)
                
        except Exception as e:
            print(f"Error loading {current_path}: {e}")

    # Initialize with pictures folder
    if os.path.exists(os.path.join(base_path, "pictures")):
        create_folder_node(content_area, "pictures", "pictures", 0)

def _setup_automation_settings(parent, shared_vars, save_callback):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(card, text="Automation Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    frame = ctk.CTkFrame(card, fg_color="transparent")
    frame.pack(pady=(0, 15), padx=20, fill="x")
    
    def add_bool(label, var_name):
        val = getattr(shared_vars, var_name).value
        var = ctk.BooleanVar(value=val)
        def cmd():
            getattr(shared_vars, var_name).value = var.get()
            save_callback()
        ctk.CTkCheckBox(frame, text=label, variable=var, command=cmd).pack(anchor="w", pady=5)
        
    add_bool("Skip using EGO in Battle", "skip_ego_check")
    add_bool("Good PC Mode (Faster Transitions)", "good_pc_mode")

def _setup_shortcuts(parent, config, save_callback, root, update_callback):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    
    ctk.CTkLabel(card, text="Keyboard Shortcuts", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    shortcuts_frame = ctk.CTkFrame(card, fg_color="transparent")
    shortcuts_frame.pack(pady=(0, 15))

    # Load from config
    if 'Shortcuts' not in config:
        config['Shortcuts'] = {}
        
    defaults = {
        'mirror_dungeon': 'ctrl+q',
        'exp': 'ctrl+e',
        'threads': 'ctrl+r',
        'battle': 'ctrl+t',
        'call_function': 'ctrl+g',
        'terminate_functions': 'ctrl+shift+g',
        'chain_automation': 'ctrl+b'
    }
    
    for key, val in defaults.items():
        if key not in config['Shortcuts']:
            config['Shortcuts'][key] = val
            
    # Helper for shortcut rows
    def create_shortcut_row(label_text, shortcut_key):
        row = ctk.CTkFrame(shortcuts_frame)
        row.pack(fill="x", pady=5)
        ctk.CTkLabel(row, text=label_text, width=150, anchor="e", font=UIStyle.BODY_FONT).pack(side="left", padx=(10, 10))
        
        current_val = config['Shortcuts'].get(shortcut_key, "")
        var = ctk.StringVar(value=current_val)
        
        entry = ctk.CTkEntry(row, width=150, font=UIStyle.BODY_FONT, textvariable=var)
        entry.pack(side="left", padx=(0, 10))
        
        def save_shortcut(event=None):
            new_val = var.get()
            config['Shortcuts'][shortcut_key] = new_val
            save_callback()
            if update_callback:
                update_callback()
                
        entry.bind('<FocusOut>', save_shortcut)
        entry.bind('<Return>', save_shortcut)

    create_shortcut_row("Mirror Dungeon:", 'mirror_dungeon')
    create_shortcut_row("Exp:", 'exp')
    create_shortcut_row("Threads:", 'threads')
    create_shortcut_row("Start Battle:", 'battle')
    create_shortcut_row("Chain Automation:", 'chain_automation')
    create_shortcut_row("Call Function:", 'call_function')
    create_shortcut_row("Terminate Functions:", 'terminate_functions')

    # Help text
    shortcut_help = ctk.CTkLabel(shortcuts_frame, text="Format examples: ctrl+q, alt+s, shift+x", 
                                font=UIStyle.SMALL_FONT, text_color="gray")
    shortcut_help.pack(pady=(5, 10))

def _setup_theme(parent, config, save_callback, base_path, root, restart_callback):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(card, text="Theme", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))
    
    themes = load_available_themes(base_path)
    current = config.get("Settings", {}).get("appearance_mode", "Dark")
    
    def change_theme(new_theme):
        # Save config first
        config["Settings"]["appearance_mode"] = new_theme
        save_callback()
        
        # If we have a restart callback, use it to apply theme properly
        if restart_callback:
            restart_callback(new_theme)
        
    ctk.CTkOptionMenu(card, values=list(themes.keys()), command=change_theme, variable=ctk.StringVar(value=current)).pack(pady=(0, 15))

def _setup_danger_zone(parent, base_path):
    card = CardFrame(parent)
    card.pack(fill="x", pady=10, padx=10)
    ctk.CTkLabel(card, text="Danger Zone", font=UIStyle.SUBHEADER_FONT, text_color="#ff5555").pack(pady=(15, 10))
    
    def reset():
        if messagebox.askyesno("Reset", "Reset all settings to default? This will restart the application."):
            config_dir = os.path.join(base_path, "config")
            backup = f"{config_dir}_backup_{int(time.time())}"
            try:
                if os.path.exists(config_dir):
                    shutil.move(config_dir, backup)
                os.execl(sys.executable, sys.executable, *sys.argv)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to reset: {e}")
                
    ctk.CTkButton(card, text="Reset to Defaults", command=reset, fg_color="#c42b1c", hover_color="#8f1f14").pack(pady=(0, 15))
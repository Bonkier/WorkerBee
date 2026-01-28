import os
import json
import time
import threading
import customtkinter as ctk
from tkinter import messagebox
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import load_json_data, save_json_data
from src.gui.constants import TEAM_ORDER

# Global state for mirror page
mirror_checkbox_vars = {}
pack_dropdown_vars = {}
pack_expand_frames = {}
pack_exception_expand_frames = {}
grace_dropdown_vars = []
grace_expand_frame = None
grace_selection_data = {}

def load_mirror_tab(parent, config, shared_vars, callbacks, ui_context, base_path, save_callback):
    """Load and render the Mirror Dungeon tab"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)
    
    # Run Configuration Card
    run_card = CardFrame(scroll_frame)
    run_card.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(run_card, text="Run Configuration", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

    input_row = ctk.CTkFrame(run_card, fg_color="transparent")
    input_row.pack(pady=(0, 10))

    ctk.CTkLabel(input_row, text="Number of Runs:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
    entry = ctk.CTkEntry(input_row, height=UIStyle.ENTRY_HEIGHT, font=UIStyle.BODY_FONT, width=80)
    entry.pack(side="left")
    entry.insert(0, str(config.get('Settings', {}).get('mirror_runs', 1)))
    ui_context['mirror_runs_entry'] = entry

    def save_runs(event=None):
        try:
            runs = int(entry.get())
            config['Settings']['mirror_runs'] = runs
            if hasattr(shared_vars, 'mirror_runs'):
                shared_vars.mirror_runs.value = runs
            save_callback()
        except ValueError:
            pass

    entry.bind("<FocusOut>", save_runs)
    entry.bind("<Return>", save_runs)

    def start_mirror_wrapper():
        try:
            runs = int(entry.get())
            config['Settings']['mirror_runs'] = runs
            save_callback()
            callbacks['start_mirror'](runs)
        except ValueError:
            pass

    start_button = ctk.CTkButton(run_card, text="Start", command=start_mirror_wrapper, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT)
    start_button.pack(pady=(0, 20))
    ui_context['mirror_start_button'] = start_button

    settings_card = CardFrame(scroll_frame)
    settings_card.pack(fill="x", padx=10, pady=10)

    ctk.CTkLabel(settings_card, text="Advanced Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 5))

    master_frame = ctk.CTkFrame(settings_card, fg_color="transparent")
    master_frame.pack(fill="x", padx=10, pady=10)
    
    master_content = ctk.CTkFrame(master_frame, fg_color="transparent")
    
    is_expanded = ctk.BooleanVar(value=False)
    
    def toggle_master():
        if is_expanded.get():
            master_content.pack_forget()
            expand_btn.configure(text="▶ Settings")
            is_expanded.set(False)
        else:
            master_content.pack(fill="x", pady=10)
            expand_btn.configure(text="▼ Settings")
            is_expanded.set(True)
            if not master_content.winfo_children():
                load_mirror_settings(master_content, base_path, shared_vars, config, save_callback)

    expand_btn = ctk.CTkButton(master_frame, text="▶ Settings", command=toggle_master, width=200, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.SUBHEADER_FONT, anchor="w")
    expand_btn.pack(anchor="center")

def load_mirror_settings(parent, base_path, shared_vars, config, save_callback):
    """Populate the advanced settings content"""

    ctk.CTkLabel(parent, text="Your Team", font=UIStyle.SUBHEADER_FONT).pack(pady=(10, 5))
    team_frame = ctk.CTkFrame(parent, fg_color="transparent")
    team_frame.pack(pady=5)

    status_path = os.path.join(base_path, "config", "status_selection.json")
    saved_team = set()
    if os.path.exists(status_path):
        try:
            data = load_json_data(status_path)
            saved_team = set(data.values())
        except: pass

    global mirror_checkbox_vars
    mirror_checkbox_vars = {}

    for name, row, col in TEAM_ORDER:
        var = ctk.BooleanVar(value=name in saved_team)
        mirror_checkbox_vars[name] = var
        chk = ctk.CTkCheckBox(team_frame, text=name.capitalize(), variable=var, 
                              command=lambda: save_team_selection(base_path), font=UIStyle.BODY_FONT)
        chk.grid(row=row, column=col, padx=10, pady=5, sticky="w")

    ctk.CTkLabel(parent, text="Basic Settings", font=UIStyle.SUBHEADER_FONT).pack(pady=(20, 5))
    basic_frame = ctk.CTkFrame(parent, fg_color="transparent")
    basic_frame.pack(pady=5)
    
    def add_setting_checkbox(label, key, default=False):
        current_val = config.get("Settings", {}).get(key, default)
        
        var = ctk.BooleanVar(value=current_val)
        
        def on_change():
            if "Settings" not in config: config["Settings"] = {}
            config["Settings"][key] = var.get()

            if hasattr(shared_vars, key):
                getattr(shared_vars, key).value = var.get()

            save_callback()
                
        chk = ctk.CTkCheckBox(basic_frame, text=label, variable=var, command=on_change, font=UIStyle.BODY_FONT)
        chk.pack(anchor="w", padx=10, pady=5)
        return var

    add_setting_checkbox("Hard Mode", "hard_mode", False)
    add_setting_checkbox("Skip Rest Shop", "skip_restshop", False)
    add_setting_checkbox("Skip EGO Check", "skip_ego_check", False)
    add_setting_checkbox("Skip EGO Fusion", "skip_ego_fusion", False)
    add_setting_checkbox("Skip Sinner Healing", "skip_sinner_healing", False)
    add_setting_checkbox("Skip EGO Enhancing", "skip_ego_enhancing", False)
    add_setting_checkbox("Skip EGO Buying", "skip_ego_buying", False)
    add_setting_checkbox("Prioritize List over Status", "prioritize_list_over_status", False)
    
    add_setting_checkbox("Claim Rewards on Defeat", "claim_on_defeat", False)

    retry_frame = ctk.CTkFrame(basic_frame, fg_color="transparent")
    retry_frame.pack(anchor="w", padx=10, pady=5)
    ctk.CTkLabel(retry_frame, text="Retry Count on Defeat:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
    
    retry_val = config.get("Settings", {}).get("retry_count", 0)
    
    retry_entry = ctk.CTkEntry(retry_frame, width=60, font=UIStyle.BODY_FONT)
    retry_entry.pack(side="left")
    retry_entry.insert(0, str(retry_val))
    
    def save_retry(event=None):
        try:
            val = int(retry_entry.get())
            if "Settings" not in config: config["Settings"] = {}
            config["Settings"]["retry_count"] = val
            shared_vars.retry_count.value = val
            save_callback()
        except: pass
        
    retry_entry.bind("<FocusOut>", save_retry)
    retry_entry.bind("<Return>", save_retry)

    refresh_frame = ctk.CTkFrame(basic_frame, fg_color="transparent")
    refresh_frame.pack(anchor="w", padx=10, pady=5)
    ctk.CTkLabel(refresh_frame, text="Pack Refreshes:", font=UIStyle.BODY_FONT).pack(side="left", padx=(0, 10))
    
    refresh_val = 7
    try:
        refresh_val = config.get("Settings", {}).get("pack_refreshes", 7)
    except: pass
    
    refresh_entry = ctk.CTkEntry(refresh_frame, width=60, font=UIStyle.BODY_FONT)
    refresh_entry.pack(side="left")
    refresh_entry.insert(0, str(refresh_val))
    
    def save_refresh(event=None):
        try:
            val = int(refresh_entry.get())
            if "Settings" not in config: config["Settings"] = {}
            config["Settings"]["pack_refreshes"] = val
            shared_vars.pack_refreshes.value = val
            save_callback()
        except: pass
        
    refresh_entry.bind("<FocusOut>", save_refresh)
    refresh_entry.bind("<Return>", save_refresh)

    ctk.CTkLabel(parent, text="Grace Selection", font=UIStyle.SUBHEADER_FONT).pack(pady=(20, 5))
    grace_frame = ctk.CTkFrame(parent, fg_color="transparent")
    grace_frame.pack(fill="x", pady=5)
    load_grace_selection_ui(grace_frame, base_path)

    ctk.CTkLabel(parent, text="Pack Priority", font=UIStyle.SUBHEADER_FONT).pack(pady=(20, 5))
    pack_frame = ctk.CTkFrame(parent, fg_color="transparent")
    pack_frame.pack(fill="x", pady=5)
    
    load_pack_priority_ui(pack_frame, base_path)

    ctk.CTkLabel(parent, text="Pack Exceptions", font=UIStyle.SUBHEADER_FONT).pack(pady=(20, 5))
    pack_ex_frame = ctk.CTkFrame(parent, fg_color="transparent")
    pack_ex_frame.pack(fill="x", pady=5)
    
    load_pack_exceptions_ui(pack_ex_frame, base_path)

    ctk.CTkLabel(parent, text="Fuse Exceptions", font=UIStyle.SUBHEADER_FONT).pack(pady=(20, 5))
    fuse_frame = ctk.CTkFrame(parent, fg_color="transparent")
    fuse_frame.pack(fill="x", pady=5)
    
    load_fuse_exceptions_ui(fuse_frame, base_path)

    def refresh_fuse():
        load_fuse_exceptions_ui(fuse_frame, base_path)
    ctk.CTkButton(parent, text="Refresh Fusion List", command=refresh_fuse, height=24, font=UIStyle.SMALL_FONT).pack(pady=5)

def save_team_selection(base_path):
    status_path = os.path.join(base_path, "config", "status_selection.json")
    selected = [name for name, var in mirror_checkbox_vars.items() if var.get()]

    existing_data = load_json_data(status_path)
    existing_list = [existing_data[str(i)] for i in sorted([int(k) for k in existing_data.keys()])] if existing_data else []

    final_list = [s for s in existing_list if s in selected]
    for s in selected:
        if s not in final_list:
            final_list.append(s)

    output = {str(i+1): s for i, s in enumerate(final_list)}
    save_json_data(status_path, output)

def load_grace_selection_ui(parent, base_path):
    global grace_selection_data, grace_dropdown_vars, grace_expand_frame
    
    grace_path = os.path.join(base_path, "config", "grace_selection.json")
    default_grace = {
        "order": {
            "Grace 1": 1, "Grace 2": 2, "Grace 3": 3, "Grace 4": 4, "Grace 5": 5
        }
    }
    grace_selection_data = load_json_data(grace_path)
    if not grace_selection_data:
        grace_selection_data = default_grace
        save_json_data(grace_path, grace_selection_data)

    GRACE_NAMES = ["star of the beniggening", "cumulating starcloud", "interstellar travel", "star shower", "binary star shop", "moon star shop", "favor of the nebula", "starlight guidance", "chance comet", "perfected possibility"]
    
    wrapper = ctk.CTkFrame(parent, fg_color="transparent")
    wrapper.pack(fill="x", padx=10)
    
    arrow_var = ctk.StringVar(value="▶")
    
    def toggle(btn=None):
        if grace_expand_frame.winfo_ismapped():
            grace_expand_frame.pack_forget()
            arrow_var.set("▶")
        else:
            grace_expand_frame.pack(fill="x", pady=5)
            arrow_var.set("▼")
        if btn: btn.configure(text=f"{arrow_var.get()} Grace Selection")

    btn = ctk.CTkButton(wrapper, text="▶ Grace Selection", command=lambda: toggle(btn), width=200, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.SUBHEADER_FONT, anchor="w")
    btn.pack(anchor="center")
    
    grace_expand_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
    grace_expand_frame.pack_forget()
    
    grace_dropdown_vars = []
    current_order = grace_selection_data.get("order", {})
    reverse_map = {v: k for k, v in current_order.items()}
    
    for i in range(10):
        row = ctk.CTkFrame(grace_expand_frame, fg_color="transparent")
        row.pack(pady=1, anchor="center")
        
        ctk.CTkLabel(row, text=f"{i+1}.", width=30, anchor="e", text_color="#b0b0b0").pack(side="left", padx=(0, 10))
        
        var = ctk.StringVar(value=reverse_map.get(i+1, "None"))
        grace_dropdown_vars.append(var)
        
        def on_change(idx=i):
            new_val = grace_dropdown_vars[idx].get()
            if new_val != "None":
                for j, v in enumerate(grace_dropdown_vars):
                    if j != idx and v.get() == new_val:
                        v.set("None")
                        break
            save_grace_selection(base_path)
            
        ctk.CTkOptionMenu(row, variable=var, values=GRACE_NAMES + ["None"], command=lambda _, i=i: on_change(i), width=200).pack(side="left")

def save_grace_selection(base_path):
    updated_order = {}
    for i, var in enumerate(grace_dropdown_vars):
        val = var.get()
        if val != "None":
            updated_order[val] = i + 1
            
    grace_selection_data["order"] = updated_order
    save_json_data(os.path.join(base_path, "config", "grace_selection.json"), grace_selection_data)

def load_floor_packs(base_path):
    floor_packs = {}
    packs_base_dir = os.path.join(base_path, "pictures", "mirror", "packs")
    floor_mapping = {"floor1": "f1", "floor2": "f2", "floor3": "f3", "floor4": "f4", "floor5": "f5"}
    
    for floor_key, folder_name in floor_mapping.items():
        floor_dir = os.path.join(packs_base_dir, folder_name)
        packs = []
        if os.path.exists(floor_dir):
            for filename in os.listdir(floor_dir):
                if filename.lower().endswith(('.png', '.jpg', '.jpeg')):
                    packs.append(os.path.splitext(filename)[0])
        packs.sort()
        floor_packs[floor_key] = packs
    return floor_packs

def load_pack_priority_ui(parent, base_path):
    global pack_dropdown_vars
    pack_dropdown_vars = {} 
    floor_packs = load_floor_packs(base_path)
    pack_priority_path = os.path.join(base_path, "config", "pack_priority.json")
    pack_priority_data = load_json_data(pack_priority_path)
    
    columns = [["floor1", "floor2"], ["floor3", "floor4"], ["floor5"]]
    
    for i in range(len(columns)):
        parent.grid_columnconfigure(i, weight=1)
    
    for col_idx, group in enumerate(columns):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.grid(row=0, column=col_idx, padx=10, sticky="n")
        
        for floor in group:
            wrapper = ctk.CTkFrame(col, fg_color="transparent")
            wrapper.pack(pady=5, fill="x")

            is_expanded = ctk.BooleanVar(value=False)
            content = ctk.CTkFrame(wrapper, fg_color="transparent")
            
            def toggle(f=floor, c=content, v=is_expanded, btn=None):
                if v.get():
                    c.pack_forget()
                    btn.configure(text=f"▶ {f.capitalize()}")
                    v.set(False)
                else:
                    c.pack(fill="x")
                    btn.configure(text=f"▼ {f.capitalize()}")
                    v.set(True)
            
            btn = ctk.CTkButton(wrapper, text=f"▶ {floor.capitalize()}", width=150, height=30, anchor="w")
            btn.configure(command=lambda b=btn, t=toggle: t(btn=b))
            btn.pack(anchor="center")

            if floor not in pack_dropdown_vars:
                pack_dropdown_vars[floor] = []
                
            current_prio = pack_priority_data.get(floor, {})
            reverse_map = {v: k for k, v in current_prio.items()}
            
            for i in range(len(floor_packs.get(floor, []))):
                row = ctk.CTkFrame(content, fg_color="transparent")
                row.pack(pady=1)
                ctk.CTkLabel(row, text=f"{i+1}.", width=20).pack(side="left")
                
                var = ctk.StringVar(value=reverse_map.get(i+1, "None"))
                pack_dropdown_vars[floor].append(var)

                def make_callback(f_val, idx_val, v_var):
                    def callback(choice):
                        if choice != "None":
                            for j, other_var in enumerate(pack_dropdown_vars[f_val]):
                                if j != idx_val and other_var.get() == choice:

                                    current_saved = load_json_data(pack_priority_path, {})
                                    floor_data = current_saved.get(f_val, {})

                                    old_key = next((k for k, val in floor_data.items() if val == idx_val + 1), None)
                                    other_var.set(old_key if old_key else "None")
                                    break
                        
                        save_pack_priority(base_path)
                    return callback
                
                ctk.CTkOptionMenu(row, variable=var, values=floor_packs.get(floor, []) + ["None"], 
                                  command=make_callback(floor, i, var), width=130).pack(side="left")

def save_pack_priority(base_path):
    data = {}
    for floor, vars_list in pack_dropdown_vars.items():
        data[floor] = {}
        for i, var in enumerate(vars_list):
            val = var.get()
            if val != "None":
                data[floor][val] = i + 1
    
    save_json_data(os.path.join(base_path, "config", "pack_priority.json"), data)
    save_json_data(os.path.join(base_path, "config", "delayed_pack_priority.json"), data)

# --- Pack Exceptions Logic ---
def load_pack_exceptions_ui(parent, base_path):
    floor_packs = load_floor_packs(base_path)
    exceptions_path = os.path.join(base_path, "config", "pack_exceptions.json")
    exceptions_data = load_json_data(exceptions_path)
    
    columns = [["floor1", "floor2"], ["floor3", "floor4"], ["floor5"]]
    
    for i in range(len(columns)):
        parent.grid_columnconfigure(i, weight=1)
    
    for col_idx, group in enumerate(columns):
        col = ctk.CTkFrame(parent, fg_color="transparent")
        col.grid(row=0, column=col_idx, padx=10, sticky="n")
        
        for floor in group:
            wrapper = ctk.CTkFrame(col, fg_color="transparent")
            wrapper.pack(pady=5, fill="x")
            
            is_expanded = ctk.BooleanVar(value=False)
            content = ctk.CTkFrame(wrapper, fg_color="transparent")
            
            def toggle(f=floor, c=content, v=is_expanded, btn=None):
                if v.get():
                    c.pack_forget()
                    btn.configure(text=f"▶ {f.capitalize()}")
                    v.set(False)
                else:
                    c.pack(fill="x")
                    btn.configure(text=f"▼ {f.capitalize()}")
                    v.set(True)
            
            btn = ctk.CTkButton(wrapper, text=f"▶ {floor.capitalize()}", width=150, height=30, anchor="w")
            btn.configure(command=lambda b=btn, t=toggle: t(btn=b))
            btn.pack(anchor="center")
            
            current_exceptions = exceptions_data.get(floor, [])
            
            for pack in floor_packs.get(floor, []):
                var = ctk.BooleanVar(value=pack in current_exceptions)
                
                def on_toggle(f=floor, p=pack, v=var):
                    update_pack_exception(base_path, f, p, v.get())
                    
                ctk.CTkCheckBox(content, text=pack, variable=var, command=on_toggle, font=UIStyle.SMALL_FONT).pack(anchor="w")

def update_pack_exception(base_path, floor, pack, is_checked):
    path = os.path.join(base_path, "config", "pack_exceptions.json")
    data = load_json_data(path)
    if floor not in data: data[floor] = []
    
    if is_checked and pack not in data[floor]:
        data[floor].append(pack)
    elif not is_checked and pack in data[floor]:
        data[floor].remove(pack)
        
    save_json_data(path, data)
    save_json_data(os.path.join(base_path, "config", "delayed_pack_exceptions.json"), data)

# --- Fuse Exceptions Logic ---
def load_fuse_exceptions_ui(parent, base_path):
    for widget in parent.winfo_children():
        widget.destroy()

    fuse_dir = os.path.join(base_path, "pictures", "CustomFuse")

    if not os.path.exists(fuse_dir):
        try:
            os.makedirs(fuse_dir)
        except OSError:
            pass

    custom_gifts_dir = os.path.join(fuse_dir, "CustomEgoGifts")
    if not os.path.exists(custom_gifts_dir):
        try:
            os.makedirs(custom_gifts_dir)
        except OSError:
            pass
        
    exceptions_path = os.path.join(base_path, "config", "fusion_exceptions.json")
    saved_exceptions = load_json_data(exceptions_path, [])

    other_items = []
    has_custom_ego_gifts = False
    
    if os.path.exists(fuse_dir):
        for item in os.listdir(fuse_dir):
            if item == "CustomEgoGifts":
                has_custom_ego_gifts = True
                continue
            
            full_path = os.path.join(fuse_dir, item)
            if os.path.isdir(full_path) or item.lower().endswith(('.png', '.jpg', '.jpeg')):
                other_items.append(item)

    wrapper = ctk.CTkFrame(parent, fg_color="transparent")
    wrapper.pack(fill="x", padx=10)

    content_frame = ctk.CTkFrame(wrapper, fg_color="transparent")
    
    def toggle(btn):
        if content_frame.winfo_ismapped():
            content_frame.pack_forget()
            btn.configure(text="▶ Fuse Exceptions")
        else:
            content_frame.pack(fill="x", pady=5)
            btn.configure(text="▼ Fuse Exceptions")

    btn = ctk.CTkButton(wrapper, text="▶ Fuse Exceptions", width=200, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.SUBHEADER_FONT, anchor="w")
    btn.configure(command=lambda: toggle(btn))
    btn.pack(anchor="center")

    if not has_custom_ego_gifts and not other_items:
        ctk.CTkLabel(content_frame, text="No items found in pictures/CustomFuse", font=UIStyle.SMALL_FONT, text_color="gray").pack(pady=10)

    def add_checkbox(name, is_dir):
        display_name = name if is_dir else os.path.splitext(name)[0]
        var = ctk.BooleanVar(value=display_name in saved_exceptions)
        
        def on_toggle(n=display_name, v=var):
            update_fuse_exception(base_path, n, v.get())
            
        ctk.CTkCheckBox(content_frame, text=display_name, variable=var, command=on_toggle, font=UIStyle.SMALL_FONT).pack(anchor="center", padx=20, pady=2)

    if has_custom_ego_gifts:
        add_checkbox("CustomEgoGifts", True)

        if other_items:
            separator = ctk.CTkFrame(content_frame, height=2, fg_color="#404040")
            separator.pack(fill="x", pady=5, padx=10)

    for item in other_items:
        is_dir = os.path.isdir(os.path.join(fuse_dir, item))
        add_checkbox(item, is_dir)

def update_fuse_exception(base_path, name, is_checked):
    path = os.path.join(base_path, "config", "fusion_exceptions.json")
    data = load_json_data(path, [])
    
    if is_checked and name not in data:
        data.append(name)
    elif not is_checked and name in data:
        data.remove(name)
        
    save_json_data(path, data)
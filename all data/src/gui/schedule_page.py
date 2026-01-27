import os
import json
import customtkinter as ctk
from datetime import datetime
from tkinter import messagebox
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import load_json_data, save_json_data, ensure_schedule_file

def load_schedule_tab(parent, base_path):
    """Load and render the schedule tab"""
    for widget in parent.winfo_children():
        widget.destroy()

    ensure_schedule_file(base_path)
    schedule_path = os.path.join(base_path, "config", "schedule.json")
    
    data = load_json_data(schedule_path)
    if not data:
        data = {"enabled": False, "tasks": []}

    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    ctk.CTkLabel(scroll_frame, text="Scheduler", font=UIStyle.HEADER_FONT).pack(pady=(20, 10), anchor="w", padx=20)
    
    # Global Enable Switch
    global_enabled = ctk.BooleanVar(value=data.get("enabled", False))
    
    def toggle_scheduler():
        data["enabled"] = global_enabled.get()
        save_json_data(schedule_path, data)
        
    switch_card = CardFrame(scroll_frame)
    switch_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkSwitch(switch_card, text="Enable Scheduler", variable=global_enabled, command=toggle_scheduler, font=UIStyle.SUBHEADER_FONT).pack(pady=15, padx=20, anchor="w")

    # Add Task Card
    add_task_card = CardFrame(scroll_frame)
    add_task_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(add_task_card, text="Add Scheduled Task", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 10))

    input_frame = ctk.CTkFrame(add_task_card, fg_color="transparent")
    input_frame.pack(pady=(0, 15), padx=20)

    ctk.CTkLabel(input_frame, text="Time (HH:MM):", font=UIStyle.BODY_FONT).grid(row=0, column=0, padx=5, pady=5)
    sched_time_entry = ctk.CTkEntry(input_frame, width=100, font=UIStyle.BODY_FONT)
    sched_time_entry.grid(row=0, column=1, padx=5, pady=5)
    sched_time_entry.insert(0, "12:00")

    ctk.CTkLabel(input_frame, text="Action:", font=UIStyle.BODY_FONT).grid(row=0, column=2, padx=5, pady=5)
    sched_type_var = ctk.StringVar(value="Mirror Dungeon")
    sched_type_dropdown = ctk.CTkOptionMenu(
        input_frame, 
        variable=sched_type_var, 
        values=["Mirror Dungeon", "Exp", "Threads", "Chain Automation"],
        font=UIStyle.BODY_FONT
    )
    sched_type_dropdown.grid(row=0, column=3, padx=5, pady=5)

    ctk.CTkLabel(input_frame, text="Runs:", font=UIStyle.BODY_FONT).grid(row=0, column=4, padx=5, pady=5)
    sched_runs_entry = ctk.CTkEntry(input_frame, width=60, font=UIStyle.BODY_FONT)
    sched_runs_entry.grid(row=0, column=5, padx=5, pady=5)
    sched_runs_entry.insert(0, "1")

    def add_schedule_task():
        time_str = sched_time_entry.get().strip()
        try:
            datetime.strptime(time_str, "%H:%M")
            runs = int(sched_runs_entry.get())
            if runs < 1: raise ValueError
        except ValueError:
            messagebox.showerror("Invalid Input", "Invalid time (HH:MM) or runs")
            return
            
        task = {
            "time": time_str,
            "type": sched_type_var.get(),
            "runs": runs,
            "enabled": True
        }
        
        data["tasks"].append(task)
        save_json_data(schedule_path, data)
        load_schedule_tab(parent, base_path) # Refresh

    ctk.CTkButton(add_task_card, text="Add Task", command=add_schedule_task, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(pady=(0, 15))

    # Tasks List
    ctk.CTkLabel(scroll_frame, text="Scheduled Tasks", font=UIStyle.SUBHEADER_FONT).pack(pady=(10, 5), anchor="w", padx=20)
    
    for i, task in enumerate(data.get("tasks", [])):
        task_card = CardFrame(scroll_frame)
        task_card.pack(fill="x", padx=10, pady=5)
        
        header_frame = ctk.CTkFrame(task_card, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=5)
        
        task_type = task.get("type", "Unknown")
        info_text = f"{task.get('time', '??:??')} - {task_type} ({task.get('runs', 1)} runs)"
        ctk.CTkLabel(header_frame, text=info_text, font=UIStyle.BODY_FONT, anchor="w").pack(side="left")
        
        def delete_task(idx=i):
            data["tasks"].pop(idx)
            save_json_data(schedule_path, data)
            load_schedule_tab(parent, base_path)

        ctk.CTkButton(header_frame, text="Delete", command=delete_task, width=60, height=24, fg_color="#c42b1c", hover_color="#8f1f14", font=UIStyle.SMALL_FONT).pack(side="right", padx=5)
        
        task_enabled = ctk.BooleanVar(value=task.get("enabled", True))
        def toggle_task(idx=i, var=task_enabled):
            data["tasks"][idx]["enabled"] = var.get()
            save_json_data(schedule_path, data)
            
        ctk.CTkSwitch(header_frame, text="", variable=task_enabled, command=lambda idx=i: toggle_task(idx), width=40).pack(side="right")
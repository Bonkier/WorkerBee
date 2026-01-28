import os
import json
import customtkinter as ctk
from datetime import datetime
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import load_json_data

def load_statistics_tab(parent, base_path):
    """Load and render the statistics tab"""
    for widget in parent.winfo_children():
        widget.destroy()
    
    stats_path = os.path.join(base_path, "config", "stats.json")
    data = load_json_data(stats_path)
    
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)
    
    ctk.CTkLabel(scroll_frame, text="Statistics", font=UIStyle.HEADER_FONT).pack(pady=(20, 10), anchor="w", padx=20)

    md_card = CardFrame(scroll_frame)
    md_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(md_card, text="Mirror Dungeon", font=UIStyle.SUBHEADER_FONT).pack(pady=10, padx=15, anchor="w")
    
    md_grid = ctk.CTkFrame(md_card, fg_color="transparent")
    md_grid.pack(pady=(0, 15), padx=20, fill="x")
    
    md_stats = data.get("mirror", {})
    runs = md_stats.get("runs", 0)
    wins = md_stats.get("wins", 0)
    losses = md_stats.get("losses", 0)
    win_rate = (wins / runs * 100) if runs > 0 else 0
    
    ctk.CTkLabel(md_grid, text=f"Total Runs: {runs}", font=UIStyle.BODY_FONT).pack(side="left", expand=True)
    ctk.CTkLabel(md_grid, text=f"Wins: {wins}", font=UIStyle.BODY_FONT, text_color="#4caf50").pack(side="left", expand=True)
    ctk.CTkLabel(md_grid, text=f"Losses: {losses}", font=UIStyle.BODY_FONT, text_color="#f44336").pack(side="left", expand=True)
    ctk.CTkLabel(md_grid, text=f"Win Rate: {win_rate:.1f}%", font=UIStyle.BODY_FONT).pack(side="left", expand=True)

    lux_card = CardFrame(scroll_frame)
    lux_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(lux_card, text="Luxcavations", font=UIStyle.SUBHEADER_FONT).pack(pady=10, padx=15, anchor="w")
    
    lux_grid = ctk.CTkFrame(lux_card, fg_color="transparent")
    lux_grid.pack(pady=(0, 15), padx=20, fill="x")
    
    exp_runs = data.get("exp", {}).get("runs", 0)
    threads_runs = data.get("threads", {}).get("runs", 0)
    
    ctk.CTkLabel(lux_grid, text=f"Exp Runs: {exp_runs}", font=UIStyle.BODY_FONT).pack(side="left", expand=True)
    ctk.CTkLabel(lux_grid, text=f"Thread Runs: {threads_runs}", font=UIStyle.BODY_FONT).pack(side="left", expand=True)

    if "history" in md_stats and md_stats["history"]:
        hist_card = CardFrame(scroll_frame)
        hist_card.pack(fill="x", padx=10, pady=10)
        ctk.CTkLabel(hist_card, text="Recent Runs", font=UIStyle.SUBHEADER_FONT).pack(pady=10, padx=15, anchor="w")
        
        history_frame = ctk.CTkScrollableFrame(hist_card, height=300, fg_color="transparent")
        history_frame.pack(fill="x", padx=10, pady=(0, 15))
        
        for entry in md_stats["history"][:50]: 
            result = entry.get("result", "Unknown")
            duration = entry.get("duration", 0)
            timestamp = entry.get("timestamp", 0)
            date_str = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M')
            
            mins, secs = divmod(int(duration), 60)
            duration_str = f"{mins}:{secs:02d}"
            
            run_frame = ctk.CTkFrame(history_frame, fg_color="#252525", corner_radius=6)
            run_frame.pack(fill="x", pady=4, padx=5)
            
            top_row = ctk.CTkFrame(run_frame, fg_color="transparent")
            top_row.pack(fill="x", padx=10, pady=(8, 8))
            
            result_color = "#4caf50" if result == "Win" else "#f44336"
            
            ctk.CTkLabel(top_row, text=result, font=(UIStyle.HEADER_FONT[0], 13, "bold"), text_color=result_color).pack(side="left")
            ctk.CTkLabel(top_row, text=" | ", font=UIStyle.SMALL_FONT, text_color="gray").pack(side="left")
            ctk.CTkLabel(top_row, text=f"{date_str}", font=UIStyle.SMALL_FONT, text_color="#e0e0e0").pack(side="left")
            ctk.CTkLabel(top_row, text=" | ", font=UIStyle.SMALL_FONT, text_color="gray").pack(side="left")
            ctk.CTkLabel(top_row, text=f"Time: {duration_str}", font=UIStyle.SMALL_FONT, text_color="#e0e0e0").pack(side="left")

            bottom_row = ctk.CTkFrame(run_frame, fg_color="transparent")
            bottom_row.pack(fill="x", padx=10, pady=(0, 8))
            
            floor_times = entry.get("floor_times", {})
            packs = entry.get("packs", [])

            sorted_floors = sorted(floor_times.keys(), key=lambda x: int(x.replace("floor", "")) if x.replace("floor", "").isdigit() else 99)
            
            pack_details = []
            for idx, floor_key in enumerate(sorted_floors):
                start_t = floor_times[floor_key]
                end_t = floor_times[sorted_floors[idx+1]] if idx + 1 < len(sorted_floors) else duration
                
                floor_dur = max(0, end_t - start_t)
                f_mins, f_secs = divmod(int(floor_dur), 60)
                time_str = f"{f_mins}:{f_secs:02d}"
                
                pack_name = packs[idx] if idx < len(packs) else "Unknown"
                pack_details.append(f"{pack_name} - {time_str}")
            
            packs_str = " | ".join(pack_details) if pack_details else "No pack data"
            ctk.CTkLabel(bottom_row, text=f"Packs | {packs_str}", font=(UIStyle.FONT_FAMILY, 11), text_color="#a0a0a0", anchor="w", justify="left", wraplength=500).pack(fill="x")

    def refresh():
        load_statistics_tab(parent, base_path)
        
    ctk.CTkButton(scroll_frame, text="Refresh Stats", command=refresh, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(pady=20)
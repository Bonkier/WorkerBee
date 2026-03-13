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

    if hasattr(parent, 'ui_cache') and parent.ui_cache:
        try:
            update_statistics_ui(parent.ui_cache, data)
            return
        except Exception:
            # If update fails (e.g. widgets destroyed), clear cache and rebuild
            del parent.ui_cache
    
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)
    
    ctk.CTkLabel(scroll_frame, text="Statistics", font=UIStyle.HEADER_FONT).pack(pady=(20, 10), anchor="w", padx=20)

    md_card = CardFrame(scroll_frame)
    md_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(md_card, text="Mirror Dungeon", font=UIStyle.SUBHEADER_FONT).pack(pady=10, padx=15, anchor="w")
    
    md_grid = ctk.CTkFrame(md_card, fg_color="transparent")
    md_grid.pack(pady=(0, 15), padx=20, fill="x")
    
    ui_cache = {}
    
    ui_cache['md_runs'] = ctk.CTkLabel(md_grid, text="", font=UIStyle.BODY_FONT)
    ui_cache['md_runs'].pack(side="left", expand=True)
    ui_cache['md_wins'] = ctk.CTkLabel(md_grid, text="", font=UIStyle.BODY_FONT, text_color="#4caf50")
    ui_cache['md_wins'].pack(side="left", expand=True)
    ui_cache['md_losses'] = ctk.CTkLabel(md_grid, text="", font=UIStyle.BODY_FONT, text_color="#f44336")
    ui_cache['md_losses'].pack(side="left", expand=True)
    ui_cache['md_rate'] = ctk.CTkLabel(md_grid, text="", font=UIStyle.BODY_FONT)
    ui_cache['md_rate'].pack(side="left", expand=True)

    lux_card = CardFrame(scroll_frame)
    lux_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(lux_card, text="Luxcavations", font=UIStyle.SUBHEADER_FONT).pack(pady=10, padx=15, anchor="w")
    
    lux_grid = ctk.CTkFrame(lux_card, fg_color="transparent")
    lux_grid.pack(pady=(0, 15), padx=20, fill="x")
    
    ui_cache['exp_runs'] = ctk.CTkLabel(lux_grid, text="", font=UIStyle.BODY_FONT)
    ui_cache['exp_runs'].pack(side="left", expand=True)
    ui_cache['thread_runs'] = ctk.CTkLabel(lux_grid, text="", font=UIStyle.BODY_FONT)
    ui_cache['thread_runs'].pack(side="left", expand=True)

    hist_card = CardFrame(scroll_frame)
    hist_card.pack(fill="x", padx=10, pady=10)
    ctk.CTkLabel(hist_card, text="Recent Runs", font=UIStyle.SUBHEADER_FONT).pack(pady=10, padx=15, anchor="w")
    
    history_frame = ctk.CTkScrollableFrame(hist_card, height=300, fg_color="transparent")
    history_frame.pack(fill="x", padx=10, pady=(0, 15))
    ui_cache['history_frame'] = history_frame

    def refresh():
        # Force full reload if needed, though update_statistics_ui handles data updates
        if hasattr(parent, 'ui_cache'):
            del parent.ui_cache
        load_statistics_tab(parent, base_path)
        
    ctk.CTkButton(scroll_frame, text="Refresh Stats", command=refresh, height=UIStyle.BUTTON_HEIGHT, font=UIStyle.BODY_FONT).pack(pady=20)

    try:
        update_statistics_ui(ui_cache, data)
        parent.ui_cache = ui_cache
    except Exception as e:
        ctk.CTkLabel(scroll_frame, text=f"Error loading stats: {e}", text_color="red").pack()

def update_statistics_ui(ui_cache, data):
    md_stats = data.get("mirror", {})
    runs = md_stats.get("runs", 0)
    wins = md_stats.get("wins", 0)
    losses = md_stats.get("losses", 0)
    win_rate = (wins / runs * 100) if runs > 0 else 0
    
    if not ui_cache['md_runs'].winfo_exists():
        raise RuntimeError("Widgets destroyed")

    ui_cache['md_runs'].configure(text=f"Total Runs: {runs}")
    ui_cache['md_wins'].configure(text=f"Wins: {wins}")
    ui_cache['md_losses'].configure(text=f"Losses: {losses}")
    ui_cache['md_rate'].configure(text=f"Win Rate: {win_rate:.1f}%")
    
    ui_cache['exp_runs'].configure(text=f"Exp Runs: {data.get('exp', {}).get('runs', 0)}")
    ui_cache['thread_runs'].configure(text=f"Thread Runs: {data.get('threads', {}).get('runs', 0)}")

    if "history" in md_stats and md_stats["history"]:
        history_frame = ui_cache['history_frame']
        for widget in history_frame.winfo_children():
            widget.destroy()
        
        # Limit to 10 recent runs to prevent UI lag
        for entry in md_stats["history"][:10]: 
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
            packs_by_floor = entry.get("packs_by_floor", {})

            sorted_floors = sorted(floor_times.keys(), key=lambda x: int(x.replace("floor", "")) if x.replace("floor", "").isdigit() else 99)

            pack_details = []
            for idx, floor_key in enumerate(sorted_floors):
                start_t = floor_times[floor_key]
                end_t = floor_times[sorted_floors[idx+1]] if idx + 1 < len(sorted_floors) else duration

                floor_dur = max(0, end_t - start_t)
                f_mins, f_secs = divmod(int(floor_dur), 60)
                time_str = f"{f_mins}:{f_secs:02d}"

                if floor_key in packs_by_floor:
                    pack_name = packs_by_floor[floor_key]
                else:
                    pack_name = packs[idx] if idx < len(packs) else "Unknown"
                pack_details.append(f"{pack_name} - {time_str}")
            
            packs_str = " | ".join(pack_details) if pack_details else "No pack data"
            ctk.CTkLabel(bottom_row, text=f"Packs | {packs_str}", font=(UIStyle.FONT_FAMILY, 11), text_color="#a0a0a0", anchor="w", justify="left", wraplength=500).pack(fill="x")
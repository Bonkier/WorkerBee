import customtkinter as ctk
import os
import time
import tkinter as tk
from src.gui.styles import UIStyle
from src.gui.components import CardFrame
from src.gui.utils import load_json_data

def load_dashboard_tab(parent, sidebar, callbacks, ui_context, base_path=None):
    """Load and render the Dashboard tab"""
    for widget in parent.winfo_children():
        widget.destroy()
        
    scroll_frame = ctk.CTkScrollableFrame(parent, corner_radius=0, fg_color="transparent")
    scroll_frame.pack(fill="both", expand=True)

    status_card = CardFrame(scroll_frame)
    status_card.pack(fill="x", padx=20, pady=(20, 10))
    
    status_header = ctk.CTkFrame(status_card, fg_color="transparent")
    status_header.pack(fill="x", padx=20, pady=(15, 0))
    ctk.CTkLabel(status_header, text="System Status", font=UIStyle.SUBHEADER_FONT).pack(side="left")

    status_indicator = ctk.CTkLabel(status_header, text="●", font=("Segoe UI", 16), text_color="#4caf50")
    status_indicator.pack(side="right")
    ui_context['status_indicator'] = status_indicator
    
    status_label = ctk.CTkLabel(status_card, text="Idle - Ready to start", font=UIStyle.BODY_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR)
    status_label.pack(pady=(5, 20), padx=20, anchor="w")
    ui_context['status_label'] = status_label

    if base_path:
        stats_path = os.path.join(base_path, "config", "stats.json")
        stats_data = load_json_data(stats_path)
        
        md_stats = stats_data.get("mirror", {})
        runs = md_stats.get("runs", 0)
        history = md_stats.get("history", [])

        prev_session_runs = 0
        if history:
            sessions = []
            current_session = []
            last_ts = history[0].get("timestamp", 0)
            current_session.append(history[0])
            
            for entry in history[1:]:
                ts = entry.get("timestamp", 0)
                if last_ts - ts > 1800:
                    sessions.append(current_session)
                    current_session = []
                current_session.append(entry)
                last_ts = ts
            sessions.append(current_session)

            last_run_time = history[0].get("timestamp", 0)
            if time.time() - last_run_time < 1800:
                if len(sessions) > 1:
                    prev_session_runs = len(sessions[1])
            else:
                prev_session_runs = len(sessions[0])

        stats_container = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        stats_container.pack(fill="x", padx=10, pady=10)
        
        def create_stat_card(parent, title, value, subtext=None):
            card = CardFrame(parent)
            card.pack(side="left", fill="both", expand=True, padx=10)
            
            container = ctk.CTkFrame(card, fg_color="transparent")
            container.pack(expand=True, fill="y", pady=15)
            
            ctk.CTkLabel(container, text=title, font=UIStyle.SMALL_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR).pack(anchor="center")
            ctk.CTkLabel(container, text=str(value), font=("Segoe UI", 28, "bold")).pack(anchor="center", pady=5)
            if subtext:
                ctk.CTkLabel(container, text=subtext, font=UIStyle.SMALL_FONT, text_color="gray").pack(anchor="center")
            else:
                ctk.CTkLabel(container, text=" ", font=UIStyle.SMALL_FONT).pack(anchor="center")
            return card

        create_stat_card(stats_container, "Total Runs", runs)
        create_stat_card(stats_container, "Prev. Session", prev_session_runs, "Runs completed")

        status_path = os.path.join(base_path, "config", "status_selection.json")
        status_data = load_json_data(status_path)
        selected_team = "None"
        if status_data:
            if all(key.isdigit() for key in status_data.keys()):
                sorted_items = sorted(status_data.items(), key=lambda x: int(x[0]))
                statuses = [item[1] for item in sorted_items]
                if statuses: selected_team = statuses[0].capitalize()
            else:
                statuses = status_data.get("selected_statuses", [])
                if statuses: selected_team = statuses[0].capitalize()
        
        team_card = CardFrame(scroll_frame)
        team_card.pack(fill="x", padx=20, pady=10)
        ctk.CTkLabel(team_card, text="Selected MD Team", font=UIStyle.SMALL_FONT, text_color=UIStyle.TEXT_SECONDARY_COLOR).pack(pady=(15, 0))
        ctk.CTkLabel(team_card, text=selected_team, font=("Segoe UI", 24, "bold")).pack(pady=(0, 15))

        recent_runs = history[:10]
        if recent_runs:
            durations = [r.get("duration", 0) for r in recent_runs if r.get("duration", 0) > 0]
            durations.reverse()
            
            avg_time = sum(durations) / len(durations) if durations else 0
            mins, secs = divmod(int(avg_time), 60)
            avg_time_str = f"{mins}m {secs}s"
            
            graph_card = CardFrame(scroll_frame)
            graph_card.pack(fill="x", padx=20, pady=10)
            
            header = ctk.CTkFrame(graph_card, fg_color="transparent")
            header.pack(fill="x", padx=20, pady=(15, 5))
            ctk.CTkLabel(header, text="Average Time (Last 10)", font=UIStyle.SUBHEADER_FONT).pack(side="left")
            ctk.CTkLabel(header, text=avg_time_str, font=("Segoe UI", 18, "bold"), text_color=UIStyle.ACCENT_COLOR).pack(side="right")

            canvas_height = 140
            canvas = ctk.CTkCanvas(graph_card, height=canvas_height, bg=UIStyle.CARD_COLOR, highlightthickness=0)
            canvas.pack(fill="x", padx=20, pady=(0, 15))
            
            if len(durations) > 1:
                min_d = min(durations)
                max_d = max(durations)
                range_d = max_d - min_d if max_d > min_d else 1
                
                margin_left = 50
                margin_right = 20
                margin_top = 20
                margin_bottom = 30
                
                w = 800
                h = canvas_height - margin_top - margin_bottom
                
                step = w / (len(durations) - 1)
                
                points = []
                for i, d in enumerate(durations):
                    x = margin_left + i * step
                    norm = (d - min_d) / range_d
                    y = margin_top + h - (norm * h)
                    points.append((x, y))

                canvas.create_line(margin_left, margin_top, margin_left, margin_top + h, fill="gray", width=2)
                canvas.create_line(margin_left, margin_top + h, margin_left + w, margin_top + h, fill="gray", width=2)
                
                if len(points) > 1:
                    canvas.create_line(points, fill=UIStyle.ACCENT_COLOR, width=2, smooth=True)
                    for x, y in points:
                        canvas.create_oval(x-3, y-3, x+3, y+3, fill=UIStyle.MAIN_BG_COLOR, outline=UIStyle.ACCENT_COLOR)

                min_mins, min_secs = divmod(int(min_d), 60)
                max_mins, max_secs = divmod(int(max_d), 60)
                
                canvas.create_text(margin_left - 10, margin_top + h, text=f"{min_mins}:{min_secs:02d}", fill="gray", anchor="e", font=("Segoe UI", 9))
                canvas.create_text(margin_left - 10, margin_top, text=f"{max_mins}:{max_secs:02d}", fill="gray", anchor="e", font=("Segoe UI", 9))
                
                canvas.create_text(margin_left, margin_top + h + 15, text="Oldest", fill="gray", anchor="center", font=("Segoe UI", 9))
                canvas.create_text(margin_left + w, margin_top + h + 15, text="Newest", fill="gray", anchor="center", font=("Segoe UI", 9))

    actions_card = CardFrame(scroll_frame)
    actions_card.pack(fill="x", padx=20, pady=10)
    ctk.CTkLabel(actions_card, text="Quick Actions", font=UIStyle.SUBHEADER_FONT).pack(pady=(15, 15), padx=20, anchor="w")

    actions_grid = ctk.CTkFrame(actions_card, fg_color="transparent")
    actions_grid.pack(fill="x", padx=15, pady=(0, 20))

    ctk.CTkButton(actions_grid, text="Start Mirror Dungeon", command=lambda: sidebar.show_page("Mirror Dungeon"), height=45, font=UIStyle.BODY_FONT,
                  fg_color=UIStyle.BUTTON_COLOR, hover_color=UIStyle.BUTTON_HOVER_COLOR, 
                  border_width=1, border_color=UIStyle.BUTTON_BORDER_COLOR,
                  corner_radius=UIStyle.CORNER_RADIUS).pack(side="left", expand=True, fill="x", padx=5)
    ctk.CTkButton(actions_grid, text="Start Exp Luxcavation", command=lambda: sidebar.show_page("Exp"), height=45, font=UIStyle.BODY_FONT,
                  fg_color=UIStyle.BUTTON_COLOR, hover_color=UIStyle.BUTTON_HOVER_COLOR, 
                  border_width=1, border_color=UIStyle.BUTTON_BORDER_COLOR,
                  corner_radius=UIStyle.CORNER_RADIUS).pack(side="left", expand=True, fill="x", padx=5)
    ctk.CTkButton(actions_grid, text="Start Thread Luxcavation", command=lambda: sidebar.show_page("Threads"), height=45, font=UIStyle.BODY_FONT,
                  fg_color=UIStyle.BUTTON_COLOR, hover_color=UIStyle.BUTTON_HOVER_COLOR, 
                  border_width=1, border_color=UIStyle.BUTTON_BORDER_COLOR,
                  corner_radius=UIStyle.CORNER_RADIUS).pack(side="left", expand=True, fill="x", padx=5)
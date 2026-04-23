import os
import customtkinter as ctk
import logging
from src.gui.styles import UIStyle
import src.gui.process_handler as process_handler

class UIUpdater:
    def __init__(self, root, ui_context, shared_vars, commands, base_path, sidebar):
        self.root = root
        self.ui_context = ui_context
        self.shared_vars = shared_vars
        self.commands = commands
        self.base_path = base_path
        self.sidebar = sidebar
        self.last_stats_mtime = 0

    def check_processes(self):
        """Check if processes are still running and update UI accordingly"""
        try:
            if process_handler.process is not None:
                if not process_handler.process.is_alive():
                    process_handler.process = None
                    if 'mirror_start_button' in self.ui_context and self.ui_context['mirror_start_button']:
                        self.ui_context['mirror_start_button'].configure(text="Start", command=self.commands['start_mirror'], fg_color=UIStyle.BUTTON_COLOR, hover_color=UIStyle.BUTTON_HOVER_COLOR)

            if process_handler.exp_process is not None:
                if not process_handler.exp_process.is_alive():
                    process_handler.exp_process = None
                    if 'exp_start_button' in self.ui_context and self.ui_context['exp_start_button']:
                        self.ui_context['exp_start_button'].configure(text="Start", command=self.commands['start_exp'], fg_color=UIStyle.BUTTON_COLOR, hover_color=UIStyle.BUTTON_HOVER_COLOR)

            if process_handler.threads_process is not None:
                if not process_handler.threads_process.is_alive():
                    process_handler.threads_process = None
                    if 'threads_start_button' in self.ui_context and self.ui_context['threads_start_button']:
                        self.ui_context['threads_start_button'].configure(text="Start", command=self.commands['start_threads'], fg_color=UIStyle.BUTTON_COLOR, hover_color=UIStyle.BUTTON_HOVER_COLOR)

            if process_handler.battle_process is not None:
                if process_handler.battle_process.poll() is not None:
                    process_handler.battle_process = None

            for proc in process_handler.function_process_list[:]:
                if proc.poll() is not None:
                    try:
                        process_handler.function_process_list.remove(proc)
                    except ValueError:
                        pass 
            if process_handler.function_process_list:
                if 'function_terminate_button' in self.ui_context and self.ui_context['function_terminate_button']:
                    self.ui_context['function_terminate_button'].configure(state="normal")
            else:
                if 'function_terminate_button' in self.ui_context and self.ui_context['function_terminate_button']:
                    self.ui_context['function_terminate_button'].configure(state="disabled")

            if 'status_label' in self.ui_context and self.ui_context['status_label']:
                running_process = process_handler.get_running_process_name()
                if running_process:
                    new_text = f"Running: {running_process}"
                    if self.ui_context['status_label'].cget("text") != new_text:
                        self.ui_context['status_label'].configure(text=new_text, text_color=UIStyle.ACCENT_COLOR)
                        if 'status_indicator' in self.ui_context:
                            self.ui_context['status_indicator'].configure(text_color="#ff9800") # Orange for running
                else:
                    new_text = "Idle"
                    if self.ui_context['status_label'].cget("text") != new_text:
                        self.ui_context['status_label'].configure(text=new_text, text_color=UIStyle.TEXT_SECONDARY_COLOR)
                        if 'status_indicator' in self.ui_context:
                            self.ui_context['status_indicator'].configure(text_color="#4caf50") # Green for idle

        except Exception as e:
            logging.getLogger("gui_launcher").error(f"Error in UI update loop: {e}")

        # Scheduling is now owned by _unified_tick (see bottom of class) to
        # avoid four parallel after() loops hammering the UI thread.

    def update_compact_status(self):
        """Update status label in compact mode"""
        
        if 'compact_status_label' in self.ui_context and self.ui_context['compact_status_label']:
             if self.ui_context['compact_status_label'].winfo_ismapped():
                status = process_handler.get_running_process_name() or "Idle"
                self.ui_context['compact_status_label'].configure(text=status, text_color=UIStyle.ACCENT_COLOR if status != "Idle" else UIStyle.TEXT_SECONDARY_COLOR)

                if 'compact_stop_btn' in self.ui_context and self.ui_context['compact_stop_btn']:
                    if status != "Idle":
                        if not self.ui_context['compact_stop_btn'].winfo_ismapped():
                            self.ui_context['compact_stop_btn'].pack(pady=5)
                    else:
                        if self.ui_context['compact_stop_btn'].winfo_ismapped():
                            self.ui_context['compact_stop_btn'].pack_forget()
        
        # Scheduling owned by _unified_tick.

    def check_stats_update(self):
        """Check if stats file has changed and reload stats tab"""
        if self.sidebar.current_page == "Statistics":
            try:
                stats_path = os.path.join(self.base_path, "config", "stats.json")
                if os.path.exists(stats_path):
                    current_mtime = os.path.getmtime(stats_path)
                    if current_mtime != self.last_stats_mtime:
                        self.last_stats_mtime = current_mtime
                        self.commands['load_statistics_tab']()
            except Exception as e:
                logging.getLogger("gui_launcher").warning(f"Stats update check failed: {e}")
        # Scheduling owned by _unified_tick.

    def check_chain_status(self):
        try:
            import src.gui.chain_automation as chain_automation
            chain_automation.check_chain_status(self.root, self.ui_context, self.shared_vars)
        except Exception as e:
            logging.getLogger("gui_launcher").error(f"Error in chain status check: {e}")
        # Scheduling owned by _unified_tick.

    def _unified_tick(self):
        """Run every periodic UI check from a single timer to reduce Tk
        scheduling overhead on lower-end systems. Runs every 1500ms; the
        stats check only runs every other tick (roughly 3s cadence)."""
        self._tick_count = getattr(self, '_tick_count', 0) + 1
        try:
            self.check_processes()
            self.update_compact_status()
            self.check_chain_status()
            if self._tick_count % 2 == 0:
                self.check_stats_update()
        finally:
            try:
                self.root.after(1500, self._unified_tick)
            except Exception:
                pass
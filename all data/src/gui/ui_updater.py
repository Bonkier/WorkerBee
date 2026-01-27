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
            # Check Mirror Dungeon process
            if process_handler.process is not None:
                if not process_handler.process.is_alive():
                    # Process has ended
                    process_handler.process = None
                    if 'mirror_start_button' in self.ui_context and self.ui_context['mirror_start_button']:
                        self.ui_context['mirror_start_button'].configure(text="Start", command=self.commands['start_mirror'], fg_color=UIStyle.ACCENT_COLOR, hover_color=UIStyle.HOVER_COLOR)
            
            # Check Exp process
            if process_handler.exp_process is not None:
                if not process_handler.exp_process.is_alive():
                    # Process has ended
                    process_handler.exp_process = None
                    if 'exp_start_button' in self.ui_context and self.ui_context['exp_start_button']:
                        self.ui_context['exp_start_button'].configure(text="Start", command=self.commands['start_exp'], fg_color=UIStyle.ACCENT_COLOR, hover_color=UIStyle.HOVER_COLOR)
            
            # Check Threads process
            if process_handler.threads_process is not None:
                if not process_handler.threads_process.is_alive():
                    # Process has ended
                    process_handler.threads_process = None
                    if 'threads_start_button' in self.ui_context and self.ui_context['threads_start_button']:
                        self.ui_context['threads_start_button'].configure(text="Start", command=self.commands['start_threads'], fg_color=UIStyle.ACCENT_COLOR, hover_color=UIStyle.HOVER_COLOR)
            
            # Check Battle process specifically
            if process_handler.battle_process is not None:
                if process_handler.battle_process.poll() is not None:
                    # Battle process has ended
                    process_handler.battle_process = None
            
            # Check all Function Runner processes
            for proc in process_handler.function_process_list[:]:
                if proc.poll() is not None:
                    try:
                        process_handler.function_process_list.remove(proc)
                    except ValueError:
                        pass # Already removed by cleanup thread
                    
            # Update terminate button state
            if process_handler.function_process_list:
                if 'function_terminate_button' in self.ui_context and self.ui_context['function_terminate_button']:
                    self.ui_context['function_terminate_button'].configure(state="normal")
            else:
                if 'function_terminate_button' in self.ui_context and self.ui_context['function_terminate_button']:
                    self.ui_context['function_terminate_button'].configure(state="disabled")
            
            # Update Dashboard Status
            if 'status_label' in self.ui_context and self.ui_context['status_label']:
                running_process = process_handler.get_running_process_name()
                if running_process:
                    self.ui_context['status_label'].configure(text=f"Running: {running_process}", text_color=UIStyle.ACCENT_COLOR)
                else:
                    self.ui_context['status_label'].configure(text="Idle", text_color=UIStyle.TEXT_SECONDARY_COLOR)

        except Exception as e:
            logging.getLogger("gui_launcher").error(f"Error in UI update loop: {e}")

        # Schedule next check
        self.root.after(1000, self.check_processes)

    def update_compact_status(self):
        """Update status label in compact mode"""
        # We need to access the global compact_status_label from gui_launcher
        # Since we can't easily import it, we rely on it being passed or available in ui_context if we added it there
        # But compact mode elements are created in gui_launcher.
        # For now, we'll assume the logic remains in gui_launcher or we add it to ui_context.
        # Let's add it to ui_context in gui_launcher.
        
        if 'compact_status_label' in self.ui_context and self.ui_context['compact_status_label']:
             # Check if compact mode is active (we can check if the widget is mapped)
             if self.ui_context['compact_status_label'].winfo_ismapped():
                status = process_handler.get_running_process_name() or "Idle"
                self.ui_context['compact_status_label'].configure(text=status, text_color=UIStyle.ACCENT_COLOR if status != "Idle" else UIStyle.TEXT_SECONDARY_COLOR)
                
                # Handle stop button visibility
                if 'compact_stop_btn' in self.ui_context and self.ui_context['compact_stop_btn']:
                    if status != "Idle":
                        if not self.ui_context['compact_stop_btn'].winfo_ismapped():
                            self.ui_context['compact_stop_btn'].pack(pady=5)
                    else:
                        if self.ui_context['compact_stop_btn'].winfo_ismapped():
                            self.ui_context['compact_stop_btn'].pack_forget()
        
        self.root.after(1000, self.update_compact_status)

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
            except Exception:
                pass
        self.root.after(2000, self.check_stats_update)

    def check_chain_status(self):
        import src.gui.chain_automation as chain_automation
        chain_automation.check_chain_status(self.root, self.ui_context, self.shared_vars)
        self.root.after(1000, self.check_chain_status)
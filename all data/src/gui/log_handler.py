import logging
import queue
import threading
import tkinter as tk
import common

class OptimizedLogHandler(logging.Handler):
    def __init__(self, text_widget, log_filters, module_filters, log_modules):
        super().__init__()
        self.text_widget = text_widget
        self.log_filters = log_filters
        self.module_filters = module_filters
        self.log_modules = log_modules
        self.queue = queue.Queue()
        self.running = True
        
        # Set formatter
        self.setFormatter(common.NoMillisecondsFormatter(
            fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%d/%m/%Y %H:%M:%S'
        ))
        
        self.update_thread = threading.Thread(target=self._update_widget, daemon=True)
        self.update_thread.start()

    def emit(self, record):
        if self.running:
            self.queue.put(record)

    def _update_widget(self):
        while self.running:
            try:
                record = self.queue.get(block=True, timeout=0.2)
                if self._should_show_record(record):
                    msg = self.format(record)
                    try:
                        # Use the widget's after method to schedule update on main thread
                        self.text_widget.after(0, self._append_log, msg)
                    except:
                        self.running = False
                        break
                self.queue.task_done()
            except queue.Empty:
                continue
            except Exception:
                pass

    def _should_show_record(self, record):
        level_name = record.levelname
        module_name = self._get_module_name(record.name)
        
        if level_name in self.log_filters and module_name in self.module_filters:
            show_level = self.log_filters[level_name].get()
            show_module = self.module_filters[module_name].get()
            
            if hasattr(record, 'dirty') and record.dirty and common.CLEAN_LOGS_ENABLED:
                return False
            
            return show_level and show_module
        return False

    def _get_module_name(self, logger_name):
        for module, pattern in self.log_modules.items():
            if pattern == logger_name:
                return module
        return "Other"

    def _append_log(self, msg):
        display_msg = msg.replace(" | DIRTY", "")
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", display_msg + "\n")
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

    def close(self):
        self.running = False
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            self.update_thread.join(timeout=0.1)
        super().close()
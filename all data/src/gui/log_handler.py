import logging
import queue
import threading
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
        """Batch log records and flush to the Tk widget on a throttled
        schedule. Direct after(0) per record floods the Tk event loop on
        lower-end systems; batching at ~250ms intervals keeps UI responsive.
        """
        BATCH_FLUSH_MS = 250
        MAX_BATCH = 50
        pending = []
        while self.running:
            try:
                record = self.queue.get(block=True, timeout=0.25)
                if self._should_show_record(record):
                    try:
                        pending.append(self.format(record))
                    except Exception:
                        pass
                self.queue.task_done()
            except queue.Empty:
                pass
            except Exception as e:
                logging.getLogger(__name__).warning(f"Log handler update error: {e}")

            if pending and (len(pending) >= MAX_BATCH or self.queue.empty()):
                batch = pending
                pending = []
                try:
                    self.text_widget.after(0, self._append_batch, batch)
                except Exception:
                    self.running = False
                    break

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

    def _append_batch(self, msgs):
        text = "\n".join(m.replace(" | DIRTY", "") for m in msgs) + "\n"
        try:
            self.text_widget.configure(state="normal")
            self.text_widget.insert("end", text)
            # Trim to last ~1000 lines to prevent unbounded widget growth
            line_count = int(self.text_widget.index("end-1c").split(".")[0])
            if line_count > 1000:
                self.text_widget.delete("1.0", f"{line_count - 1000}.0")
            self.text_widget.see("end")
            self.text_widget.configure(state="disabled")
        except Exception:
            pass

    def close(self):
        self.running = False
        if hasattr(self, 'update_thread') and self.update_thread.is_alive():
            self.update_thread.join(timeout=0.1)
        super().close()
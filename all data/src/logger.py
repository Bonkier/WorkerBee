import os
import time
import queue
import logging
import threading
from logging.handlers import RotatingFileHandler
from typing import Optional

_log_queue: Optional[queue.Queue] = None
_log_thread: Optional[threading.Thread] = None
_logging_enabled: bool = True
_async_enabled: bool = True

def set_logging_enabled(enabled: bool):
    global _logging_enabled
    _logging_enabled = enabled

def is_logging_enabled() -> bool:
    return _logging_enabled

def set_async_enabled(enabled: bool):
    global _async_enabled
    _async_enabled = enabled

class NoMillisecondsFormatter(logging.Formatter):
    def formatTime(self, record, datefmt=None):
        return time.strftime('%d/%m/%Y %H:%M:%S', time.localtime(record.created))

    def format(self, record):
        formatted = super().format(record)
        if hasattr(record, 'dirty') and record.dirty:
            formatted += " | DIRTY"
        return formatted

def _log_worker(log_queue: queue.Queue, log_filename: str):
    handler = RotatingFileHandler(log_filename, maxBytes=1*1024*1024, backupCount=1, encoding='utf-8')
    formatter = NoMillisecondsFormatter(
        fmt='%(asctime)s | %(name)s | %(levelname)s | %(funcName)s:%(lineno)d | %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S'
    )
    handler.setFormatter(formatter)

    worker_logger = logging.getLogger('async_log_worker')
    worker_logger.addHandler(handler)
    worker_logger.setLevel(logging.DEBUG)

    try:
        while True:
            try:
                record_data = log_queue.get(timeout=1.0)

                if record_data is None:
                    break

                level, name, msg, funcName, lineno, dirty = record_data

                record = logging.LogRecord(
                    name=name,
                    level=level,
                    pathname='',
                    lineno=lineno,
                    msg=msg,
                    args=(),
                    exc_info=None,
                    func=funcName
                )
                record.dirty = dirty

                worker_logger.handle(record)

            except queue.Empty:
                continue
            except Exception as e:
                print(f"Async logger worker error: {e}", flush=True)

    except KeyboardInterrupt:
        pass
    finally:
        handler.close()

# Keep the old name as an alias so existing code referencing _log_worker_process still works
_log_worker_process = _log_worker

def start_async_logging(log_filename: str):
    global _log_queue, _log_thread

    if _log_thread is not None:
        return

    _log_queue = queue.Queue(maxsize=1000)

    _log_thread = threading.Thread(
        target=_log_worker,
        args=(_log_queue, log_filename),
        daemon=True,
        name='AsyncLogWorker'
    )
    _log_thread.start()

def stop_async_logging():
    global _log_queue, _log_thread

    if _log_thread is not None:
        _log_queue.put(None)
        _log_thread.join(timeout=1.0)
        _log_thread = None

    _log_queue = None


def async_log(level: int, name: str, msg: str, funcName: str, lineno: int, dirty: bool = False):
    global _log_queue, _logging_enabled, _async_enabled

    if not _logging_enabled:
        return

    if not _async_enabled or _log_queue is None:
        return False

    try:
        _log_queue.put_nowait((level, name, msg, funcName, lineno, dirty))
        return True
    except queue.Full:
        return False

class AsyncDirtyLogger(logging.Logger):

    def _log_async_or_sync(self, level, msg, args, dirty=False):
        if not _logging_enabled:
            return

        import inspect
        frame = inspect.currentframe().f_back.f_back
        funcName = frame.f_code.co_name
        lineno = frame.f_lineno

        if args:
            msg = msg % args

        if async_log(level, self.name, msg, funcName, lineno, dirty):
            return

        if self.isEnabledFor(level):
            record = self.makeRecord(self.name, level, '', lineno, msg, (), None, funcName)
            record.dirty = dirty
            self.handle(record)

    def debug(self, msg, *args, dirty=False, **kwargs):
        self._log_async_or_sync(logging.DEBUG, msg, args, dirty)

    def info(self, msg, *args, dirty=False, **kwargs):
        self._log_async_or_sync(logging.INFO, msg, args, dirty)

    def warning(self, msg, *args, dirty=False, **kwargs):
        self._log_async_or_sync(logging.WARNING, msg, args, dirty)

    def error(self, msg, *args, dirty=False, **kwargs):
        self._log_async_or_sync(logging.ERROR, msg, args, dirty)

    def critical(self, msg, *args, dirty=False, **kwargs):
        self._log_async_or_sync(logging.CRITICAL, msg, args, dirty)

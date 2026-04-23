"""Consolidated path detection for packaged (Nuitka/PyInstaller) + dev runs.

Single source of truth. Used by common.py, shared_vars.py, and updater.py.
"""
import os
import sys


def is_frozen():
    """Return True if we are running inside a packaged exe."""
    if getattr(sys, 'frozen', False):
        return True
    if hasattr(sys, '_MEIPASS'):
        return True
    if '__compiled__' in globals():
        return True
    main = sys.modules.get('__main__')
    if main is not None and hasattr(main, '__compiled__'):
        return True
    exe_name = os.path.basename(sys.executable).lower()
    if exe_name and exe_name not in (
        'python.exe', 'pythonw.exe', 'py.exe', 'python3.exe', 'python'
    ):
        return True
    return False


def get_base_path():
    """Folder that contains the real user-visible exe (writable).

    For Nuitka onefile, sys.executable is a temp extraction dir, so prefer
    sys.argv[0]. We reject any path inside %TEMP%.
    """
    if is_frozen():
        candidates = []
        if sys.argv and sys.argv[0]:
            candidates.append(os.path.dirname(os.path.abspath(sys.argv[0])))
        candidates.append(os.path.dirname(sys.executable))

        temp_dir = os.environ.get('TEMP') or os.environ.get('TMP') or ''
        temp_dir = os.path.abspath(temp_dir).lower() if temp_dir else ''

        for c in candidates:
            if not c:
                continue
            if temp_dir and os.path.abspath(c).lower().startswith(temp_dir):
                continue
            return c
        return candidates[0] if candidates else os.getcwd()

    folder_path = os.path.dirname(os.path.abspath(__file__))
    if os.path.basename(folder_path) == 'src':
        return os.path.dirname(folder_path)
    return folder_path


def get_bundle_path():
    """Folder containing bundled read-only resources (pictures, themes, etc.)

    Nuitka onefile: the temp extraction dir. PyInstaller: sys._MEIPASS.
    Walks from this module's location if neither is directly usable.
    """
    if not is_frozen():
        return get_base_path()

    meipass = getattr(sys, '_MEIPASS', None)
    if meipass and os.path.isdir(meipass):
        return meipass

    base = get_base_path()

    def _has_markers(d):
        if not d or not os.path.isdir(d):
            return False
        return any(os.path.isdir(os.path.join(d, m))
                   for m in ('pictures', 'themes', 'config', 'audio'))

    try:
        cur = os.path.dirname(os.path.abspath(__file__))
        for _ in range(6):
            if cur and cur != base and _has_markers(cur):
                return cur
            parent = os.path.dirname(cur)
            if parent == cur:
                break
            cur = parent
    except (OSError, ValueError):
        pass

    temp_dir = (os.environ.get('TEMP') or os.environ.get('TMP') or '').lower()
    for p in sys.path:
        if not p:
            continue
        ap = os.path.abspath(p)
        if temp_dir and ap.lower().startswith(temp_dir) and _has_markers(ap):
            return ap

    if temp_dir:
        try:
            pid = os.getpid()
            raw_temp = os.environ.get('TEMP') or os.environ.get('TMP') or ''
            for name in os.listdir(raw_temp):
                if name.lower().startswith(f'onefile_{pid}_'):
                    cand = os.path.join(raw_temp, name)
                    if _has_markers(cand):
                        return cand
        except OSError:
            pass

    exe_dir = os.path.dirname(sys.executable)
    return exe_dir if os.path.isdir(exe_dir) else base

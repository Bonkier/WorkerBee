import sys
import os
import importlib.util

if getattr(sys, 'frozen', False):
    _meipass = sys._MEIPASS
    _src_dir = os.path.join(_meipass, 'src')

    _WORKERBEE_MODULES = {
        'mirror', 'mirror_1366', 'mirror_utils', 'mirror_utils_1366',
        'common', 'shared_vars', 'core', 'compiled_runner', 'exp_runner',
        'threads_runner', 'luxcavation_functions', 'battler', 'battlepass_collector',
        'extractor', 'function_runner', 'headless_bridge', 'audio_manager',
        'logger', 'movement_detector', 'mp_types', 'profiles', 'updater',
        'Game_Launcher', 'theme_restart', 'src',
    }

    class _LooseSourceFinder:
        def find_spec(self, fullname, path, target=None):
            root = fullname.split('.')[0]
            if root not in _WORKERBEE_MODULES:
                return None

            parts = fullname.split('.')
            rel = os.path.join(*parts)

            for base in (_src_dir, _meipass):
                pkg = os.path.join(base, rel, '__init__.py')
                if os.path.isfile(pkg):
                    return importlib.util.spec_from_file_location(
                        fullname, pkg,
                        submodule_search_locations=[os.path.join(base, rel)]
                    )
                mod = os.path.join(base, rel + '.py')
                if os.path.isfile(mod):
                    return importlib.util.spec_from_file_location(fullname, mod)

            return None

    sys.meta_path.insert(0, _LooseSourceFinder())

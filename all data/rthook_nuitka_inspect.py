"""Nuitka compatibility shim.

Nuitka-compiled modules have __file__ = None, which breaks inspect.getsourcefile
when torch tries to register custom ops. Patch inspect so None filenames are
handled gracefully.
"""
import inspect as _inspect

_orig_getsourcefile = _inspect.getsourcefile


def _patched_getsourcefile(object):
    try:
        return _orig_getsourcefile(object)
    except (AttributeError, TypeError):
        return None


_inspect.getsourcefile = _patched_getsourcefile


_orig_getabsfile = _inspect.getabsfile


def _patched_getabsfile(object, _filename=None):
    try:
        return _orig_getabsfile(object, _filename)
    except (AttributeError, TypeError):
        return None


_inspect.getabsfile = _patched_getabsfile

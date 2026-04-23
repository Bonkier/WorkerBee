"""Copy heavy deps into build_nuitka/lib/ after Nuitka build.

Packages: easyocr, torch, torchvision, skimage, scipy, rapidfuzz, and their
transitive deps that Nuitka excluded via --nofollow-import-to.
"""
import os
import shutil
import sys
import sysconfig

HERE = os.path.dirname(os.path.abspath(__file__))
DEST = os.path.join(HERE, 'build_nuitka', 'lib')

# Packages to ship externally (top-level only: easyocr's deps like numpy,
# Pillow, etc. are still bundled by Nuitka)
PACKAGES = [
    'easyocr',
    'torch',
    'torchvision',
    'torchaudio',
    'skimage',
    'scipy',
    'rapidfuzz',
    'Levenshtein',
    'sympy',       # torch transitively
    'networkx',    # torch transitively
    'imageio',     # skimage transitively
    'tifffile',    # skimage transitively
    'lazy_loader', # skimage transitively
    'pyclipper',   # easyocr
    'shapely',     # easyocr
    'ninja',       # torch
    'mpmath',      # sympy
    'filelock',    # torch
    'fsspec',      # torch
    'jinja2',      # torch
    'MarkupSafe',  # jinja2
    'markupsafe',
    'charset_normalizer',  # huggingface / transformers / easyocr util
    'PyYAML',
    'yaml',
    'bidi',        # easyocr for RTL text
    'python_bidi', # older name
]


def _site_packages_dirs():
    """Return all plausible site-packages dirs (system + user)."""
    dirs = []
    purelib = sysconfig.get_paths().get('purelib')
    if purelib and os.path.isdir(purelib):
        dirs.append(purelib)
    # User site (where pip install --user or Store Python puts things)
    try:
        import site
        user_site = site.getusersitepackages()
        if user_site and os.path.isdir(user_site):
            dirs.append(user_site)
    except Exception:
        pass
    # Windows Store Python local packages
    local_app = os.environ.get('LOCALAPPDATA', '')
    if local_app:
        for root, _, _ in os.walk(os.path.join(local_app, 'Packages')):
            if root.lower().endswith('site-packages'):
                dirs.append(root)
    for p in sys.path:
        if p.endswith('site-packages') and os.path.isdir(p) and p not in dirs:
            dirs.append(p)
    if not dirs:
        raise RuntimeError('site-packages not found')
    return dirs


def _copy(src, dst):
    if os.path.isdir(src):
        if os.path.isdir(dst):
            shutil.rmtree(dst)
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns(
            '__pycache__', '*.pyc', 'tests', 'test', 'docs', 'examples'
        ))
        return True
    return False


def _find_in_sites(name, sites):
    for s in sites:
        p = os.path.join(s, name)
        if os.path.isdir(p):
            return p
    return None


def main():
    sites = _site_packages_dirs()
    print(f'site-packages dirs: {len(sites)}')
    for s in sites:
        print(f'  - {s}')
    os.makedirs(DEST, exist_ok=True)

    copied = 0
    skipped = []
    for pkg in PACKAGES:
        src = _find_in_sites(pkg, sites)
        if src and _copy(src, os.path.join(DEST, pkg)):
            print(f'  + {pkg}   (from {os.path.dirname(src)})')
            copied += 1
        else:
            skipped.append(pkg)

    # Copy .dist-info metadata folders (some packages need these)
    for site in sites:
        try:
            for name in os.listdir(site):
                if name.endswith('.dist-info'):
                    base = name.split('-')[0].lower().replace('_', '-')
                    for pkg in PACKAGES:
                        if pkg.lower().replace('_', '-') == base:
                            _copy(os.path.join(site, name), os.path.join(DEST, name))
                            break
        except OSError:
            pass

    print(f'\nCopied {copied} packages to {DEST}')
    if skipped:
        print(f'Skipped (not found): {", ".join(skipped)}')


if __name__ == '__main__':
    main()

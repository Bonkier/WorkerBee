import os
import sys

if getattr(sys, 'frozen', False):
    torch_lib = os.path.join(sys._MEIPASS, 'torch', 'lib')
    if os.path.isdir(torch_lib):
        os.add_dll_directory(torch_lib)
        os.environ['PATH'] = torch_lib + os.pathsep + os.environ.get('PATH', '')

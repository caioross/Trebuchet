import sys
import os
from interface.ui import run_ui

if os.name == "nt": 
    import ctypes
    try:
        ctypes.windll.psapi.EmptyWorkingSet(ctypes.windll.kernel32.GetCurrentProcess())
    except:
        pass

if __name__ in {"__main__", "__mp_main__"}:
    print("TREBUCHET FRAMEWORK v4.0")
    run_ui()
from __future__ import annotations

import sys
from pathlib import Path


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_VALUE_NAME = "Damien"


def startup_command(project_root: Path) -> str:
    if getattr(sys, "frozen", False):
        return f'"{Path(sys.executable)}"'
    packaged_exe = project_root / "Damien.exe"
    if packaged_exe.exists():
        return f'"{packaged_exe}"'
    pythonw = Path(sys.executable).with_name("pythonw.exe")
    executable = pythonw if pythonw.exists() else Path(sys.executable)
    return f'"{executable}" "{project_root / "main.py"}"'


def is_launch_at_sign_in_enabled() -> bool:
    try:
        import winreg
    except ImportError:
        return False
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_READ) as key:
            winreg.QueryValueEx(key, APP_VALUE_NAME)
            return True
    except OSError:
        return False


def set_launch_at_sign_in(enabled: bool, project_root: Path) -> None:
    try:
        import winreg
    except ImportError as exc:
        raise RuntimeError("Launch at sign-in is only available on Windows.") from exc

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, APP_VALUE_NAME, 0, winreg.REG_SZ, startup_command(project_root))
        else:
            try:
                winreg.DeleteValue(key, APP_VALUE_NAME)
            except FileNotFoundError:
                pass

from __future__ import annotations

import ctypes
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from ctypes import wintypes


ERROR_ALREADY_EXISTS = 183
SW_RESTORE = 9
WAIT_OBJECT_0 = 0
INFINITE = 0xFFFFFFFF
EVENT_MODIFY_STATE = 0x0002


@dataclass
class SingleInstance:
    name: str = "DamienAssistantSingleInstance"
    restore_event_name: str = "DamienAssistantRestoreWindow"
    handle: int | None = None
    restore_event_handle: int | None = None
    already_running: bool = False

    def acquire(self) -> bool:
        if sys.platform != "win32":
            return True
        kernel32 = _kernel32()
        self.handle = kernel32.CreateMutexW(None, False, self.name)
        self.already_running = kernel32.GetLastError() == ERROR_ALREADY_EXISTS
        if self.already_running:
            signal_existing_instance(self.restore_event_name)
            focus_existing_window()
            return False
        self.restore_event_handle = kernel32.CreateEventW(None, False, False, self.restore_event_name)
        return True

    def start_restore_listener(self, callback: Callable[[], None]) -> None:
        if sys.platform != "win32" or not self.restore_event_handle:
            return

        def listen() -> None:
            kernel32 = _kernel32()
            while self.restore_event_handle:
                result = kernel32.WaitForSingleObject(self.restore_event_handle, INFINITE)
                if result == WAIT_OBJECT_0 and self.restore_event_handle:
                    callback()

        threading.Thread(target=listen, daemon=True).start()

    def release(self) -> None:
        if sys.platform != "win32":
            return
        kernel32 = _kernel32()
        if self.restore_event_handle:
            kernel32.SetEvent(self.restore_event_handle)
            kernel32.CloseHandle(self.restore_event_handle)
            self.restore_event_handle = None
        if self.handle:
            kernel32.CloseHandle(self.handle)
            self.handle = None


def signal_existing_instance(event_name: str = "DamienAssistantRestoreWindow") -> bool:
    if sys.platform != "win32":
        return False
    kernel32 = _kernel32()
    event_handle = kernel32.OpenEventW(EVENT_MODIFY_STATE, False, event_name)
    if not event_handle:
        return False
    try:
        return bool(kernel32.SetEvent(event_handle))
    finally:
        kernel32.CloseHandle(event_handle)


def _kernel32():
    kernel32 = ctypes.windll.kernel32
    kernel32.CreateMutexW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateMutexW.restype = wintypes.HANDLE
    kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.CreateEventW.restype = wintypes.HANDLE
    kernel32.OpenEventW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    kernel32.OpenEventW.restype = wintypes.HANDLE
    kernel32.SetEvent.argtypes = [wintypes.HANDLE]
    kernel32.SetEvent.restype = wintypes.BOOL
    kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel32.WaitForSingleObject.restype = wintypes.DWORD
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def focus_existing_window(title: str = "Damien") -> bool:
    if sys.platform != "win32":
        return False
    try:
        import win32con
        import win32gui
    except ImportError:
        return False

    hwnd = win32gui.FindWindow(None, title)
    if not hwnd:
        return False
    win32gui.ShowWindow(hwnd, SW_RESTORE)
    try:
        win32gui.SetForegroundWindow(hwnd)
    except Exception:
        pass
    return True

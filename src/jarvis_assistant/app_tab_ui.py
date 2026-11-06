from __future__ import annotations

from tkinter import ttk
from typing import Any


MEMORY_TAB_BUTTONS = ["Refresh", "Delete All Memory"]
BENCHMARK_TAB_BUTTONS = ["Run Quick Benchmark"]


def memory_tab_buttons() -> list[str]:
    return list(MEMORY_TAB_BUTTONS)


def benchmark_tab_buttons() -> list[str]:
    return list(BENCHMARK_TAB_BUTTONS)


class DamienMemoryTabBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, parent: ttk.Frame) -> None:
        app = self.app
        buttons = memory_tab_buttons()
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        app.memory_view = app._text_surface(parent)
        app.memory_view.grid(row=0, column=0, columnspan=2, sticky="nsew")
        ttk.Button(parent, text=buttons[0], command=app._refresh_memory).grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Button(parent, text=buttons[1], command=app._delete_memory).grid(
            row=1, column=1, sticky="e", pady=(12, 0)
        )
        app._refresh_memory()


class DamienBenchmarkTabBuilder:
    def __init__(self, app: Any) -> None:
        self.app = app

    def build(self, parent: ttk.Frame) -> None:
        app = self.app
        buttons = benchmark_tab_buttons()
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)
        app.benchmark_output = app._text_surface(parent, font=("Consolas", 10))
        app.benchmark_output.grid(row=0, column=0, sticky="nsew")
        ttk.Button(parent, text=buttons[0], command=app._run_benchmark, style="Accent.TButton").grid(
            row=1, column=0, sticky="w", pady=(12, 0)
        )

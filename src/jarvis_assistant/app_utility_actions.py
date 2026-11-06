from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox
from typing import Any

from .ai import ChatMessage
from .system_metrics import get_gpu_memory


def benchmark_prompt() -> str:
    return "Give one concise sentence explaining why local AI privacy matters."


class UtilityActionsController:
    def __init__(self, app: Any) -> None:
        self.app = app

    def speak_benchmark(self, text: str) -> None:
        app = self.app
        app.benchmark_output.configure(state="normal")
        app.benchmark_output.insert(tk.END, text + "\n")
        app.benchmark_output.configure(state="disabled")

    def run_benchmark(self) -> None:
        app = self.app
        app._speak_benchmark(f"Benchmarking {app.model_choice.get()}...")
        threading.Thread(target=app._benchmark_worker, daemon=True).start()

    def benchmark_worker(self) -> None:
        app = self.app
        started_gpu = get_gpu_memory()
        stats_line = "No stats returned."
        for event in app.ai.stream([ChatMessage("user", benchmark_prompt())]):
            if event.kind == "done" and event.stats:
                stats_line = f"{event.stats.elapsed_seconds:.1f}s, {event.stats.tokens_per_second:.1f} tok/s"
        ended_gpu = get_gpu_memory()
        app.events.put(("benchmark", f"Timing: {stats_line}\nGPU before: {started_gpu}\nGPU after: {ended_gpu}"))

    def refresh_gpu(self) -> None:
        app = self.app
        gpu = get_gpu_memory()
        app.gpu_status.set(
            f"GPU: {gpu['name']} | {gpu['used_mb']} MB used / {gpu['total_mb']} MB | {gpu['free_mb']} MB free | {gpu['utilization']}% util"
        )

    def refresh_memory(self) -> None:
        app = self.app
        memories = app.memory.list_memories()
        app.memory_view.configure(state="normal")
        app.memory_view.delete("1.0", tk.END)
        app.memory_view.insert(tk.END, "\n\n".join(item["content"] for item in memories) or "Long-term memory is empty or disabled.")
        app.memory_view.configure(state="disabled")

    def delete_memory(self) -> None:
        app = self.app
        if messagebox.askyesno("Delete memory", "Delete all inspectable long-term memory?"):
            app.memory.delete_all()
            app._refresh_memory()

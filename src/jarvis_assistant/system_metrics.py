from __future__ import annotations

import subprocess

from .local_models import recommended_model_order


def get_gpu_memory() -> dict[str, str]:
    try:
        output = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            timeout=5,
        ).strip()
    except Exception:
        return {"name": "Unavailable", "total_mb": "0", "used_mb": "0", "free_mb": "0", "utilization": "0"}
    first = output.splitlines()[0]
    name, total, used, free, util = [part.strip() for part in first.split(",")]
    return {"name": name, "total_mb": total, "used_mb": used, "free_mb": free, "utilization": util}


def get_installed_ollama_models(base_url: str = "http://127.0.0.1:11434") -> list[str]:
    del base_url
    try:
        output = subprocess.check_output(["ollama", "list"], text=True, timeout=8)
    except Exception:
        return []
    lines = output.splitlines()[1:]
    return recommended_model_order([line.split()[0] for line in lines if line.strip()])

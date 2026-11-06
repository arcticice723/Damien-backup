from __future__ import annotations

import argparse
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from jarvis_assistant.ai import ChatMessage, OllamaProvider
from jarvis_assistant.config import load_settings
from jarvis_assistant.system_metrics import get_gpu_memory


def main() -> int:
    settings = load_settings()
    parser = argparse.ArgumentParser(description="Benchmark Damien's configured Ollama model.")
    parser.add_argument("--model", default=settings.model)
    parser.add_argument("--prompt", default="Answer in one concise sentence: what makes a local assistant private?")
    args = parser.parse_args()

    provider = OllamaProvider(
        model=args.model,
        base_url=settings.ollama_base_url,
        temperature=settings.temperature,
        num_ctx=settings.num_ctx,
        thinking_mode=settings.thinking_mode,
    )

    before = get_gpu_memory()
    print(f"Model: {args.model}")
    print(f"GPU before: {before}")
    print("Response: ", end="", flush=True)
    stats = None
    for event in provider.stream([ChatMessage("user", args.prompt)]):
        if event.kind == "text":
            print(event.content, end="", flush=True)
        elif event.kind == "done":
            stats = event.stats
    print()
    after = get_gpu_memory()
    print(f"GPU after: {after}")
    if stats:
        print(f"Timing: {stats.elapsed_seconds:.2f}s elapsed, {stats.eval_count} output tokens, {stats.tokens_per_second:.2f} tok/s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

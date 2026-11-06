import sys
import traceback
from pathlib import Path


def _runtime_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _log_fatal(exc: BaseException) -> None:
    try:
        log_path = _runtime_root() / "logs" / "damien.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write("fatal_startup_error:\n")
            file.write("".join(traceback.format_exception(exc)))
            file.write("\n")
    except OSError:
        pass


def _main() -> None:
    sys.path.insert(0, str(_runtime_root() / "src"))
    from jarvis_assistant.app import main

    main()


if __name__ == "__main__":
    try:
        _main()
    except Exception as exc:
        _log_fatal(exc)
        raise

from __future__ import annotations

import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ["DAMIEN_DEBUG_STREAMING"] = "1"
sys.path.insert(0, str(ROOT / "src"))

from jarvis_assistant.app import main


if __name__ == "__main__":
    main()

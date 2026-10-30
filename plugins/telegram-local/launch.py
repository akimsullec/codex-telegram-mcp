"""Start the MCP server with the user's isolated, preinstalled runtime."""

import subprocess
import sys
from pathlib import Path

from runtime_paths import runtime_dir

ROOT = Path(__file__).resolve().parent


def main() -> int:
    python = runtime_dir() / "Scripts" / "python.exe"
    if not python.is_file():
        print(
            "Telegram Local runtime is not installed. Run install.ps1 from the "
            "repository checkout, then restart Codex.",
            file=sys.stderr,
        )
        return 1
    try:
        return subprocess.call([str(python), str(ROOT / "server.py")], cwd=ROOT)
    except OSError:
        print("Telegram Local could not start its local Python runtime.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

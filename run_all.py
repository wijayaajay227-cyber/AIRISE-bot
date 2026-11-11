"""Convenience launcher for the AIRISE Streamlit dashboard.

The Telegram bot is optional and should be run separately with its own token.
"""

import subprocess
import sys


def main() -> int:
    return subprocess.call(
        [sys.executable, "-m", "streamlit", "run", "app.py", "--server.address", "0.0.0.0"]
    )


if __name__ == "__main__":
    raise SystemExit(main())

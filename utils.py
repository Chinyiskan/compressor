# ── utils.py ──────────────────────────────────────────────────────────────────
# Generic helper functions shared across all modules.

import re
import sys
from pathlib import Path


def human_size(n: int) -> str:
    """Convert a byte count to a human-readable string (B / KB / MB / GB)."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} TB"


def resource_path(relative_path: str) -> Path:
    """Return absolute path to a bundled resource.

    Works both during normal development and inside a PyInstaller bundle
    (where files are unpacked to ``sys._MEIPASS``).
    """
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return Path(sys._MEIPASS) / relative_path
    return Path(__file__).parent / relative_path


def get_downloads_folder() -> Path:
    """Return the default output folder: ~/Downloads/Compresso."""
    return Path.home() / "Downloads" / "Compresso"


def parse_drop_paths(raw: str) -> list:
    """Robustly parse tkinterdnd2 drop data into a list of path strings.

    Handles: single paths, multiple paths, and paths with spaces wrapped
    in curly braces ``{...}`` (tkinterdnd2 convention on Windows).
    """
    paths = []
    for m in re.finditer(r"\{([^}]+)\}|([^\s{}]+)", raw):
        p = m.group(1) or m.group(2)
        if p:
            paths.append(p)
    return paths

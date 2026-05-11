# ── main.py ───────────────────────────────────────────────────────────────────
# Entry point for Compresso.
# Instantiates and launches the main application window.

from app import CompressorApp

if __name__ == "__main__":
    app = CompressorApp()
    app.mainloop()

# ── image_processor.py ────────────────────────────────────────────────────────
# All image-compression logic for Compresso.
#
# PNG engine priority:
#   1. pngquant (libimagequant) — same engine as ilovepng, ~60-70 % savings
#   2. Pillow MEDIANCUT fallback — ~30-40 % savings
#
# JPEG: progressive + chroma subsampling 4:2:0 at lower quality settings
# WebP: lossy method=6 (best encoder effort), strip metadata

import sys
import shutil
import subprocess
from pathlib import Path

from PIL import Image


# ── pngquant binary (libimagequant — same engine as ilovepng) ─────────────────
def _find_pngquant() -> str | None:
    """Return the path to the pngquant executable, or None if not found."""
    # 0. Running as a compiled PyInstaller bundle
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        bundled = Path(sys._MEIPASS) / "pngquant.exe"
        if bundled.exists():
            return str(bundled)

    # 1. On the system PATH
    found = shutil.which("pngquant")
    if found:
        return found

    # 2. pngquant-cli pip package places it next to the Python Scripts dir
    for candidate in [
        Path(sys.executable).parent / "Scripts" / "pngquant.exe",
        Path(sys.executable).parent / "pngquant.exe",
    ]:
        if candidate.exists():
            return str(candidate)

    return None


PNGQUANT_EXE = _find_pngquant()
PNGQUANT_OK  = PNGQUANT_EXE is not None


# ── Internal helpers ───────────────────────────────────────────────────────────

def _compress_png_pngquant(src: Path, out: Path, quality: int) -> bool:
    """Run pngquant (libimagequant) on *src* and write the result to *out*.

    Returns True on success.  The *quality* parameter (0-100) controls the
    ``--quality`` range passed to pngquant:

    * quality ≥ 80 → ``65-90``  (high fidelity)
    * quality ≥ 65 → ``50-85``  (balanced)
    * quality < 65 → ``30-75``  (aggressive — like iloveimg default)
    """
    if not PNGQUANT_OK:
        return False

    if quality >= 80:
        q_range = "65-90"
    elif quality >= 65:
        q_range = "50-85"
    else:
        q_range = "30-75"

    cmd = [
        PNGQUANT_EXE,
        f"--quality={q_range}",
        "--speed=1",    # slowest = best quality
        "--strip",      # remove metadata
        "--force",
        "--output", str(out),
        str(src),
    ]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        # pngquant exit codes: 0=ok, 98=quality too low (output still written), 99=skip
        return r.returncode in (0, 98) and out.exists()
    except Exception:
        return False


def _quantize_png_pillow(img: Image.Image, colors: int = 256) -> Image.Image:
    """Pillow MEDIANCUT quantizer — fallback when pngquant is unavailable.

    Less efficient than libimagequant but requires no external binary.
    """
    has_alpha = img.mode in ("RGBA", "LA") or (
        img.mode == "P" and "transparency" in img.info
    )
    if has_alpha:
        if img.mode != "RGBA":
            img = img.convert("RGBA")
        q = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=1)
        q = q.convert("RGBA")
    else:
        if img.mode != "RGB":
            img = img.convert("RGB")
        q = img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=1)
        q = q.convert("RGB")
    return q


# ── Public API ─────────────────────────────────────────────────────────────────

def compress_image(src: Path, dest_dir: Path, fmt: str, quality: int) -> dict:
    """Compress *src* into *dest_dir* using the chosen output *fmt* and *quality*.

    Returns a result dict with keys:
        name, orig, new, saved, pct, out_path, out_fmt, ok
    """
    img = Image.open(src)
    img.load()

    src_fmt = (img.format or src.suffix.lstrip(".")).upper()
    if src_fmt in ("JPG",):
        src_fmt = "JPEG"
    if src_fmt in ("TIF",):
        src_fmt = "TIFF"

    # ── Decide output format ──────────────────────────────────────────────────
    out_fmt = src_fmt if fmt == "Mantener original" else fmt

    ext_map = {
        "JPEG": ".jpg",  "PNG":  ".png",
        "WEBP": ".webp", "WebP": ".webp",
        "BMP":  ".bmp",  "TIFF": ".tiff",
    }
    out_ext  = ext_map.get(out_fmt, src.suffix.lower())
    out_path = dest_dir / (src.stem + out_ext)

    # ── PNG: pngquant first, Pillow fallback ──────────────────────────────────
    if out_fmt == "PNG":
        pq_ok = _compress_png_pngquant(src, out_path, quality)
        if not pq_ok:
            n_colors = 256 if quality >= 72 else 64
            try:
                quantized = _quantize_png_pillow(img, colors=n_colors)
                quantized.save(out_path, format="PNG", optimize=True, compress_level=9)
            except Exception:
                img.save(out_path, format="PNG", optimize=True, compress_level=9)

    # ── WebP ──────────────────────────────────────────────────────────────────
    elif out_fmt in ("WebP", "WEBP"):
        img.save(out_path, format="WebP", quality=quality, method=6, lossless=False)

    # ── JPEG ──────────────────────────────────────────────────────────────────
    elif out_fmt == "JPEG":
        # Flatten alpha channel onto a white background before saving
        if img.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            if img.mode in ("RGBA", "LA"):
                bg.paste(img, mask=img.split()[-1])
            else:
                bg.paste(img)
            img = bg
        elif img.mode != "RGB":
            img = img.convert("RGB")
        subsampling = 0 if quality >= 80 else 2  # 4:4:4 vs 4:2:0
        img.save(
            out_path, format="JPEG", quality=quality,
            optimize=True, progressive=True, subsampling=subsampling,
        )

    # ── TIFF ──────────────────────────────────────────────────────────────────
    elif out_fmt in ("TIFF", "TIF"):
        img.save(out_path, format="TIFF", compression="tiff_lzw")

    # ── BMP / other ───────────────────────────────────────────────────────────
    elif out_fmt == "BMP":
        img.save(out_path, format="BMP")
    else:
        img.save(out_path)

    orig  = src.stat().st_size
    new   = out_path.stat().st_size
    saved = orig - new
    return {
        "name":     src.name,
        "orig":     orig,
        "new":      new,
        "saved":    saved,
        "pct":      (saved / orig * 100) if orig else 0,
        "out_path": out_path,
        "out_fmt":  out_fmt,
        "ok":       True,
    }

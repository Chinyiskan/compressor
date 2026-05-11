# ── pdf_processor.py ──────────────────────────────────────────────────────────
# Converts PDF files into individual WebP images (one per page),
# optimised for manga/comic reading on mobile browsers.
#
# Compression philosophy:
#   Manga pages are ~90% near-grayscale (scanned B&W ink on paper).
#   A smart dual-path pipeline detects this and applies different settings:
#
#   ┌─────────────┬──────────────┬──────────┬─────────────────────────────────┐
#   │  Page type  │  Max dim     │ Quality  │  Extra                          │
#   ├─────────────┼──────────────┼──────────┼─────────────────────────────────┤
#   │  B&W manga  │  1000 px     │   55     │  Grayscale (L mode) + sharpen   │
#   │  Color page │  1200 px     │   72     │  RGB, no sharpen                │
#   └─────────────┴──────────────┴──────────┴─────────────────────────────────┘
#
#   This typically yields 75-85 % size reduction vs the source PDF while keeping
#   manga text and lineart crisp on mobile screens (360-430 px CSS width).
#
# Extraction strategy (per page):
#   1. Direct xref extraction — fastest; preserves native resolution.
#   2. Page render fallback — used for vector pages or corrupt xrefs.
#
# Root-cause note on "shared resource" PDFs (pdfcoffee, etc.):
#   page.get_images() lists ALL images on EVERY page because the PDF stores
#   images in a document-level resource dict.  We deduplicate by xref and sort
#   ascending (xref allocation order == insertion/page order).

import io
import fitz                          # PyMuPDF
from PIL import Image, ImageChops, ImageStat, ImageFilter
from pathlib import Path

from config import (
    PDF_QUALITY_BW,     # WebP quality for B&W/manga pages
    PDF_QUALITY_COLOR,  # WebP quality for color pages
    PDF_MAX_DIM_BW,     # longest-side cap for B&W pages (px)
    PDF_MAX_DIM_COLOR,  # longest-side cap for color pages (px)
    PDF_GRAY_THRESHOLD, # mean channel diff below which page is "near-gray"
    PDF_RENDER_DPI,     # fallback render DPI
)


# ── Internal helpers ──────────────────────────────────────────────────────────

def _is_near_grayscale(img: Image.Image) -> bool:
    """Return True when the image is effectively B&W / grayscale.

    Scanned manga always has a tiny amount of colour noise introduced by the
    scanner, so a byte-exact channel comparison never triggers.  Instead we
    compute the mean absolute difference between the R-G and R-B channel pairs
    and compare against PDF_GRAY_THRESHOLD (default 18/255).  A value of 18
    passes real manga scans while correctly keeping colour pages as RGB.
    """
    if img.mode == "L":
        return True
    if img.mode != "RGB":
        return False
    r, g, b = img.split()
    diff_rg = ImageStat.Stat(ImageChops.difference(r, g)).mean[0]
    diff_rb = ImageStat.Stat(ImageChops.difference(r, b)).mean[0]
    return max(diff_rg, diff_rb) < PDF_GRAY_THRESHOLD


def _normalise_mode(img: Image.Image, keep_gray: bool) -> Image.Image:
    """Flatten alpha, convert palette/CMYK, and optionally convert to grayscale.

    Args:
        img:       Source image.
        keep_gray: If True, collapse to L mode when the image is near-grayscale.
    """
    # 1. Handle unusual modes first
    if img.mode == "CMYK":
        img = img.convert("RGB")
    if img.mode == "P":
        img = img.convert("RGBA")   # expands palette + transparency

    # 2. Flatten alpha onto white
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.split()[3])
        img = bg
    elif img.mode == "LA":
        bg = Image.new("L", img.size, 255)
        bg.paste(img, mask=img.split()[1])
        img = bg

    # 3. Grayscale conversion (saves ~30-40 % on top of other savings)
    if keep_gray and _is_near_grayscale(img):
        if img.mode != "L":
            img = img.convert("L")

    return img


def _cap_size(img: Image.Image, max_dim: int) -> Image.Image:
    """Downscale so the longest side <= max_dim.  Never upscale."""
    w, h = img.size
    longest = max(w, h)
    if longest > max_dim:
        scale = max_dim / longest
        return img.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS,
        )
    return img


def _sharpen_manga(img: Image.Image) -> Image.Image:
    """Apply a mild unsharp-mask pass to recover line crispness after
    downscaling.  Only applied to grayscale manga pages; has negligible
    effect on file size but noticeably improves perceived sharpness."""
    return img.filter(ImageFilter.UnsharpMask(radius=0.6, percent=130, threshold=3))


def _compress_and_save(img: Image.Image, out_path: Path) -> int:
    """Detect page type, apply the matching compression pipeline, and save.

    Pipeline:
        normalise → cap size → (sharpen if BW) → save WebP

    Returns the output file size in bytes.
    """
    is_bw = _is_near_grayscale(img)

    quality = PDF_QUALITY_BW    if is_bw else PDF_QUALITY_COLOR
    max_dim = PDF_MAX_DIM_BW    if is_bw else PDF_MAX_DIM_COLOR

    img = _normalise_mode(img, keep_gray=is_bw)
    img = _cap_size(img, max_dim)

    if is_bw and img.mode == "L":
        img = _sharpen_manga(img)

    img.save(
        out_path,
        format      = "WebP",
        quality     = quality,
        method      = 6,       # max encoder effort
        lossless    = False,
        exif        = b"",     # strip EXIF
        icc_profile = b"",     # strip ICC profile
    )
    return out_path.stat().st_size


def _render_page(doc: fitz.Document, page_idx: int) -> Image.Image:
    """Rasterise a PDF page and return a Pillow Image.
    Zoom is capped so the longest side never exceeds the colour-page limit."""
    page      = doc.load_page(page_idx)
    rect      = page.rect
    zoom_dpi  = PDF_RENDER_DPI / 72.0
    zoom_cap  = PDF_MAX_DIM_COLOR / max(rect.width, rect.height)
    zoom      = min(zoom_dpi, zoom_cap)
    pix  = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    mode = "L" if pix.n == 1 else "RGB"
    return Image.frombytes(mode, [pix.width, pix.height], pix.samples)


def _collect_unique_xrefs(doc: fitz.Document) -> list:
    """Return all unique image xrefs found anywhere in the document,
    sorted ascending (allocation order ≈ page/insertion order)."""
    seen: set  = set()
    xrefs: list = []
    for page_num in range(len(doc)):
        page = doc.load_page(page_num)
        for img_ref in page.get_images(full=True):
            xref = img_ref[0]
            if xref not in seen:
                seen.add(xref)
                xrefs.append(xref)
    return sorted(xrefs)


# ── Public API ────────────────────────────────────────────────────────────────

def compress_pdf(src: Path, dest_dir: Path, progress_cb=None) -> dict:
    """Extract every page of *src* as an optimised WebP into dest_dir/<stem>/.

    The pipeline automatically detects near-grayscale (manga/comic) pages and
    applies aggressive compression suitable for mobile browser reading, while
    keeping colour pages (covers, illustrations) at higher quality.

    Args:
        src:         Path to the source PDF.
        dest_dir:    Root output directory.  A sub-folder named after the PDF
                     stem is created automatically.
        progress_cb: Optional callable(float) receiving values in [0, 1].

    Returns:
        Result dict with keys: name, orig, new, saved, pct, out_path, out_fmt, ok.
    """
    out_dir = dest_dir / src.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        doc = fitz.open(str(src))
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF: {e}")

    total_pages = len(doc)
    if total_pages == 0:
        raise ValueError("El PDF está vacío.")

    orig_size = src.stat().st_size
    new_size  = 0

    all_xrefs  = _collect_unique_xrefs(doc)
    has_shared = (len(all_xrefs) == total_pages and total_pages > 1)
    pad        = max(3, len(str(total_pages)))

    if has_shared:
        # ── Shared-resource PDF (e.g. pdfcoffee) ─────────────────────────────
        # Each xref corresponds to exactly one page in document order.
        items       = list(enumerate(all_xrefs))
        total_items = len(items)

        for order_idx, xref in items:
            out_path = out_dir / f"{str(order_idx + 1).zfill(pad)}.webp"

            try:
                raw = doc.extract_image(xref)
                img = Image.open(io.BytesIO(raw["image"]))
                img.load()
            except Exception:
                img = _render_page(doc, order_idx)

            new_size += _compress_and_save(img, out_path)

            if progress_cb:
                progress_cb((order_idx + 1) / total_items)

    else:
        # ── Standard PDF: one image (or vector content) per page ──────────────
        for i in range(total_pages):
            page     = doc.load_page(i)
            out_path = out_dir / f"{str(i + 1).zfill(pad)}.webp"
            img      = None

            page_imgs = page.get_images(full=True)
            if len(page_imgs) == 1:
                try:
                    raw = doc.extract_image(page_imgs[0][0])
                    img = Image.open(io.BytesIO(raw["image"]))
                    img.load()
                except Exception:
                    img = None

            if img is None:
                img = _render_page(doc, i)

            new_size += _compress_and_save(img, out_path)

            if progress_cb:
                progress_cb((i + 1) / total_pages)

    doc.close()

    saved = orig_size - new_size
    return {
        "name":     src.name,
        "orig":     orig_size,
        "new":      new_size,
        "saved":    saved,
        "pct":      (saved / orig_size * 100) if orig_size else 0,
        "out_path": out_dir,
        "out_fmt":  "WEBP",
        "ok":       True,
    }

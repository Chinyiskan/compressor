# ── config.py ─────────────────────────────────────────────────────────────────
# Centralized constants for Compresso.
# All UI colours, format lists, quality defaults and extension sets live here
# so that every other module can import from a single source of truth.

import customtkinter as ctk

# ── Appearance ─────────────────────────────────────────────────────────────────
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

# ── Colour palette ─────────────────────────────────────────────────────────────
BG_BASE     = "#0D1117"
BG_SURFACE  = "#161B22"
BG_ELEVATED = "#1C2333"
BG_INPUT    = "#21262D"
ACCENT      = "#58A6FF"
ACCENT2     = "#A371F7"   # purple accent for video mode
ACCENT3     = "#E11D48"   # crimson red accent for PDF mode
ACCENT_DARK = "#3B82F6"
SUCCESS     = "#3FB950"
WARNING     = "#D29922"
DANGER      = "#F85149"
TEXT_PRI    = "#E6EDF3"
TEXT_SEC    = "#8B949E"
TEXT_DIM    = "#484F58"
BORDER      = "#30363D"

# ── Format lists ───────────────────────────────────────────────────────────────
IMG_FORMATS = ["Mantener original", "JPEG", "PNG", "WebP"]

VID_FORMATS = ["Mantener original", "MP4  (H.265 / HEVC)", "MP4  (H.264)", "WebM  (VP9)"]
PDF_FORMATS = ["Extraer como WebP"]
VID_QUALITY = {
    "Alta calidad  (CRF 20)":    20,
    "Balanceado  (CRF 26)":      26,
    "Máx. compresión  (CRF 32)": 32,
}

# ── Fixed auto-quality ─────────────────────────────────────────────────────────
# Same philosophy as ilovepng/iloveimg: squeeze as much as possible while
# keeping the result visually indistinguishable from the original.
IMG_QUALITY_AUTO = 78   # JPEG / WebP Pillow scale (0-95)
VID_QUALITY_AUTO = 30   # FFmpeg CRF (lower = larger file)

# ── PDF → WebP manga pipeline ──────────────────────────────────────────────────
# Dual-path: B&W manga pages get aggressive compression; colour pages (covers,
# illustrations) are kept at higher quality so they still look great.
#
# Target: 75-85 % size reduction vs source PDF, optimised for mobile browsers.
#   B&W path  → grayscale L mode + Q45 + 800 px cap + unsharp-mask sharpening
#   Color path → RGB          + Q72 + 1200 px cap
#
# Sizing rationale:
#   Mobile screens are 360-430 px CSS wide. At 2× device pixel ratio (most
#   mid-range phones), a 800 px wide image fills the screen perfectly. Going
#   higher wastes bandwidth with zero perceptual benefit at reading scale.
#
# PDF_GRAY_THRESHOLD: mean per-channel difference (0-255) below which an RGB
#   image is treated as "near-grayscale".  12 avoids false-positive on soft
#   pastel-colour pages (covers) while catching all genuine B&W scans.
PDF_QUALITY_BW     = 45    # WebP quality for B&W / manga pages
PDF_QUALITY_COLOR  = 72    # WebP quality for colour pages (covers, art)
PDF_MAX_DIM_BW     = 800   # longest-side cap for B&W pages (px)
PDF_MAX_DIM_COLOR  = 1200  # longest-side cap for colour pages (px)
PDF_GRAY_THRESHOLD = 12    # near-grayscale detection threshold (0-255)
PDF_RENDER_DPI     = 150   # DPI used when rasterising vector/fallback pages

# ── Supported extensions ───────────────────────────────────────────────────────
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tiff", ".tif"}
VID_EXT = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
PDF_EXT = {".pdf"}

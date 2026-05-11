# ── video_processor.py ────────────────────────────────────────────────────────
# All video-compression logic for Compresso.
#
# Requires: imageio-ffmpeg  (pip install imageio-ffmpeg)
# Codec support: H.264 (libx264), H.265/HEVC (libx265), VP9 (libvpx-vp9)
# Progress: real-time via FFmpeg's  -progress pipe:1  output.

import json
import subprocess
from pathlib import Path


# ── FFmpeg discovery ───────────────────────────────────────────────────────────
try:
    import imageio_ffmpeg

    FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
    FFMPEG_OK  = True
except Exception:
    FFMPEG_EXE = None
    FFMPEG_OK  = False


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_video_duration(src: Path) -> float:
    """Return the duration of *src* in seconds using the ffprobe bundled with
    imageio-ffmpeg.  Returns 0.0 if FFmpeg is unavailable or probing fails.
    """
    if not FFMPEG_OK:
        return 0.0

    # Some imageio-ffmpeg builds do not ship a separate ffprobe binary
    ffprobe = FFMPEG_EXE.replace("ffmpeg", "ffprobe")
    if not Path(ffprobe).exists():
        ffprobe = FFMPEG_EXE  # fall back to ffmpeg -i

    try:
        result = subprocess.run(
            [
                FFMPEG_EXE,
                "-v",           "quiet",
                "-print_format", "json",
                "-show_format",
                "-i",           str(src),
            ],
            capture_output=True,
            text=True,
            timeout=15,
        )
        info = json.loads(result.stdout)
        return float(info["format"].get("duration", 0))
    except Exception:
        return 0.0


# ── Public API ─────────────────────────────────────────────────────────────────

def compress_video(
    src: Path,
    dest_dir: Path,
    fmt: str,
    crf: int,
    progress_cb=None,
) -> dict:
    """Compress *src* into *dest_dir* using FFmpeg.

    Parameters
    ----------
    src:
        Path to the source video file.
    dest_dir:
        Directory where the compressed file will be written.
    fmt:
        Format string from ``VID_FORMATS`` (e.g. ``"MP4  (H.264)"``).
    crf:
        Constant-Rate-Factor base value.  The actual value passed to FFmpeg
        may be offset per codec to compensate for encoder differences.
    progress_cb:
        Optional callable ``(float)`` receiving a value in ``[0, 1]``
        representing the overall encode progress.

    Returns
    -------
    dict
        Result dict with keys: name, orig, new, saved, pct, out_path, out_fmt, ok
    """
    if not FFMPEG_OK:
        raise RuntimeError("FFmpeg no disponible. Instala imageio-ffmpeg.")

    raw_fmt = fmt.split("  ")[0]  # strip trailing whitespace + codec label

    # ── Determine output container + codec ────────────────────────────────────
    if raw_fmt == "Mantener original":
        suf = src.suffix.lower()
        if suf == ".webm":
            out_ext, vcodec = ".webm", "libvpx-vp9"
        else:
            out_ext, vcodec = ".mp4", "libx264"
    elif "H.265" in fmt:
        out_ext, vcodec = ".mp4",  "libx265"
    elif "WebM" in fmt:
        out_ext, vcodec = ".webm", "libvpx-vp9"
    else:
        out_ext, vcodec = ".mp4",  "libx264"

    out_path = dest_dir / (src.stem + "_c" + out_ext)
    duration = get_video_duration(src)

    # Bounding-box scale: cap at 1280 px on the longest side (≈ 720 p)
    vf_scale = "scale='trunc(iw*min(1,min(1280/iw,1280/ih))/2)*2':-2"

    # ── Build FFmpeg command ──────────────────────────────────────────────────
    if vcodec == "libx265":
        cmd = [
            FFMPEG_EXE, "-y", "-i", str(src),
            "-vcodec", "libx265",
            "-crf",    str(crf + 2),
            "-preset", "slow",
            "-vf",     vf_scale,
            "-acodec", "aac", "-b:a", "64k",
            "-tag:v",  "hvc1",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(out_path),
        ]
    elif vcodec == "libx264":
        cmd = [
            FFMPEG_EXE, "-y", "-i", str(src),
            "-vcodec", "libx264",
            "-crf",    str(crf + 2),
            "-preset", "slower",
            "-vf",     vf_scale,
            "-acodec", "aac", "-b:a", "64k",
            "-movflags", "+faststart",
            "-progress", "pipe:1", "-nostats", str(out_path),
        ]
    else:  # VP9
        cmd = [
            FFMPEG_EXE, "-y", "-i", str(src),
            "-vcodec", "libvpx-vp9",
            "-crf",    str(crf + 5),
            "-b:v",    "0",
            "-vf",     vf_scale,
            "-acodec", "libopus", "-b:a", "48k",
            "-progress", "pipe:1", "-nostats", str(out_path),
        ]

    # ── Run FFmpeg and stream progress ────────────────────────────────────────
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    for line in proc.stdout:
        line = line.strip()
        if line.startswith("out_time_ms=") and duration > 0 and progress_cb:
            try:
                ms = int(line.split("=")[1])
                progress_cb(min(ms / (duration * 1_000_000), 1.0))
            except ValueError:
                pass

    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"FFmpeg terminó con código {proc.returncode}")

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
        "out_fmt":  out_ext.lstrip(".").upper(),
        "ok":       True,
    }

import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from pathlib import Path
import customtkinter as ctk

from config import *
from utils import resource_path, parse_drop_paths, human_size, get_downloads_folder
from image_processor import compress_image
from video_processor import compress_video, FFMPEG_OK
from pdf_processor import compress_pdf

class CompressorApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("Compresso")
        self.geometry("960x720")
        self.minsize(820, 640)
        self.configure(bg=BG_BASE)

        try:
            icon_path = resource_path("favicon.ico")
            if icon_path.exists():
                self.iconbitmap(str(icon_path))
        except Exception:
            pass

        self._mode = "image"  # "image" | "video"
        self.queued_files: list = []
        self.results: list = []
        self._processing = False
        self._row_labels: dict = {}  # path → status Label widget

        self._build_ui()
        self._center_window()

    def _center_window(self):
        self.update_idletasks()
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        ww, wh = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{(sw - ww) // 2}+{(sh - wh) // 2}")

    def _build_ui(self):
        # ══ Header ══════════════════════════════════════════════════════════
        header = tk.Frame(self, bg=BG_BASE)
        header.pack(fill="x", padx=32, pady=(28, 0))

        # Logo group
        logo_grp = tk.Frame(header, bg=BG_BASE)
        logo_grp.pack(side="left")

        tk.Label(
            logo_grp, text="⚡", bg=BG_BASE, fg=ACCENT, font=("Segoe UI", 22, "bold")
        ).pack(side="left")
        tk.Label(
            logo_grp,
            text=" Compresso",
            bg=BG_BASE,
            fg=TEXT_PRI,
            font=("Segoe UI", 22, "bold"),
        ).pack(side="left")
        tk.Label(
            logo_grp,
            text="  ·  Comprime sin perder calidad",
            bg=BG_BASE,
            fg=TEXT_DIM,
            font=("Segoe UI", 10),
        ).pack(side="left", pady=(4, 0))

        # ── Mode toggle (pill) ──
        toggle_frame = tk.Frame(
            header, bg=BG_SURFACE, highlightbackground=BORDER, highlightthickness=1
        )
        toggle_frame.pack(side="right")

        self._img_tab_btn = tk.Label(
            toggle_frame,
            text="🖼  Imágenes",
            bg=ACCENT,
            fg="white",
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
        )
        self._img_tab_btn.pack(side="left")
        self._img_tab_btn.bind("<Button-1>", lambda e: self._switch_mode("image"))

        self._vid_tab_btn = tk.Label(
            toggle_frame,
            text="🎬  Videos",
            bg=BG_SURFACE,
            fg=TEXT_SEC,
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
        )
        self._vid_tab_btn.pack(side="left")
        self._vid_tab_btn.bind("<Button-1>", lambda e: self._switch_mode("video"))

        self._pdf_tab_btn = tk.Label(
            toggle_frame,
            text="📄  PDFs",
            bg=BG_SURFACE,
            fg=TEXT_SEC,
            font=("Segoe UI", 10, "bold"),
            padx=16,
            pady=7,
            cursor="hand2",
        )
        self._pdf_tab_btn.pack(side="left")
        self._pdf_tab_btn.bind("<Button-1>", lambda e: self._switch_mode("pdf"))

        # ══ Drop Zone ════════════════════════════════════════════════════════
        dz_wrap = tk.Frame(self, bg=BG_BASE)
        dz_wrap.pack(fill="x", padx=32, pady=(22, 0))

        self.drop_zone = tk.Frame(
            dz_wrap,
            bg=BG_SURFACE,
            highlightbackground=ACCENT,
            highlightthickness=2,
            relief="flat",
            cursor="hand2",
        )
        self.drop_zone.pack(fill="x")
        self.drop_zone.pack_propagate(False)
        self.drop_zone.configure(height=172)

        # Inner frame to give a subtle inset look
        dz_inner = tk.Frame(self.drop_zone, bg=BG_SURFACE)
        dz_inner.place(relx=0.5, rely=0.5, anchor="center")

        self._dz_icon = tk.Label(
            dz_inner, text="🖼️", bg=BG_SURFACE, font=("Segoe UI", 38)
        )
        self._dz_icon.pack()
        self._dz_title = tk.Label(
            dz_inner,
            text="Arrastra tus imágenes aquí",
            bg=BG_SURFACE,
            fg=TEXT_PRI,
            font=("Segoe UI", 14, "bold"),
        )
        self._dz_title.pack()
        tk.Label(
            dz_inner,
            text="o haz clic para seleccionar archivos",
            bg=BG_SURFACE,
            fg=TEXT_SEC,
            font=("Segoe UI", 10),
        ).pack()
        self._dz_hint = tk.Label(
            dz_inner,
            text="JPEG · PNG · WebP · BMP · TIFF",
            bg=BG_SURFACE,
            fg=TEXT_DIM,
            font=("Segoe UI", 8),
        )
        self._dz_hint.pack(pady=(3, 0))

        # DnD & click binding
        self.drop_zone.drop_target_register(DND_FILES)
        self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)
        for w in [self.drop_zone, dz_inner] + list(dz_inner.winfo_children()):
            w.bind("<Button-1>", lambda e: self._browse_files())

        # Hover glow
        def _get_glow_color():
            if self._mode == "image": return "#78BBFF"
            if self._mode == "pdf": return "#FB7185"
            return "#C084FC"
            
        def _get_accent_color():
            if self._mode == "image": return ACCENT
            if self._mode == "pdf": return ACCENT3
            return ACCENT2

        self.drop_zone.bind(
            "<Enter>",
            lambda e: (
                self.drop_zone.configure(highlightbackground=_get_glow_color()),
                dz_inner.configure(bg=BG_ELEVATED),
            ),
        )
        self.drop_zone.bind(
            "<Leave>",
            lambda e: (
                self.drop_zone.configure(highlightbackground=_get_accent_color()),
                dz_inner.configure(bg=BG_SURFACE),
            ),
        )

        # ══ Options row ════════════════════════════════════════════════════
        self.opts_frame = tk.Frame(self, bg=BG_BASE)
        self.opts_frame.pack(fill="x", padx=32, pady=(14, 0))

        # — Format card —
        fmt_card = tk.Frame(
            self.opts_frame,
            bg=BG_SURFACE,
            highlightbackground=BORDER,
            highlightthickness=1,
            padx=14,
            pady=11,
        )
        fmt_card.pack(side="left", fill="both", expand=True, padx=(0, 8))

        tk.Label(
            fmt_card,
            text="FORMATO DESTINO",
            bg=BG_SURFACE,
            fg=TEXT_DIM,
            font=("Segoe UI", 8, "bold"),
        ).pack(anchor="w")

        self.fmt_var = tk.StringVar(value=IMG_FORMATS[0])
        self.fmt_menu = ctk.CTkOptionMenu(
            fmt_card,
            values=IMG_FORMATS,
            variable=self.fmt_var,
            fg_color=BG_INPUT,
            button_color=ACCENT,
            button_hover_color=ACCENT_DARK,
            dropdown_fg_color=BG_ELEVATED,
            font=ctk.CTkFont("Segoe UI", 12),
            width=210,
        )
        self.fmt_menu.pack(anchor="w", pady=(6, 0))

        # — Compress button —
        btn_card = tk.Frame(self.opts_frame, bg=BG_BASE)
        btn_card.pack(side="left", fill="both", expand=True)

        self.compress_btn = ctk.CTkButton(
            btn_card,
            text="⚡  Comprimir",
            command=self._start_compression,
            fg_color=ACCENT,
            hover_color=ACCENT_DARK,
            font=ctk.CTkFont("Segoe UI", 13, "bold"),
            height=48,
            corner_radius=8,
        )
        self.compress_btn.pack(fill="x", pady=(10, 0))

        # ══ Queue header ════════════════════════════════════════════════════
        q_hdr = tk.Frame(self, bg=BG_BASE)
        q_hdr.pack(fill="x", padx=32, pady=(20, 0))

        self.queue_label = tk.Label(
            q_hdr,
            text="Cola  (0)",
            bg=BG_BASE,
            fg=TEXT_PRI,
            font=("Segoe UI", 11, "bold"),
        )
        self.queue_label.pack(side="left")

        self._clear_lbl = tk.Label(
            q_hdr,
            text="Limpiar todo",
            bg=BG_BASE,
            fg=TEXT_SEC,
            font=("Segoe UI", 9),
            cursor="hand2",
        )
        self._clear_lbl.pack(side="right")
        self._clear_lbl.bind("<Enter>", lambda e: self._clear_lbl.configure(fg=ACCENT))
        self._clear_lbl.bind(
            "<Leave>", lambda e: self._clear_lbl.configure(fg=TEXT_SEC)
        )
        self._clear_lbl.bind("<Button-1>", lambda e: self._clear_queue())

        # ══ Queue list ══════════════════════════════════════════════════════
        q_wrap = tk.Frame(self, bg=BG_BASE)
        q_wrap.pack(fill="both", expand=True, padx=32, pady=(6, 0))

        self.canvas = tk.Canvas(q_wrap, bg=BG_SURFACE, highlightthickness=0, bd=0)
        self._vsb = tk.Scrollbar(q_wrap, orient="vertical", command=self.canvas.yview)
        self.inner_list = tk.Frame(self.canvas, bg=BG_SURFACE)

        self.inner_list.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.inner_list, anchor="nw")
        self.canvas.configure(yscrollcommand=self._vsb.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        self._vsb.pack(side="right", fill="y")

        # Mousewheel scroll
        self.canvas.bind(
            "<Enter>",
            lambda e: self.canvas.bind_all(
                "<MouseWheel>",
                lambda ev: self.canvas.yview_scroll(-1 * (ev.delta // 120), "units"),
            ),
        )
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

        # Empty state
        self.empty_label = tk.Label(
            self.inner_list,
            text="Arrastra archivos a la zona de arriba para comenzar.",
            bg=BG_SURFACE,
            fg=TEXT_DIM,
            font=("Segoe UI", 10),
            justify="center",
        )
        self.empty_label.pack(expand=True, pady=36)

        # ══ Status bar ══════════════════════════════════════════════════════
        sb = tk.Frame(self, bg=BG_ELEVATED, height=32)
        sb.pack(fill="x", side="bottom")
        sb.pack_propagate(False)

        self.progress_bar = ctk.CTkProgressBar(
            sb, fg_color=BG_INPUT, progress_color=ACCENT, height=3
        )
        self.progress_bar.pack(fill="x", side="top")
        self.progress_bar.set(0)

        self.status_var = tk.StringVar(value="Listo para comprimir.")
        tk.Label(
            sb,
            textvariable=self.status_var,
            bg=BG_ELEVATED,
            fg=TEXT_SEC,
            font=("Segoe UI", 9),
        ).pack(side="left", padx=14, pady=(2, 0))

    def _switch_mode(self, mode: str):
        if mode == self._mode:
            return
        self._mode = mode
        is_img = mode == "image"
        is_pdf = mode == "pdf"
        
        if is_img:
            acc = ACCENT
        elif is_pdf:
            acc = ACCENT3
        else:
            acc = ACCENT2

        # Toggle button styling
        self._img_tab_btn.configure(
            bg=ACCENT if is_img else BG_SURFACE, fg="white" if is_img else TEXT_SEC
        )
        self._vid_tab_btn.configure(
            bg=ACCENT2 if (mode == "video") else BG_SURFACE,
            fg="white" if (mode == "video") else TEXT_SEC,
        )
        self._pdf_tab_btn.configure(
            bg=ACCENT3 if is_pdf else BG_SURFACE,
            fg="white" if is_pdf else TEXT_SEC,
        )

        # Drop zone accent
        self.drop_zone.configure(highlightbackground=acc)

        # Drop zone text & icon
        if is_img:
            self._dz_icon.configure(text="🖼️")
            self._dz_title.configure(text="Arrastra tus imágenes aquí")
            self._dz_hint.configure(text="JPEG · PNG · WebP · BMP · TIFF")
        elif is_pdf:
            self._dz_icon.configure(text="📄")
            self._dz_title.configure(text="Arrastra tus PDFs aquí")
            self._dz_hint.configure(text="Extrae páginas como imágenes WebP")
        else:
            self._dz_icon.configure(text="🎬")
            self._dz_title.configure(text="Arrastra tus videos aquí")
            self._dz_hint.configure(text="MP4 · WebM · MOV · MKV · AVI")

        # Format options
        if is_img:
            fmts = IMG_FORMATS
        elif is_pdf:
            fmts = PDF_FORMATS
        else:
            fmts = VID_FORMATS

        self.fmt_menu.configure(values=fmts, button_color=acc)
        self.fmt_var.set(fmts[0])

        # Compress button color
        self.compress_btn.configure(fg_color=acc)

        # Progress bar color
        self.progress_bar.configure(progress_color=acc)

        # Clear queue when switching
        self._clear_queue()
        
        if is_img:
            status = "Modo imágenes."
        elif is_pdf:
            status = "Modo PDF — extraer páginas."
        else:
            status = "Modo video — se usará FFmpeg."
            
        self.status_var.set(status)

    @property
    def _valid_ext(self):
        if self._mode == "image": return IMG_EXT
        if self._mode == "pdf": return PDF_EXT
        return VID_EXT

    def _on_drop(self, event):
        paths = parse_drop_paths(event.data)
        added = 0
        for p in paths:
            path = Path(p)
            if path.is_dir():
                for f in path.rglob("*"):
                    if f.suffix.lower() in self._valid_ext and self._enqueue(f):
                        added += 1
            elif path.suffix.lower() in self._valid_ext:
                if self._enqueue(path):
                    added += 1
        if added:
            kind = "imagen(es)" if self._mode == "image" else "video(s)"
            self.status_var.set(f"Se agregaron {added} {kind}.")
        elif paths:
            self.status_var.set("Ningún archivo compatible fue detectado en el drop.")

    def _browse_files(self):
        if self._mode == "image":
            types = [
                ("Imágenes", "*.jpg *.jpeg *.png *.webp *.bmp *.tiff *.tif"),
                ("Todos", "*.*"),
            ]
        elif self._mode == "pdf":
            types = [
                ("PDF", "*.pdf"),
                ("Todos", "*.*"),
            ]
        else:
            types = [
                ("Videos", "*.mp4 *.mov *.mkv *.avi *.webm *.m4v"),
                ("Todos", "*.*"),
            ]
        files = filedialog.askopenfilenames(
            title="Seleccionar archivos", filetypes=types
        )
        added = 0
        for f in files:
            if self._enqueue(Path(f)):
                added += 1
        if added:
            kind = "imagen(es)" if self._mode == "image" else "video(s)"
            self.status_var.set(f"Se agregaron {added} {kind}.")

    def _enqueue(self, path: Path) -> bool:
        if path in self.queued_files:
            return False
        self.queued_files.append(path)
        self._add_queue_row(path)
        self._refresh_queue_label()
        return True

    def _add_queue_row(self, path: Path):
        if self.empty_label.winfo_ismapped():
            self.empty_label.pack_forget()

        is_vid = self._mode == "video"
        row_bg = BG_SURFACE
        row_bg2 = BG_ELEVATED

        idx = len(self.queued_files) - 1
        bg = row_bg if idx % 2 == 0 else row_bg2

        row = tk.Frame(
            self.inner_list, bg=bg, highlightbackground=BORDER, highlightthickness=0
        )
        row.pack(fill="x", padx=0, pady=0)

        # Colored left strip
        if is_vid:
            strip_color = ACCENT2
        elif self._mode == "pdf":
            strip_color = ACCENT3
        else:
            strip_color = ACCENT
            
        tk.Frame(row, bg=strip_color, width=3).pack(side="left", fill="y")

        ext = path.suffix.upper().lstrip(".")
        BADGE_COLORS = {
            "JPG": "#D97706",
            "JPEG": "#D97706",
            "PNG": "#7C3AED",
            "WEBP": "#059669",
            "BMP": "#475569",
            "TIFF": "#475569",
            "TIF": "#475569",
            "MP4": "#DC2626",
            "MOV": "#EA580C",
            "MKV": "#CA8A04",
            "AVI": "#0284C7",
            "WEBM": "#16A34A",
            "M4V": "#9333EA",
            "PDF": "#E11D48",
        }
        badge_bg = BADGE_COLORS.get(ext, "#475569")

        badge = tk.Label(
            row,
            text=ext,
            bg=badge_bg,
            fg="white",
            font=("Segoe UI", 7, "bold"),
            padx=7,
            pady=3,
        )
        badge.pack(side="left", padx=(10, 8), pady=8)

        # Name
        name_lbl = tk.Label(
            row, text=path.name, bg=bg, fg=TEXT_PRI, font=("Segoe UI", 10), anchor="w"
        )
        name_lbl.pack(side="left", fill="x", expand=True)

        # Size
        try:
            sz = human_size(path.stat().st_size)
        except Exception:
            sz = "?"
        tk.Label(row, text=sz, bg=bg, fg=TEXT_DIM, font=("Segoe UI", 9)).pack(
            side="left", padx=(0, 10)
        )

        # Status indicator
        status_lbl = tk.Label(
            row, text="  ·  ", bg=bg, fg=TEXT_DIM, font=("Segoe UI", 11)
        )
        status_lbl.pack(side="left", padx=(0, 2))

        # Remove btn
        rm = tk.Label(
            row,
            text="✕",
            bg=bg,
            fg=DANGER,
            font=("Segoe UI", 11),
            cursor="hand2",
            padx=10,
        )
        rm.pack(side="right")
        rm.bind(
            "<Button-1>",
            lambda e, p=path, r=row: (
                self._remove_from_queue(p),
                r.destroy(),
                self._refresh_queue_label(),
            ),
        )

        # Hover on row
        def _enter(e, r=row, children=row.winfo_children()):
            for c in r.winfo_children():
                try:
                    c.configure(bg=BG_ELEVATED if bg == BG_SURFACE else BG_SURFACE)
                except Exception:
                    pass
            r.configure(bg=BG_ELEVATED if bg == BG_SURFACE else BG_SURFACE)

        def _leave(e, r=row, orig=bg):
            for c in r.winfo_children():
                try:
                    c.configure(bg=orig)
                except Exception:
                    pass
            r.configure(bg=orig)

        row.bind("<Enter>", _enter)
        row.bind("<Leave>", _leave)

        # Store status label reference in the app dict (Path objects are immutable)
        self._row_labels[path] = status_lbl

    def _remove_from_queue(self, path: Path):
        if path in self.queued_files:
            self.queued_files.remove(path)
        if not self.queued_files:
            self.empty_label.pack(expand=True, pady=36)

    def _clear_queue(self):
        if self._processing:
            return
        self.queued_files.clear()
        self._row_labels.clear()
        for w in self.inner_list.winfo_children():
            if w != self.empty_label:
                w.destroy()
        self.empty_label.pack(expand=True, pady=36)
        self._refresh_queue_label()
        self.progress_bar.set(0)

    def _refresh_queue_label(self):
        self.queue_label.configure(text=f"Cola  ({len(self.queued_files)})")

    def _start_compression(self):
        if self._processing:
            return
        if not self.queued_files:
            messagebox.showwarning(
                "Cola vacía", "Agrega al menos un archivo antes de comprimir."
            )
            return
        if self._mode == "video" and not FFMPEG_OK:
            messagebox.showerror(
                "FFmpeg no disponible",
                "No se encontró imageio-ffmpeg.\n"
                "Instálalo con:  pip install imageio-ffmpeg",
            )
            return

        self._processing = True
        self.compress_btn.configure(state="disabled", text="Procesando…")
        self.results.clear()
        threading.Thread(target=self._worker, daemon=True).start()

    def _worker(self):
        dest = get_downloads_folder()
        dest.mkdir(parents=True, exist_ok=True)

        total = len(self.queued_files)
        fmt = self.fmt_var.get()

        # Fixed auto-quality: always use the optimal compression level
        quality = IMG_QUALITY_AUTO if self._mode == "image" else VID_QUALITY_AUTO

        for i, src in enumerate(list(self.queued_files)):
            self.after(
                0,
                lambda i=i, t=total: self.status_var.set(f"Comprimiendo {i + 1}/{t}…"),
            )
            self.after(0, lambda v=i / total: self.progress_bar.set(v))

            try:
                if self._mode == "image":
                    result = compress_image(src, dest, fmt, quality)
                elif self._mode == "pdf":
                    def _prog(p, i=i, t=total):
                        overall = (i + p) / t
                        self.after(0, lambda v=overall: self.progress_bar.set(v))
                    result = compress_pdf(src, dest, _prog)
                else:
                    def _prog(p, i=i, t=total):
                        overall = (i + p) / t
                        self.after(0, lambda v=overall: self.progress_bar.set(v))

                    result = compress_video(src, dest, fmt, quality, _prog)

                self.results.append(result)
                self.after(0, lambda s=src: self._mark_row(s, True))
            except Exception as ex:
                self.results.append({"name": src.name, "ok": False, "error": str(ex)})
                self.after(0, lambda s=src: self._mark_row(s, False))

        self.after(0, lambda: self.progress_bar.set(1.0))
        self.after(0, self._show_summary)

    def _mark_row(self, path: Path, ok: bool):
        lbl = self._row_labels.get(path)
        if lbl and lbl.winfo_exists():
            lbl.configure(text="✅" if ok else "❌", fg=SUCCESS if ok else DANGER)

    def _show_summary(self):
        self._processing = False
        if self._mode == "image":
            acc_text = "⚡  Comprimir"
        elif self._mode == "pdf":
            acc_text = "⚡  Extraer PDF"
        else:
            acc_text = "⚡  Comprimir video"
            
        self.compress_btn.configure(state="normal", text=acc_text)

        ok_res = [r for r in self.results if r.get("ok")]
        fail_res = [r for r in self.results if not r.get("ok")]

        t_orig = sum(r["orig"] for r in ok_res)
        t_new = sum(r["new"] for r in ok_res)
        t_saved = t_orig - t_new
        pct_avg = (t_saved / t_orig * 100) if t_orig else 0

        dest = get_downloads_folder()

        # ── Summary window ──
        win = tk.Toplevel(self)
        win.title("Resumen")
        win.configure(bg=BG_BASE)
        win.geometry("700x580")
        win.grab_set()

        self.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        win.geometry(f"+{px + (pw - 700) // 2}+{py + (ph - 580) // 2}")

        # Title
        if self._mode == "image": acc = ACCENT
        elif self._mode == "pdf": acc = ACCENT3
        else: acc = ACCENT2
        tk.Label(
            win,
            text="✅  Compresión completada",
            bg=BG_BASE,
            fg=SUCCESS,
            font=("Segoe UI", 18, "bold"),
        ).pack(pady=(28, 2))
        tk.Label(
            win, text=str(dest), bg=BG_BASE, fg=TEXT_DIM, font=("Segoe UI", 9)
        ).pack()

        # Stats cards
        cards = tk.Frame(win, bg=BG_BASE)
        cards.pack(fill="x", padx=28, pady=18)

        def stat_card(parent, label, value, color):
            f = tk.Frame(
                parent,
                bg=BG_SURFACE,
                highlightbackground=BORDER,
                highlightthickness=1,
                padx=14,
                pady=10,
            )
            f.pack(side="left", fill="both", expand=True, padx=4)
            tk.Label(
                f, text=label, bg=BG_SURFACE, fg=TEXT_DIM, font=("Segoe UI", 7, "bold")
            ).pack()
            tk.Label(
                f, text=value, bg=BG_SURFACE, fg=color, font=("Segoe UI", 16, "bold")
            ).pack()

        stat_card(cards, "ORIGINAL", human_size(t_orig), TEXT_SEC)
        stat_card(cards, "COMPRIMIDO", human_size(t_new), acc)
        stat_card(cards, "ESPACIO LIBRE", human_size(t_saved), SUCCESS)
        stat_card(cards, "REDUCCIÓN", f"{pct_avg:.1f}%", WARNING)

        # Table header
        hdr = tk.Frame(win, bg=BG_ELEVATED)
        hdr.pack(fill="x", padx=28)
        for text, w in [
            ("Archivo", 36),
            ("Original", 10),
            ("Comprimido", 12),
            ("Ahorro", 9),
            ("", 5),
        ]:
            tk.Label(
                hdr,
                text=text,
                bg=BG_ELEVATED,
                fg=TEXT_DIM,
                font=("Segoe UI", 8, "bold"),
                width=w,
                anchor="w",
            ).pack(side="left", padx=4, pady=5)

        # Scrollable rows
        tbl_wrap = tk.Frame(win, bg=BG_BASE)
        tbl_wrap.pack(fill="both", expand=True, padx=28, pady=(0, 8))

        t_canvas = tk.Canvas(tbl_wrap, bg=BG_SURFACE, highlightthickness=0, bd=0)
        t_sb = tk.Scrollbar(tbl_wrap, orient="vertical", command=t_canvas.yview)
        t_inner = tk.Frame(t_canvas, bg=BG_SURFACE)
        t_inner.bind(
            "<Configure>",
            lambda e: t_canvas.configure(scrollregion=t_canvas.bbox("all")),
        )
        t_canvas.create_window((0, 0), window=t_inner, anchor="nw")
        t_canvas.configure(yscrollcommand=t_sb.set)
        t_canvas.pack(side="left", fill="both", expand=True)
        t_sb.pack(side="right", fill="y")

        for idx, r in enumerate(self.results):
            rb = BG_SURFACE if idx % 2 == 0 else BG_ELEVATED
            row = tk.Frame(t_inner, bg=rb)
            row.pack(fill="x")
            if r.get("ok"):
                nm = r["name"]
                nm = (nm[:34] + "…") if len(nm) > 35 else nm
                vals = [
                    (nm, TEXT_PRI, 36),
                    (human_size(r["orig"]), TEXT_DIM, 10),
                    (human_size(r["new"]), acc, 12),
                    (f"{r['pct']:.1f}%", SUCCESS if r["pct"] > 0 else DANGER, 9),
                    ("✅", SUCCESS, 5),
                ]
            else:
                nm = r["name"][:34]
                vals = [
                    (nm, TEXT_PRI, 36),
                    ("—", TEXT_DIM, 10),
                    ("—", TEXT_DIM, 12),
                    ("—", TEXT_DIM, 9),
                    ("❌", DANGER, 5),
                ]
            for text, color, w in vals:
                tk.Label(
                    row,
                    text=text,
                    bg=rb,
                    fg=color,
                    font=("Segoe UI", 9),
                    width=w,
                    anchor="w",
                ).pack(side="left", padx=4, pady=4)

        if fail_res:
            tk.Label(
                win,
                text=f"⚠  {len(fail_res)} archivo(s) fallaron.",
                bg=BG_BASE,
                fg=WARNING,
                font=("Segoe UI", 9),
            ).pack()

        # Buttons
        btns = tk.Frame(win, bg=BG_BASE)
        btns.pack(pady=(6, 20))

        ctk.CTkButton(
            btns,
            text="📂  Abrir carpeta",
            command=lambda: os.startfile(str(dest)),
            fg_color=BG_ELEVATED,
            hover_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
            font=ctk.CTkFont("Segoe UI", 11),
            height=38,
            corner_radius=8,
        ).pack(side="left", padx=8)

        ctk.CTkButton(
            btns,
            text="Cerrar",
            command=win.destroy,
            fg_color=acc,
            hover_color=ACCENT_DARK,
            font=ctk.CTkFont("Segoe UI", 11),
            height=38,
            corner_radius=8,
        ).pack(side="left", padx=8)

        if self._mode == "image":
            kind = "imagen(es)"
        elif self._mode == "pdf":
            kind = "PDF(s)"
        else:
            kind = "video(s)"
        self.status_var.set(
            f"✅  {len(ok_res)} {kind} procesados  ·  "
            f"{human_size(t_saved)} ahorrados  ·  "
            f"Guardados en Downloads/Compresso"
        )

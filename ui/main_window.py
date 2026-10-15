import os
import customtkinter as ctk
import threading
import numpy as np
from tkinter import filedialog
from typing import Optional
from PIL import Image

from ui.image_panel import ImagePanel
from ui.results_panel import ResultsPanel

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

_FONT    = "Segoe UI"
_APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_HDR_BG    = ("#1a4f9c", "#0d2a5c")
_HDR_SUB   = ("#93c5fd", "#6ea8e8")
_DROP_BG   = ("#dbeafe", "#1a2a42")
_DROP_HOV  = ("#bfdbfe", "#1e3050")
_DROP_BORD = ("#3b82f6", "#2d5fa8")
_STATUS    = {
    "green":  ("#15803d", "#4ade80"),
    "red":    ("#dc2626", "#f87171"),
    "orange": ("#d97706", "#fbbf24"),
    "gray":   ("gray50",  "gray55"),
}

# Ancho del panel izquierdo: imagen 286px + 3px margen c/lado + 16px padding x2 = 324
_LEFT_W = 330


def _load_logo(filename: str, size: int) -> "ctk.CTkImage | None":
    """Carga un logo con fondo negro/blanco y lo convierte a blanco con alpha.

    Usa la luminancia del pixel como canal alpha: blanco=opaco, negro=transparente.
    Funciona correctamente con JPEG (sin artifacts de compresión) y PNG.
    """
    path = os.path.join(_APP_DIR, filename)
    if not os.path.exists(path):
        return None
    try:
        # Luminancia → alpha: pixel brillante = opaco, oscuro = transparente
        gray  = Image.open(path).convert("L")
        alpha = gray.point(lambda x: min(255, int(x * 1.4)))  # leve boost de contraste
        # Logo blanco puro con el alpha derivado de la luminancia
        white = Image.new("RGBA", gray.size, (255, 255, 255, 0))
        white.putalpha(alpha)
        white = white.resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=white, dark_image=white, size=(size, size))
    except Exception:
        return None


class MainWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("NotaINE — Notaría Pública No. 134")
        self.geometry("1300x820")
        self.minsize(1080, 680)

        self._frente_img: Optional[np.ndarray] = None
        self._reverso_img: Optional[np.ndarray] = None
        self._engine_ready = False
        self._warmup_future = None

        # Ícono de la ventana y barra de tareas
        ico = os.path.join(_APP_DIR, "LOGONUEVO.ico")
        if os.path.exists(ico):
            self.iconbitmap(ico)

        self._build_ui()
        self._set_status("Cargando motor OCR…  (la primera vez en una PC "
                         "nueva puede tardar unos minutos)", "orange")
        self._start_warmup_check()

    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── Header ───────────────────────────────────────────────────
        hdr = ctk.CTkFrame(self, height=60, corner_radius=0, fg_color=_HDR_BG)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)

        # Logo empresa (fondo negro → transparente sobre el azul del header)
        empresa_logo = _load_logo("LogoEmpresa.JPG", 44)
        if empresa_logo:
            ctk.CTkLabel(hdr, text="", image=empresa_logo,
                         width=44, height=44).pack(side="left", padx=(16, 6), pady=8)

        ctk.CTkLabel(hdr, text="NotaINE",
                     font=ctk.CTkFont(family=_FONT, size=20, weight="bold"),
                     text_color="white").pack(side="left", pady=16)
        ctk.CTkLabel(hdr, text="  —  Notaría Pública No. 134",
                     font=ctk.CTkFont(family=_FONT, size=14),
                     text_color=_HDR_SUB).pack(side="left", pady=16)

        ctk.CTkLabel(hdr, text="Procesamiento 100 % local  •  Sin internet",
                     font=ctk.CTkFont(family=_FONT, size=11),
                     text_color=_HDR_SUB).pack(side="right", padx=22)

        # ── Footer ─────────────────────────────────────────────────────
        # (se empaqueta antes del body para que quede fijo abajo)
        footer = ctk.CTkFrame(self, height=26, corner_radius=0,
                              fg_color=("gray82", "gray12"))
        footer.pack(fill="x", side="bottom")
        footer.pack_propagate(False)
        ctk.CTkLabel(
            footer,
            text="NotaINE   •   Notaría Pública No. 134   •   Desarrollado por Alberto Torres",
            font=ctk.CTkFont(family=_FONT, size=10),
            text_color=("gray45", "gray55")).pack(pady=4)

        # ── Body ──────────────────────────────────────────────────────
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=12)

        # ── Panel izquierdo ───────────────────────────────────────────
        left = ctk.CTkFrame(body, width=_LEFT_W, corner_radius=14)
        left.pack(side="left", fill="y", padx=(0, 12))
        left.pack_propagate(False)

        # Botón compacto de carga PDF
        self._btn_pdf = ctk.CTkButton(
            left, text="📂  Cargar PDF",
            font=ctk.CTkFont(family=_FONT, size=13, weight="bold"),
            height=40, corner_radius=10,
            command=self._load_pdf)
        self._btn_pdf.pack(fill="x", padx=14, pady=(14, 6))

        # Nombre de archivo cargado
        self._fname_lbl = ctk.CTkLabel(
            left, text="Ningún archivo seleccionado",
            font=ctk.CTkFont(family=_FONT, size=10),
            text_color=("gray55", "gray55"),
            wraplength=_LEFT_W - 28)
        self._fname_lbl.pack(pady=(0, 8))

        # ── Imágenes grandes apiladas ──────────────────────────────────
        self.panel_frente = ImagePanel(left, on_load_callback=self._on_frente_loaded)
        self.panel_frente.pack(padx=14, pady=(0, 6))

        self.panel_reverso = ImagePanel(left, on_load_callback=self._on_reverso_loaded)
        self.panel_reverso.pack(padx=14, pady=(0, 10))

        # Separador
        ctk.CTkFrame(left, height=1, fg_color=("gray75", "gray28")
                     ).pack(fill="x", padx=14, pady=(0, 8))

        # Botón PROCESAR (deshabilitado hasta que el motor OCR termine de cargar)
        self.btn_process = ctk.CTkButton(
            left, text="Cargando motor…",
            font=ctk.CTkFont(family=_FONT, size=15, weight="bold"),
            height=48, corner_radius=12,
            state="disabled",
            command=self._process)
        self.btn_process.pack(fill="x", padx=14, pady=(0, 6))

        # Botón Limpiar
        self.btn_clear = ctk.CTkButton(
            left, text="Limpiar",
            font=ctk.CTkFont(family=_FONT, size=12),
            height=32, fg_color="transparent",
            border_width=1, border_color=("gray60", "gray42"),
            text_color=("gray35", "gray65"),
            hover_color=("gray88", "gray24"),
            command=self._clear)
        self.btn_clear.pack(fill="x", padx=14)

        # Status
        self.status = ctk.CTkLabel(
            left, text="",
            font=ctk.CTkFont(family=_FONT, size=11),
            wraplength=_LEFT_W - 28)
        self.status.pack(pady=10, padx=14)

        # ── Panel derecho ─────────────────────────────────────────────
        self.results_panel = ResultsPanel(body, export_callback=self._export_pdf)
        self.results_panel.pack(side="left", fill="both", expand=True)

    # ──────────────────────────────────────────────────────────────────
    def _start_warmup_check(self):
        try:
            from core.ocr_engine import _executor, _run_ocr_impl
            # Warm-up REAL: corre una inferencia sobre una imagen del tamaño de
            # una INE (~1334×845 px a 400 DPI). Esto NO solo crea el motor, sino
            # que compila las primitivas oneDNN para esa forma de entrada. Al
            # abrir el primer PDF real, todo está caliente → segundos, no minutos.
            # Se usa _run_ocr_impl (corre DENTRO del hilo del executor); usar
            # run_ocr aquí causaría auto-bloqueo del executor de 1 hilo.
            dummy = np.zeros((845, 1334, 3), dtype=np.uint8)
            self._warmup_future = _executor.submit(_run_ocr_impl, dummy)
        except Exception:
            self._on_engine_ready()
            return
        import time
        self._warmup_t0 = time.time()
        self.after(1000, self._check_warmup)

    def _check_warmup(self):
        if self._warmup_future is None or self._warmup_future.done():
            try:
                if self._warmup_future:
                    self._warmup_future.result()
            except Exception as exc:
                self._set_status(f"Error al cargar motor: {exc}", "red")
                self.btn_process.configure(text="Error de motor")
                return
            self._on_engine_ready()
        else:
            # Contador visible: que nunca parezca congelado mientras carga.
            import time
            secs = int(time.time() - self._warmup_t0)
            self._set_status(
                f"Cargando motor OCR…  {secs} s  (mientras, puedes cargar el PDF)",
                "orange")
            self.after(1000, self._check_warmup)

    def _on_engine_ready(self):
        self._engine_ready = True
        self.btn_process.configure(state="normal", text="⚡  PROCESAR")
        self._set_status("✓ Motor listo. Carga un PDF para comenzar.", "green")
        self.after(5000, lambda: self._set_status("", "gray"))

    # ──────────────────────────────────────────────────────────────────
    def _load_pdf(self):
        path = filedialog.askopenfilename(
            title="Seleccionar PDF escaneado de INE",
            filetypes=[("PDF", "*.pdf"), ("Todos", "*.*")])
        if not path:
            return

        self._btn_pdf.configure(state="disabled", text="Cargando...")
        self._set_status("Leyendo PDF...", "gray")

        def worker():
            try:
                from core.pdf_loader import pdf_to_images
                pages = pdf_to_images(path)
                self.after(0, lambda: self._on_pdf_loaded(pages, path))
            except Exception as exc:
                import traceback
                traceback.print_exc()
                msg = str(exc) or repr(exc)
                self.after(0, lambda m=msg: self._set_status(f"Error: {m}", "red"))
                self.after(0, lambda: self._btn_pdf.configure(
                    state="normal", text="📂  Cargar PDF"))

        threading.Thread(target=worker, daemon=True).start()

    def _on_pdf_loaded(self, pages: list, path: str):
        self._btn_pdf.configure(state="normal", text="📂  Cargar PDF")
        if not pages:
            self._set_status("PDF vacío.", "red")
            return

        fname = path.replace("\\", "/").split("/")[-1]
        self._fname_lbl.configure(text=fname, text_color=("gray40", "gray65"))

        self._frente_img = pages[0]
        self.panel_frente._set_from_array(pages[0])

        if len(pages) >= 2:
            self._reverso_img = pages[1]
            self.panel_reverso._set_from_array(pages[1])
            self._set_status(f"✓  {len(pages)} páginas listas.", "green")
        else:
            self._reverso_img = None
            self.panel_reverso.clear()
            self._set_status("Solo 1 página (solo frente).", "orange")

    def _on_frente_loaded(self, img: np.ndarray, _: str):
        self._frente_img = img

    def _on_reverso_loaded(self, img: np.ndarray, _: str):
        self._reverso_img = img

    def _process(self):
        if not self._engine_ready:
            self._set_status("Motor cargando, espera un momento…", "orange")
            return
        if self._frente_img is None:
            self._set_status("Carga al menos el frente.", "orange")
            return

        self.btn_process.configure(state="disabled", text="Procesando...")
        self._set_status("Ejecutando OCR...", "gray")

        def worker():
            try:
                from core.processor import process_full
                result = process_full(self._frente_img, self._reverso_img)
                self.after(0, lambda r=result: self._on_result(r))
            except Exception as exc:
                import traceback
                traceback.print_exc()
                msg = str(exc) or repr(exc)
                self.after(0, lambda m=msg: self._on_error(m))

        threading.Thread(target=worker, daemon=True).start()

    def _on_result(self, result):
        # Si el PDF venía con las páginas invertidas (reverso primero), corregir
        # el orden de las imágenes para los thumbnails y la exportación a PDF.
        if result.get("paginas_invertidas") and self._reverso_img is not None:
            self._frente_img, self._reverso_img = self._reverso_img, self._frente_img
            self.panel_frente._set_from_array(self._frente_img)
            self.panel_reverso._set_from_array(self._reverso_img)

        self.results_panel.update_results(result)
        self.btn_process.configure(state="normal", text="⚡  PROCESAR")
        self._set_status("✓  Extracción completada.", "green")

    def _on_error(self, error: str):
        self.btn_process.configure(state="normal", text="⚡  PROCESAR")
        self._set_status(f"Error: {error}", "red")

    def _export_pdf(self, data: dict):
        # Requiere que haya datos extraídos (al menos nombre o CURP)
        if not any(data.get(k) for k in ("nombre_completo", "curp", "clave_elector")):
            self._set_status("Procesa una INE antes de exportar.", "orange")
            return

        sugerido = (data.get("nombre_completo") or "INE").replace(" ", "_")
        path = filedialog.asksaveasfilename(
            title="Guardar PDF",
            defaultextension=".pdf",
            initialfile=f"{sugerido}.pdf",
            filetypes=[("PDF", "*.pdf")])
        if not path:
            return

        try:
            from core.pdf_export import export_to_pdf
            export_to_pdf(path, data, self._frente_img, self._reverso_img)
            self._set_status("✓  PDF exportado correctamente.", "green")
        except Exception as e:
            self._set_status(f"Error al exportar: {e}", "red")

    def _clear(self):
        self._frente_img = None
        self._reverso_img = None
        self.panel_frente.clear()
        self.panel_reverso.clear()
        self.results_panel.clear()
        self._fname_lbl.configure(text="Ningún archivo seleccionado",
                                   text_color=("gray55", "gray55"))
        self._set_status("", "gray")

    def _set_status(self, text: str, color: str):
        self.status.configure(text=text,
                               text_color=_STATUS.get(color, _STATUS["gray"]))

import sys
import os
import traceback
import multiprocessing

# Desactivar la inicialización "eager" de PaddleX (gestor de repos de
# entrenamiento) — innecesaria para inferencia y causa doble-init en el .exe.
os.environ.setdefault("PADDLE_PDX_EAGER_INIT", "False")

# Bloquear librerías de IA que el OCR no usa (ver nota en core/ocr_engine.py).
# Debe hacerse ANTES de cualquier import de paddle. Recorta el arranque a
# una fracción y permite excluirlas del empaquetado (exe mucho más chico).
for _mod in ("torch", "transformers"):
    if _mod not in sys.modules:
        sys.modules[_mod] = None

# Hilos de cómputo = núcleos FÍSICOS del CPU (mín 2, máx 4). Los lógicos
# engañan: un i5-4460S tiene 4 físicos/4 lógicos (usar 4), un i3 con
# hyper-threading tiene 2 físicos/4 lógicos (usar 2, no satura sus 4 GB).
# psutil distingue físicos; si falla, se estima con lógicos/2.
try:
    import psutil
    _cores = psutil.cpu_count(logical=False) or 2
except Exception:
    _cores = (os.cpu_count() or 4) // 2
_n_threads = str(max(2, min(4, _cores)))
os.environ.setdefault("OMP_NUM_THREADS", _n_threads)
os.environ.setdefault("MKL_NUM_THREADS", _n_threads)
os.environ.setdefault("OPENBLAS_NUM_THREADS", _n_threads)
# Forzar MKL-DNN (oneDNN) y aumentar caché de primitivas compiladas.
os.environ.setdefault("FLAGS_use_mkldnn", "1")
os.environ.setdefault("FLAGS_mkldnn_cache_capacity", "20")

# ── Directorio base (compatible con PyInstaller) ──────────────────────────
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(sys.executable)
    DATA_DIR = getattr(sys, '_MEIPASS', BASE_DIR)   # _internal en onedir
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = BASE_DIR

sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

# ── Matplotlib: evitar la construcción del caché de fuentes ───────────────
# paddleocr importa matplotlib; la PRIMERA vez en una PC, matplotlib escanea
# todas las fuentes del sistema ("building the font cache") — 3-5 minutos en
# PCs lentas, sin ningún aviso visual (parece colgado). Empaquetamos un caché
# pre-construido y lo copiamos al perfil del usuario si aún no existe.
os.environ.setdefault("MPLBACKEND", "Agg")   # nunca graficamos; backend mínimo
def _seed_mpl_cache():
    try:
        import shutil
        cache_dir = os.path.join(
            os.environ.get("LOCALAPPDATA", BASE_DIR), "NotaINE", "mpl-cache")
        os.makedirs(cache_dir, exist_ok=True)
        os.environ["MPLCONFIGDIR"] = cache_dir
        seed = os.path.join(DATA_DIR, "mpl-cache")
        if os.path.isdir(seed):
            for name in os.listdir(seed):
                dst = os.path.join(cache_dir, name)
                if not os.path.exists(dst):
                    shutil.copy2(os.path.join(seed, name), dst)
    except Exception:
        pass  # sin caché solo se pierde tiempo la primera vez; no es fatal
_seed_mpl_cache()

# ── stdout/stderr SIEMPRE válidos ─────────────────────────────────────────
# En modo windowed (sin consola) PyInstaller deja sys.stdout/stderr en None.
# PaddlePaddle (glog, C++) escribe a esos descriptores durante la
# inicialización y se BLOQUEA si no existen. Los redirigimos a un log.
def _ensure_stdio():
    if sys.stdout is not None and sys.stderr is not None:
        return
    try:
        log_path = os.path.join(BASE_DIR, "notaine.log")
        # Rotación simple: si el log pasa de 5 MB, empezar de cero
        # (conserva el anterior como .old por si hay que diagnosticar).
        try:
            if os.path.getsize(log_path) > 5 * 1024 * 1024:
                os.replace(log_path, log_path + ".old")
        except OSError:
            pass
        log = open(log_path, "a",
                   buffering=1, encoding="utf-8", errors="replace")
        if sys.stdout is None:
            sys.stdout = log
        if sys.stderr is None:
            sys.stderr = log
        # También fijar los descriptores 1 y 2 a nivel de sistema (para C++).
        try:
            os.dup2(log.fileno(), 1)
            os.dup2(log.fileno(), 2)
        except Exception:
            pass
    except Exception:
        pass


def _warn_if_network_drive():
    """Si la app corre desde una unidad de red (X:, \\servidor\...), avisa que
    va a tardar muchísimo y que debe copiarse al disco local. Caso real: la
    corrían desde X: y el motor tardaba 2+ min en cargar por la red."""
    try:
        import ctypes
        drive = os.path.splitdrive(BASE_DIR)[0]
        if not drive:
            return
        DRIVE_REMOTE = 4
        if ctypes.windll.kernel32.GetDriveTypeW(drive + "\\") != DRIVE_REMOTE:
            return
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showwarning(
            "NotaINE — Estás en una unidad de RED",
            f"NotaINE se está abriendo desde la unidad de red "
            f"{drive} y así tarda VARIOS MINUTOS en cargar.\n\n"
            f"Para que cargue en segundos:\n"
            f"1. Copia la carpeta NotaINE completa a esta computadora\n"
            f"    (por ejemplo a C:\\NotaINE o al Escritorio).\n"
            f"2. Ábrelo desde esa copia local.\n\n"
            f"El programa va a continuar, pero lento."
        )
        root.destroy()
    except Exception:
        pass


def _crash_dialog(exc: str):
    """Muestra un mensaje amigable si la app falla en producción."""
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "NotaINE — Error inesperado",
            f"La aplicación encontró un error y tuvo que cerrarse.\n\n"
            f"{exc}\n\n"
            f"Contacte al administrador del sistema."
        )
        root.destroy()
    except Exception:
        pass


if __name__ == "__main__":
    multiprocessing.freeze_support()  # OBLIGATORIO en PyInstaller si algo usa multiprocessing
    _ensure_stdio()
    _warn_if_network_drive()
    try:
        # El warm-up (cargar + compilar el motor OCR) lo dispara la ventana en
        # cuanto abre, sobre el hilo dedicado del executor. Mantiene UN solo
        # punto de calentamiento para que el botón PROCESAR se active justo
        # cuando el motor está realmente listo.
        from ui.main_window import MainWindow
        app = MainWindow()
        # --min: arranque minimizado (para el inicio automático con Windows;
        # el motor se calienta en segundo plano y al abrirla ya está lista).
        if "--min" in sys.argv:
            app.iconify()
        app.mainloop()
    except Exception:
        _crash_dialog(traceback.format_exc())
        sys.exit(1)

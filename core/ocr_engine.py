from __future__ import annotations
import os
import sys

# PaddleX corre repo_manager.initialize() (gestor de repos de ENTRENAMIENTO) al
# importarse si PADDLE_PDX_EAGER_INIT=True (default). En el .exe empaquetado eso
# se dispara dos veces -> "PDX has already been initialized. Reinitialization is
# not supported." y aborta el OCR. Para INFERENCIA no se necesita, así que lo
# desactivamos ANTES de importar paddle/paddleocr.
os.environ.setdefault("PADDLE_PDX_EAGER_INIT", "False")

# Bloquear librerías de IA que paddleocr importa "por si acaso" pero que el
# OCR de det+rec NO usa (son para pipelines de chart-parsing/doc-VLM que esta
# app jamás invoca). sys.modules[x] = None hace que `import x` lance
# ImportError y los try/except de paddle degraden limpio. Ahorro medido:
# import de paddleocr 14s → 4s en dev; en PCs con HDD la diferencia es mucho
# mayor (torch son cientos de MB que ya ni se leen del disco).
for _mod in ("torch", "transformers"):
    if _mod not in sys.modules:
        sys.modules[_mod] = None          # type: ignore[assignment]

import numpy as np
from dataclasses import dataclass
from typing import List
from concurrent.futures import ThreadPoolExecutor


def _models_base() -> str:
    """Carpeta raíz donde viven los modelos OCR empaquetados.

    En el .exe (PyInstaller onedir) los datos van a _internal (_MEIPASS).
    En desarrollo, a la raíz del proyecto.
    """
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _local_model_dir(name: str) -> str | None:
    """Devuelve la ruta a un modelo local empaquetado, si existe."""
    path = os.path.join(_models_base(), "models", name)
    return path if os.path.isdir(path) else None


@dataclass
class OcrBlock:
    text: str
    x1: int
    y1: int
    x2: int
    y2: int
    confidence: float

    @property
    def cx(self) -> int:
        return (self.x1 + self.x2) // 2

    @property
    def cy(self) -> int:
        return (self.y1 + self.y2) // 2

    @property
    def width(self) -> int:
        return self.x2 - self.x1

    @property
    def height(self) -> int:
        return self.y2 - self.y1


_engine = None

# PaddleOCR/oneDNN cachea sus primitivas de inferencia POR HILO. Si cada
# llamada a OCR corre en un hilo distinto (como hacía la UI al lanzar un
# Thread nuevo por cada PROCESAR), el segundo escaneo arranca con la caché
# fría y tarda muchísimo. Fijamos TODO el OCR a un único hilo persistente:
# el motor se crea y se usa siempre en el mismo hilo → caché siempre caliente.
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr")


def get_engine():
    global _engine
    if _engine is None:
        from paddleocr import PaddleOCR
        # PP-OCRv4 mobile: ~4x más rápido que medium con mínima pérdida de precisión.
        # Los escaneos de INE son texto impreso limpio — el modelo mobile es suficiente.
        kwargs = dict(
            text_detection_model_name="PP-OCRv4_mobile_det",
            text_recognition_model_name="PP-OCRv4_mobile_rec",
            use_doc_orientation_classify=False,
            use_doc_unwarping=False,
            use_textline_orientation=False,
        )
        # Si los modelos vienen empaquetados, usarlos directo (sin descargar nada).
        det_dir = _local_model_dir("PP-OCRv4_mobile_det")
        rec_dir = _local_model_dir("PP-OCRv4_mobile_rec")
        if det_dir and rec_dir:
            kwargs["text_detection_model_dir"]   = det_dir
            kwargs["text_recognition_model_dir"] = rec_dir
        _engine = PaddleOCR(**kwargs)
    return _engine


def run_ocr(img: np.ndarray, min_confidence: float = 0.5) -> List[OcrBlock]:
    """Ejecuta el OCR en el hilo dedicado y bloquea hasta tener el resultado."""
    return _executor.submit(_run_ocr_impl, img, min_confidence).result()


def _run_ocr_impl(img: np.ndarray, min_confidence: float = 0.5) -> List[OcrBlock]:
    engine = get_engine()
    results = engine.predict(img)
    blocks: List[OcrBlock] = []

    if not results:
        return blocks

    res = results[0]
    texts = res.get("rec_texts", [])
    scores = res.get("rec_scores", [])
    polys = res.get("rec_polys", [])

    for text, score, poly in zip(texts, scores, polys):
        if score < min_confidence:
            continue
        if not text or not text.strip():
            continue
        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        blocks.append(OcrBlock(
            text=text.strip(),
            x1=int(min(xs)),
            y1=int(min(ys)),
            x2=int(max(xs)),
            y2=int(max(ys)),
            confidence=float(score),
        ))

    return blocks

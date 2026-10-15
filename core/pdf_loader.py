"""Convierte páginas de un PDF escaneado a imágenes numpy BGR para el pipeline OCR."""
from __future__ import annotations
import numpy as np


def pdf_to_images(path: str, dpi: int = 400) -> list[np.ndarray]:
    """
    Renderiza cada página del PDF como imagen BGR.
    dpi=400 → ~1334×845 px para una CR80 en carta; justo debajo de resize_max(1400)
    para no perder resolución. A 300 DPI la zona MRZ se leía mal (el OCR partía la
    línea IDMEX y perdía dígitos del identificador); a 400 DPI se lee en un bloque
    limpio. Retorna lista de arrays numpy (BGR), uno por página.
    """
    import fitz  # PyMuPDF
    import cv2

    doc = fitz.open(path)
    scale = dpi / 72.0
    mat = fitz.Matrix(scale, scale)
    images: list[np.ndarray] = []

    for page in doc:
        pix = page.get_pixmap(matrix=mat, colorspace=fitz.csRGB)
        arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, 3
        ).copy()                              # copy: desanclar del buffer de fitz
        images.append(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR))

    doc.close()
    return images

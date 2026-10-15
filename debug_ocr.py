"""
Vuelca la salida cruda de PaddleOCR para una imagen, ordenada por posición.
Uso: python debug_ocr.py "ruta\\a\\imagen.jpg"
"""
import sys
sys.path.insert(0, '.')

import cv2
import numpy as np
from PIL import Image
from core import preprocessor
from core.ocr_engine import run_ocr


def load(path):
    pil = Image.open(path).convert("RGB")
    return cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)


def main():
    path = sys.argv[1]
    print(f"== Imagen: {path} ==")
    img = load(path)
    print(f"   dimensiones: {img.shape[1]}x{img.shape[0]}")
    img = preprocessor.preprocess(img)
    blocks = run_ocr(img, min_confidence=0.3)
    # Ordenar por fila (y) y luego columna (x)
    blocks.sort(key=lambda b: (b.y1 // 20, b.x1))
    print(f"   bloques detectados: {len(blocks)}\n")
    for b in blocks:
        print(f"  [{b.confidence:.2f}] y={b.y1:4d} x={b.x1:4d}  | {b.text}")


if __name__ == "__main__":
    main()

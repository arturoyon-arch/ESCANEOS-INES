"""Diagnóstico: muestra bloques OCR crudos + resultado completo para un par."""
import sys, json, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import cv2, numpy as np
from PIL import Image


def load(path):
    return cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)


frente = sys.argv[1]
reverso = sys.argv[2] if len(sys.argv) > 2 else None

from core import preprocessor, ocr_engine
from core.processor import process_full

f_img = load(frente)

print("=" * 60)
print("BLOQUES OCR CRUDOS — FRENTE")
print("=" * 60)
pre = preprocessor.preprocess(f_img)
blocks = ocr_engine.run_ocr(pre)
for b in sorted(blocks, key=lambda x: (x.y1, x.x1)):
    print(f"  [{b.y1:4d},{b.x1:4d}] ({b.confidence:.2f}) {b.text!r}")

print()
print("=" * 60)
print("RESULTADO COMPLETO")
print("=" * 60)
r_img = load(reverso) if reverso else None
result = process_full(f_img, r_img)
print(json.dumps(result, indent=2, ensure_ascii=False))

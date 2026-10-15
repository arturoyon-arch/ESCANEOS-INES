"""Prueba el pipeline completo con un par frente/reverso real."""
import sys, json
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import cv2, numpy as np
from PIL import Image
from core.processor import process_full


def load(path):
    return cv2.cvtColor(np.array(Image.open(path).convert("RGB")), cv2.COLOR_RGB2BGR)


frente = sys.argv[1]
reverso = sys.argv[2] if len(sys.argv) > 2 else None
f_img = load(frente)
r_img = load(reverso) if reverso else None
result = process_full(f_img, r_img)
print(json.dumps(result, indent=2, ensure_ascii=False))

import sys, time
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
import cv2, numpy as np
from PIL import Image
from core.processor import process_full
from core.ocr_engine import get_engine


def load(p):
    return cv2.cvtColor(np.array(Image.open(p).convert("RGB")), cv2.COLOR_RGB2BGR)


f = load(sys.argv[1])
r = load(sys.argv[2]) if len(sys.argv) > 2 else None

from core.ocr_engine import get_engine
t0 = time.time()
get_engine()
t1 = time.time()
print(f"Init motor: {t1-t0:.1f}s")

# Procesar 3 veces para promedio (ya caliente)
for i in range(3):
    t = time.time()
    process_full(f, r)
    print(f"  Credencial {i+1}: {time.time()-t:.2f}s")

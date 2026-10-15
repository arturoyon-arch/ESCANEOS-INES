"""Prueba aislada del cálculo de RFC (sin OCR).
Uso: python debug_rfc.py
Edita CASOS para comparar contra el RFC que da tu calculadora .exe."""
import sys
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
from core.rfc_calculator import calcular_rfc

# (paterno, materno, nombres, fecha DD/MM/YYYY, rfc_esperado_o_None)
CASOS = [
    ("RIOS", "TAMEZ", "CINDY VERENISE", "05/08/1983", None),
    ("RIOS", "TAMEZ", "CINDYVERENISE", "05/08/1983", None),   # como lo lee el OCR
]

for paterno, materno, nombres, fecha, esperado in CASOS:
    rfc = calcular_rfc(paterno, materno, nombres, fecha)
    marca = ""
    if esperado:
        marca = "  ✓ OK" if rfc == esperado else f"  ✗ esperado {esperado}"
    print(f"{paterno} {materno} / {nombres} ({fecha}) -> {rfc}{marca}")

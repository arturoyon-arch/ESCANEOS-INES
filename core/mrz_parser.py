"""
Parser de la zona MRZ del reverso de la INE.
Formato TD1 (ICAO 9303): 3 líneas de 30 caracteres cada una.
"""
from __future__ import annotations
import re
from typing import List, Dict, Optional
from core.ocr_engine import OcrBlock

# Pesos para cálculo del dígito de control ICAO
_WEIGHTS = [7, 3, 1]
_CHAR_VALUES = {str(i): i for i in range(10)}
_CHAR_VALUES.update({chr(c): c - 55 for c in range(65, 91)})
_CHAR_VALUES['<'] = 0


def _check_digit(s: str) -> int:
    total = sum(_CHAR_VALUES.get(c, 0) * _WEIGHTS[i % 3] for i, c in enumerate(s))
    return total % 10


def _normalize_mrz_text(text: str) -> str:
    """Limpia y normaliza un bloque de texto candidato a línea MRZ.
    El OCR a veces lee '<' como 'K'. Casos posibles:
      - Sin '<':  texto puro alfanum → decidir por heurística
      - Con '<' y 'KK': normalización parcial (algunos '<' correctos, otros K)
      - Solo '<':  ya correcto
    """
    text = text.upper().replace(" ", "").replace("-", "")

    # Si empieza con IDMEX, forzar corrección total K→<
    if text.startswith("IDMEX") or text.startswith("IDMX"):
        return text.replace("K", "<")

    if "<" in text:
        # Normalización parcial: el OCR leyó algunos '<' bien y otros como 'K'.
        # Si también tiene 'KK' → completar la corrección K→<.
        if "KK" in text:
            return text.replace("K", "<")
        return text  # ya correcto

    # Sin ningún '<': aplicar heurística KK → <<
    if "KK" in text and len(text) >= 15:
        candidate = text.replace("K", "<")
        mrz_chars = sum(1 for c in candidate if c.isalnum() or c == "<")
        if mrz_chars / len(candidate) > 0.85:
            return candidate

    return text


def _looks_like_mrz(text: str) -> bool:
    """Una línea MRZ contiene el relleno '<' o empieza con el código IDMEX.
    El texto impreso del reverso (INSTITUTO NACIONAL ELECTORAL, firmas, etc.)
    no cumple ninguna de las dos condiciones."""
    if len(text) < 12:
        return False
    if text.startswith("IDMEX") or text.startswith("IDMX") or text.startswith("ID<"):
        return True
    if "<" in text:
        # Debe tener proporción razonable de chars MRZ (alfanum + '<')
        mrz_chars = sum(1 for c in text if c.isalnum() or c == "<")
        return mrz_chars / len(text) > 0.8
    return False


_DATE_LINE_RE = re.compile(r'^\d{6}\d[HMF0-9]')  # YYMMDD + check/sex
_NAME_LINE_RE = re.compile(r'<<')               # tiene separador de nombres


def _extract_mrz_lines(blocks: List[OcrBlock]) -> List[str]:
    """Identifica las 3 líneas MRZ del reverso de la INE (formato TD1).

    Estrategia:
      1. Buscar la línea que comienza con IDMEX → ancla segura.
      2. Si no aparece, clasificar las líneas detectadas por patrón:
         - Línea de fecha: empieza con 6 dígitos (YYMMDD).
         - Línea de nombres: contiene '<<'.
         Devuelve ["", fecha, nombres] con placeholder vacío para la línea 1,
         de modo que el parsing de fecha (linea2) y nombres (linea3) siga correcto.
    """
    candidates = []
    for b in blocks:
        text = _normalize_mrz_text(b.text)
        if _looks_like_mrz(text):
            candidates.append((b.y1, text))

    if not candidates:
        return []

    candidates.sort(key=lambda x: x[0])
    lines = [text for _, text in candidates]

    # Caso 1: línea IDMEX encontrada → ancla directa
    start_idx = next(
        (i for i, l in enumerate(lines)
         if l.startswith("IDMEX") or l.startswith("IDMX")),
        None,
    )
    if start_idx is not None:
        return lines[start_idx:start_idx + 3]

    # Caso 2: sin IDMEX → clasificar por contenido para no desplazar la asignación
    date_lines = [l for l in lines if _DATE_LINE_RE.match(l)]
    name_lines = [l for l in lines if _NAME_LINE_RE.search(l)
                  and not _DATE_LINE_RE.match(l)]

    if date_lines or name_lines:
        # Placeholder vacío para la línea 1 (IDMEX no detectada)
        result = [""]
        if date_lines:
            result.append(date_lines[0])
        if name_lines:
            result.append(name_lines[0])
        return result

    # Fallback: devolver lo que haya
    return lines[-3:]


def _pad_line(line: str, length: int = 30) -> str:
    return line[:length].ljust(length, '<')


def parse_mrz(blocks: List[OcrBlock]) -> Dict[str, str]:
    result = {
        "ocr_linea1": "",
        "ocr_linea2": "",
        "ocr_linea3": "",
        "cic": "",
        "identificador_post_simbolo": "",
        "mrz_nombre": "",
        "mrz_fecha_nacimiento": "",
        "mrz_sexo": "",
        "mrz_vigencia": "",
        "mrz_valido": False,
    }

    lines = _extract_mrz_lines(blocks)
    if not lines:
        return result

    # Guardar líneas crudas
    for i, line in enumerate(lines[:3]):
        result[f"ocr_linea{i+1}"] = line

    if len(lines) < 1:
        return result

    # --- Línea 1: IDMEX + número documento + identificador tras '<<' ---
    line1 = lines[0] if lines else ""
    if "<<" in line1:
        # El identificador relevante está después del símbolo '<<'
        after = line1.split("<<", 1)[1]
        result["identificador_post_simbolo"] = after.replace("<", "").strip()
    result["ocr_linea1"] = line1

    # --- Línea 2: fecha nac + sexo + expiración ---
    if len(lines) >= 2:
        line2 = _pad_line(lines[1])
        # YYMMDD + dígito + sexo + YYMMDD + dígito + nacionalidad
        try:
            dob_raw = line2[0:6]
            sex = line2[7]
            exp_raw = line2[8:14]

            yy = int(dob_raw[0:2])
            mm = dob_raw[2:4]
            dd = dob_raw[4:6]
            year = 1900 + yy if yy > 30 else 2000 + yy
            result["mrz_fecha_nacimiento"] = f"{dd}/{mm}/{year}"
            result["mrz_sexo"] = sex if sex in ("M", "F") else ""

            exp_yy = int(exp_raw[0:2])
            exp_mm = exp_raw[2:4]
            exp_year = 2000 + exp_yy
            result["mrz_vigencia"] = f"{exp_year}-{int(exp_year)+10}"
        except (ValueError, IndexError):
            pass

    # --- Línea 3: apellido<<apellido<<nombre ---
    if len(lines) >= 3:
        line3 = _pad_line(lines[2])
        name_part = line3.replace("<", " ").strip()
        result["mrz_nombre"] = " ".join(name_part.split())

    # --- Extraer CIC ---
    # Prioridad 1: número de documento en línea IDMEX (antes del primer '<')
    # Formato: IDMEX{doc_num}{check}<<... → el doc_num es el folio/CIC
    if line1.startswith("IDMEX") or line1.startswith("IDMX"):
        doc_part = re.sub(r'^IDMX?', '', line1)   # quitar prefijo ID[M]EX
        doc_part = re.sub(r'^EX', '', doc_part)    # quitar EX si quedó
        digits_match = re.match(r'([A-Z]?\d{6,12})', doc_part)
        if digits_match:
            result["cic"] = digits_match.group(1)

    # Prioridad 2: texto impreso en el reverso (letra + 6-12 dígitos)
    if not result["cic"]:
        cic_re = re.compile(r'\b([A-Z]\d{6,12})\b')
        for b in blocks:
            m = cic_re.search(b.text.upper())
            if m:
                result["cic"] = m.group(1)
                break

    return result

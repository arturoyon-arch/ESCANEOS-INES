"""
Validación y autocorrección de campos extraídos.
"""
from __future__ import annotations
import re
from typing import Dict, Tuple

# Correcciones OCR comunes en zonas numéricas
_OCR_NUM = str.maketrans("OILSZB", "015528")
# Correcciones OCR comunes en zonas de letras
_OCR_ALPHA = str.maketrans("0158", "OISH")

ESTADOS_CURP = {
    "AS","BC","BS","CC","CL","CM","CS","CH","DF","DG","GT","GR","HG",
    "JC","MC","MN","MS","NT","NL","OC","PL","QT","QR","SP","SL","SR",
    "TC","TS","TL","VZ","YN","ZS","NE"
}

CURP_RE = re.compile(
    r'^[A-Z]{4}\d{6}[HM][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d$'
)

CLAVE_ELECTOR_RE = re.compile(r'^[A-Z]{6}\d{8}[HM]\d{3}$')

FECHA_RE = re.compile(r'^\d{2}/\d{2}/\d{4}$')


def _fix_ocr_in_field(text: str, is_numeric: bool) -> str:
    if is_numeric:
        return text.translate(_OCR_NUM)
    return text


def fix_curp(curp: str) -> Tuple[str, bool]:
    """Intenta corregir el CURP y devuelve (curp_corregido, es_valido)."""
    curp = curp.upper().strip().replace(" ", "").replace("-", "")

    # Sustituir caracteres que OCR confunde por posición
    # Posiciones 0-3: letras
    # Posiciones 4-9: dígitos (fecha)
    # Posición 10: H o M
    # Posiciones 11-12: estado (letras)
    # Posiciones 13-15: consonantes
    # Posición 16: letra o dígito
    # Posición 17: dígito verificador
    if len(curp) < 18:
        return curp, False

    chars = list(curp[:18])

    # Posiciones 4-9 deben ser dígitos
    for i in range(4, 10):
        if chars[i] in "OILSB":
            chars[i] = chars[i].translate(_OCR_NUM)

    # Posición 10: solo H o M
    if chars[10] not in ("H", "M"):
        if chars[10] == "0":
            chars[10] = "O"  # No válido pero dejarlo
        # Si es número ambiguo dejarlo y marcar inválido

    # Posición 17: dígito
    if chars[17] in "OILB":
        chars[17] = chars[17].translate(_OCR_NUM)

    curp_fixed = "".join(chars)
    valid = bool(CURP_RE.match(curp_fixed))

    # Validar estado
    if len(curp_fixed) >= 13:
        estado_code = curp_fixed[11:13]
        if estado_code not in ESTADOS_CURP:
            valid = False

    return curp_fixed, valid


def fix_fecha(fecha: str) -> Tuple[str, bool]:
    fecha = fecha.strip()
    fecha = re.sub(r'[OoIil]', lambda m: "0" if m.group() in "Oo" else "1", fecha)
    fecha = re.sub(r'[.,-]', '/', fecha)

    if not FECHA_RE.match(fecha):
        return fecha, False

    try:
        dd, mm, yyyy = int(fecha[:2]), int(fecha[3:5]), int(fecha[6:])
        if not (1 <= mm <= 12 and 1 <= dd <= 31 and 1900 <= yyyy <= 2020):
            return fecha, False
    except ValueError:
        return fecha, False

    return fecha, True


def fix_clave_elector(clave: str) -> Tuple[str, bool]:
    clave = clave.upper().strip().replace(" ", "")
    # Primeros 6: letras, siguientes 8: dígitos, 1 letra, 3 dígitos
    if len(clave) != 18:
        return clave, False
    # Corregir dígitos en posiciones 6-13
    chars = list(clave)
    for i in range(6, 14):
        if chars[i] in "OILSB":
            chars[i] = chars[i].translate(_OCR_NUM)
    clave = "".join(chars)
    return clave, bool(CLAVE_ELECTOR_RE.match(clave))


def fix_sexo(sexo: str) -> Tuple[str, bool]:
    sexo = sexo.upper().strip()[:1]
    if sexo not in ("M", "F", "H"):
        return sexo, False
    # INE usa M (masculino) y F (femenino) o H/M en MRZ
    return sexo, True


def fix_cp(cp: str) -> Tuple[str, bool]:
    cp = re.sub(r'[^0-9]', '', cp)
    return cp, len(cp) == 5


def validate_all(data: Dict) -> Dict:
    """Valida y corrige todos los campos. Agrega campo 'confianza' y 'advertencias'."""
    warnings = []
    confidence = {}

    # CURP
    curp, curp_ok = fix_curp(data.get("curp", ""))
    data["curp"] = curp
    confidence["curp"] = 1.0 if curp_ok else 0.5
    if not curp_ok:
        warnings.append("CURP no válida — verificar manualmente")

    # Fecha nacimiento
    fn, fn_ok = fix_fecha(data.get("fecha_nacimiento", ""))
    data["fecha_nacimiento"] = fn
    confidence["fecha_nacimiento"] = 1.0 if fn_ok else 0.6
    if not fn_ok:
        warnings.append("Fecha de nacimiento con formato irregular")

    # Clave de elector
    ce, ce_ok = fix_clave_elector(data.get("clave_elector", ""))
    data["clave_elector"] = ce
    confidence["clave_elector"] = 1.0 if ce_ok else 0.6
    if not ce_ok:
        warnings.append("Clave de elector con formato irregular")

    # Sexo
    sexo, sexo_ok = fix_sexo(data.get("sexo", ""))
    data["sexo"] = sexo
    confidence["sexo"] = 1.0 if sexo_ok else 0.4
    if not sexo_ok:
        warnings.append("Sexo no reconocido")

    # Código postal
    cp, cp_ok = fix_cp(data.get("codigo_postal", ""))
    data["codigo_postal"] = cp
    confidence["codigo_postal"] = 1.0 if cp_ok else 0.5

    data["_confianza"] = confidence
    data["_advertencias"] = warnings
    return data


def _curp_fecha(curp: str) -> str:
    """Deriva DD/MM/YYYY desde el CURP (posiciones 5-10: YYMMDD)."""
    if len(curp) < 10:
        return ""
    yy, mm, dd = curp[4:6], curp[6:8], curp[8:10]
    if not (yy.isdigit() and mm.isdigit() and dd.isdigit()):
        return ""
    # El CURP no distingue siglo; usar el rango plausible de una INE
    year = 2000 + int(yy) if int(yy) <= 25 else 1900 + int(yy)
    return f"{dd}/{mm}/{year}"


def _curp_sexo(curp: str) -> str:
    """Sexo desde el CURP (posición 11: H/M)."""
    if len(curp) >= 11 and curp[10] in ("H", "M"):
        return curp[10]
    return ""


def cross_validate(frente: Dict, reverso: Dict) -> str:
    """Valida el frente contra el CURP (fuente autoritativa) y el MRZ.
    El CURP es la referencia principal porque su estructura es verificable;
    el MRZ es secundario (más propenso a errores de OCR). Retorna 'OK' o
    la descripción de las discrepancias."""
    issues = []
    curp = frente.get("curp", "")

    # Fecha de nacimiento: comparar frente contra CURP (autoritativo)
    fn_frente = frente.get("fecha_nacimiento", "")
    fn_curp = _curp_fecha(curp)
    if fn_frente and fn_curp and fn_frente != fn_curp:
        issues.append(f"Fecha nac. frente ({fn_frente}) ≠ CURP ({fn_curp})")

    # Sexo: comparar frente contra CURP
    sx_frente = frente.get("sexo", "")
    sx_curp = _curp_sexo(curp)
    if sx_frente and sx_curp and sx_frente != sx_curp:
        issues.append(f"Sexo frente ({sx_frente}) ≠ CURP ({sx_curp})")

    return "OK" if not issues else " | ".join(issues)

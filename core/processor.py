from __future__ import annotations
import re
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple

from core import preprocessor, ocr_engine, version_detector, anchor_extractor, mrz_parser, validator
from core.ocr_engine import OcrBlock
from core.rfc_calculator import calcular_rfc

_CURP_QUICK = re.compile(r'[A-Z]{4}\d{6}[HM][A-Z]{5}[A-Z0-9]\d')
_IDMEX_QUICK = re.compile(r'IDMEX|IDMX')


def _has_curp(blocks: List[OcrBlock]) -> bool:
    return any(_CURP_QUICK.search(b.text.upper()) for b in blocks)


def _has_mrz(blocks: List[OcrBlock]) -> bool:
    return any(_IDMEX_QUICK.search(b.text.upper()) for b in blocks)


def _ocr_img(img: np.ndarray) -> Tuple[np.ndarray, List[OcrBlock]]:
    """Preprocesa y ejecuta OCR. Devuelve (img_procesada, bloques)."""
    img_p = preprocessor.preprocess(img)
    return img_p, ocr_engine.run_ocr(img_p)


def _ocr_with_rotation(img: np.ndarray, check_fn) -> Tuple[np.ndarray, List[OcrBlock]]:
    """OCR con corrección automática de rotación 180°.
    Si el primer intento no supera check_fn, prueba rotado 180°."""
    img_p, blocks = _ocr_img(img)
    if not check_fn(blocks):
        rotated = cv2.rotate(img_p, cv2.ROTATE_180)
        blocks_rot = ocr_engine.run_ocr(rotated)
        if check_fn(blocks_rot):
            return rotated, blocks_rot
    return img_p, blocks


def _extract_frente_from_blocks(blocks: List[OcrBlock]) -> Dict:
    version = version_detector.detect_version(blocks)
    data = anchor_extractor.extract_frente(blocks, version)
    data["version_credencial"] = version
    return validator.validate_all(data)


def process_frente(img: np.ndarray) -> Dict:
    _, blocks = _ocr_with_rotation(img, _has_curp)
    return _extract_frente_from_blocks(blocks)


def process_reverso(img: np.ndarray) -> Dict:
    _, blocks = _ocr_with_rotation(img, _has_mrz)
    return mrz_parser.parse_mrz(blocks)


def process_full(frente_img: np.ndarray, reverso_img: Optional[np.ndarray] = None) -> Dict:
    """Procesa frente + reverso con detección automática de:
    - Páginas en orden invertido (reverso escaneado primero).
    - Imagen girada 180° dentro de cada página.
    Los bloques OCR se reutilizan para evitar pases dobles.
    """
    # ── Paso 1: OCR del frente candidato (con corrección de rotación) ──
    frente_p, frente_blocks = _ocr_with_rotation(frente_img, _has_curp)

    # ── Paso 2: Detección de orden invertido ──
    # Si el frente candidato no tiene CURP, el PDF puede estar al revés.
    reverso_p: Optional[np.ndarray] = None
    reverso_blocks: Optional[List[OcrBlock]] = None
    paginas_invertidas = False

    if not _has_curp(frente_blocks) and reverso_img is not None:
        # Intentar con la segunda página (con corrección de rotación)
        rev_p, rev_blocks = _ocr_with_rotation(reverso_img, _has_curp)
        if _has_curp(rev_blocks):
            # Las páginas estaban al revés: intercambiar
            # reverso_blocks ya calculados arriba = lo que era el frente
            reverso_p, reverso_blocks = frente_p, frente_blocks
            frente_p, frente_blocks = rev_p, rev_blocks
            paginas_invertidas = True
        else:
            # No se pudo determinar → procesar como venían
            reverso_p, reverso_blocks = rev_p, rev_blocks

    # ── Paso 3: Extraer datos del frente (bloques ya calculados) ──
    frente_data = _extract_frente_from_blocks(frente_blocks)

    # ── Paso 4: OCR del reverso (reutilizar bloques si ya los tenemos) ──
    reverso_data: Dict = {}
    if reverso_img is not None:
        if reverso_blocks is None:
            # Orden correcto: aún no hemos procesado el reverso
            _, reverso_blocks = _ocr_with_rotation(reverso_img, _has_mrz)
        reverso_data = mrz_parser.parse_mrz(reverso_blocks)

    # ── Paso 5: Enriquecer con datos del reverso ──
    mrz_line3 = reverso_data.get("ocr_linea3", "")
    # Fallback: si linea3 vacía, usar linea2 cuando tiene patrón de nombres (<<)
    # y NO empieza con 6 dígitos (que sería la línea de fecha)
    if not mrz_line3:
        l2 = reverso_data.get("ocr_linea2", "")
        if "<<" in l2 and not re.match(r'^\d{6}', l2):
            mrz_line3 = l2
    if mrz_line3:
        anchor_extractor.apply_mrz_name(frente_data, mrz_line3)

    if not frente_data.get("fecha_nacimiento") and reverso_data.get("mrz_fecha_nacimiento"):
        frente_data["fecha_nacimiento"] = reverso_data["mrz_fecha_nacimiento"]

    # Restituir la Ñ (el OCR la lee como N) antes de calcular el RFC: la Ñ
    # cambia el homoclave, así que debe corregirse en los apellidos/nombre primero.
    anchor_extractor.aplicar_correccion_enie(frente_data)

    cross = validator.cross_validate(frente_data, reverso_data)

    rfc = calcular_rfc(
        frente_data.get("apellido_paterno", ""),
        frente_data.get("apellido_materno", ""),
        frente_data.get("nombre", ""),
        frente_data.get("fecha_nacimiento", ""),
    )

    frente_out = {k: v for k, v in frente_data.items() if not k.startswith("_")}
    if rfc:
        frente_out["rfc"] = rfc

    return {
        "version_credencial": frente_data.get("version_credencial", "UNKNOWN"),
        "frente": frente_out,
        "reverso": reverso_data,
        "confianza": frente_data.get("_confianza", {}),
        "advertencias": frente_data.get("_advertencias", []),
        "cross_validacion": cross,
        "paginas_invertidas": paginas_invertidas,
    }

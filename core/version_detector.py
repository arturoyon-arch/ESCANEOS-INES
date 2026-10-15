from __future__ import annotations
import re
from typing import List
from core.ocr_engine import OcrBlock

VERSION_INE_MODERNA = "INE_MODERNA"
VERSION_IFE_INTERMEDIA = "IFE_INTERMEDIA"
VERSION_IFE_ANTIGUA = "IFE_ANTIGUA"
VERSION_UNKNOWN = "UNKNOWN"


def detect_version(blocks: List[OcrBlock]) -> str:
    # Normalizar: quitar espacios para tolerar que el OCR junte palabras
    # ("INSTTTUTOFEDERALELECTORAL", "INSTITUTONACIONALELECTORAL", etc.)
    full_text = " ".join(b.text.upper() for b in blocks)
    compact = re.sub(r'[^A-Z]', '', full_text)

    is_nacional = "NACIONAL" in compact
    is_federal = "FEDERAL" in compact

    if is_nacional and not is_federal:
        return VERSION_INE_MODERNA

    if is_federal:
        has_curp = any("CURP" in b.text.upper() for b in blocks)
        has_vigencia = any("VIGENCIA" in b.text.upper() for b in blocks)
        if has_curp or has_vigencia:
            return VERSION_IFE_INTERMEDIA
        return VERSION_IFE_ANTIGUA

    # Fallback: si tiene CURP asumimos INE moderna
    if any("CURP" in b.text.upper() for b in blocks):
        return VERSION_INE_MODERNA

    return VERSION_UNKNOWN

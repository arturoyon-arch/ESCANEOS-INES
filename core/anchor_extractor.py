"""
Extrae campos del frente de la INE/IFE.

Hallazgos de OCR real (imágenes ~660px, no 600 DPI):
  - Muchos pares etiqueta+valor vienen en el MISMO bloque:
    "CLAVE DE ELECTOR TRGNAR...", "CURP TOGA...", "SECCIÓN 0190", "VIGENCIA 2024".
  - MUNICIPIO/ESTADO impresos son CÓDIGOS numéricos; el nombre real está
    en la última línea del domicilio ("CADEREYTA JIMENEZ, N.L").
  - Vigencia puede ser un año único (IFE) o un rango YYYY-YYYY (INE moderna).

Estrategia:
  - Campos con patrón fijo (CURP, clave, fecha, CP): regex sobre todos los bloques.
  - Campos etiquetados: buscar valor en el mismo bloque → derecha → abajo.
  - Campos de texto libre (nombre, domicilio): anclas + stop estricto.
"""
from __future__ import annotations
import re
from typing import List, Optional, Dict, Tuple, Pattern
from core.ocr_engine import OcrBlock

# ──────────────────────────────────────────────
# Patrones de campos estructurados
# ──────────────────────────────────────────────
_CURP_RE   = re.compile(r'[A-Z]{4}\d{6}[HM][A-Z]{2}[B-DF-HJ-NP-TV-Z]{3}[A-Z0-9]\d')
_CLAVE_RE  = re.compile(r'[A-Z]{6}\d{8}[HM]\d{3}')
_FECHA_RE  = re.compile(r'(\d{2})[/\-\.](\d{2})[/\-\.](\d{4})')
# CP: 5 dígitos que NO formen parte de una racha más larga. Captura "67480"
# aunque venga pegado a la colonia ("...CADEREYTA67480").
_CP_RE     = re.compile(r'(?<!\d)(\d{5})(?!\d)')
_YEAR_RE   = re.compile(r'^(19|20)\d{2}$')
_VIGENCIA_RANGE_RE = re.compile(r'((?:19|20)\d{2})\s*[-/aA]+\s*((?:19|20)\d{2})')
_YEAR_ANY_RE = re.compile(r'\b((?:19|20)\d{2})\b')
_SEC_RE    = re.compile(r'\b(\d{3,4})\b')

_STRUCTURED_LENIENT = re.compile(r'^[A-Z0-9]{15,20}$')

_LABELS = {
    "NOMBRE", "DOMICILIO", "CURP", "CLAVE DE ELECTOR", "CLAVE ELECTOR",
    "FECHA DE NACIMIENTO", "FECHA NACIMIENTO", "FECHA DE NACIMIEN",
    "SECCIÓN", "SECCION", "SEXO", "VIGENCIA", "EMISIÓN", "EMISION",
    "AÑO DE REGISTRO", "ANO DE REGISTRO", "AÑO", "REGISTRO", "MUNICIPIO",
    "ESTADO", "LOCALIDAD", "INSTITUTO", "MÉXICO", "MEXICO", "CREDENCIAL",
    "ELECTORAL", "FEDERAL", "NACIONAL", "REGISTRO FEDERAL", "PARA VOTAR",
}

# Códigos de estado comunes en domicilio (abreviaturas)
_ESTADO_ABBR_RE = re.compile(
    r'\b(N\.?\s?L\.?|COAH\.?|TAMPS\.?|JAL\.?|D\.?\s?F\.?|CDMX|MEX\.?|'
    r'GTO\.?|VER\.?|PUE\.?|SON\.?|SIN\.?|CHIH\.?|MICH\.?|OAX\.?|'
    r'TAB\.?|YUC\.?|ZAC\.?|DGO\.?|AGS\.?|BC\.?|BCS\.?|CAMP\.?|'
    r'COL\.?|CHIS\.?|GRO\.?|HGO\.?|MOR\.?|NAY\.?|QRO\.?|QROO\.?|'
    r'SLP\.?|TLAX\.?)\b'
)

# Versión anclada al FINAL y SIN límite de palabra inicial: captura la
# abreviatura aunque venga pegada al municipio ("CADEREYTAJIMENEZNL" → NL).
# QROO/QRO/BCS antes que BC para evitar matches parciales.
_ESTADO_ABBR_END_RE = re.compile(
    r'(?:[^A-ZÑ]{0,3})?'   # hasta 3 chars ruidosos antes de la abreviatura
    r'(QROO|QRO|BCS|BC|COAH|TAMPS|CHIH|CHIS|CDMX|TLAX|CAMP|MICH|'
    r'AGS|DGO|GTO|VER|PUE|SON|SIN|OAX|TAB|YUC|ZAC|COL|GRO|HGO|'
    r'MOR|NAY|SLP|MEX|JAL|NL|DF)\.?[A-Z]{0,2}$'
)

# Códigos de estado ordenados de más largo a más corto (para rfind correcto)
_STATE_CODES = sorted(
    ['QROO','QRO','BCS','BC','COAH','TAMPS','CHIH','CHIS','CDMX','TLAX',
     'CAMP','MICH','AGS','DGO','GTO','VER','PUE','SON','SIN','OAX','TAB',
     'YUC','ZAC','COL','GRO','HGO','MOR','NAY','SLP','MEX','JAL','NL','DF'],
    key=len, reverse=True
)


# Versión compacta (solo letras) de las etiquetas, para matchear cuando el OCR
# pega las palabras: "AÑODEREGISTRO", "CLAVEDEELECTOR".
_COMPACT_LABELS = {re.sub(r'[^A-ZÑ]', '', l.upper()) for l in _LABELS}
_COMPACT_LABELS = {l for l in _COMPACT_LABELS if len(l) >= 6}

# Nombres de pila más comunes en México. Se usan para separar nombres compuestos
# que el OCR fusiona en un solo bloque (ej: "JUANANTONIO" → "JUAN ANTONIO").
# Ordenados de más largo a más corto para evitar matches parciales erróneos.
_NOMBRES_MX = {
    # Masculinos
    'JOSE','JUAN','JESUS','LUIS','CARLOS','MIGUEL','ANGEL','MANUEL',
    'PEDRO','FRANCISCO','JORGE','RAFAEL','ANTONIO','JAVIER','ALEJANDRO',
    'MARIO','ROBERTO','SERGIO','EDGAR','OMAR','OSCAR','ARTURO','ALBERTO',
    'VICTOR','PABLO','HECTOR','IVAN','GABRIEL','RAUL','RUBEN','ERNESTO',
    'ENRIQUE','GERARDO','ARMANDO','RODRIGO','DANIEL','FERNANDO','DAVID',
    'MARTIN','JULIAN','JONATHAN','KEVIN','CHRISTIAN','ALAN','DIEGO',
    'ANDRES','JAIME','JOEL','LEONEL','LEOPOLDO','CESAR','ERIK','ERICK',
    'IGNACIO','ISMAEL','LORENZO','MARCO','MOISES','NICOLAS','ROGELIO',
    'SAMUEL','SANTIAGO','TOMAS','ELIAS','EDUARDO','EMILIO','EFRAIN',
    'FELICIANO','GENARO','GUILLERMO','HILARIO','HOMERO','JACINTO',
    'JUVENTINO','LÁZARO','LAZARO','MACARIO','NABOR','NARCISO','PORFIRIO',
    'QUIRINO','RODRIGO','SEVERO','TIBURCIO','URBANO','ZEFERINO',
    # Femeninos
    'MARIA','ANA','ROSA','LAURA','DIANA','PATRICIA','SANDRA','CLAUDIA',
    'CAROLINA','ADRIANA','MONICA','JESSICA','ALEJANDRA','KAREN','BRENDA',
    'SILVIA','VERONICA','IRMA','LETICIA','BEATRIZ','ELIZABETH','YOLANDA',
    'MARTHA','NORMA','ELENA','GUADALUPE','SARA','SOFIA','NATALIA','PAOLA',
    'VALERIA','ALICIA','CRISTINA','LUCIA','TERESA','GABRIELA','GRACIELA',
    'MARISOL','ROCIO','BLANCA','ISABEL','LILIANA','LORENA','ERIKA',
    'GRISELDA','FABIOLA','WENDY','EVELYN','CINDY','VERENISE','CONCEPCION',
    'ESPERANZA','DOLORES','JULIA','OLGA','EMMA','REBECA','SUSANA',
    'ANGELICA','CELIA','DELIA','ESTELA','GLORIA','HILDA','INES','JUANA',
    'LEONOR','LOURDES','MARGARITA','NORA','OFELIA','PILAR','REYNA',
    'RUTH','SELENE','SONIA','VIRGINIA','XOCHITL','JOSEFINA','CATALINA',
    'CONSUELO','FLORENCIA','HERMINIA','HILARIA','REFUGIO','TRINIDAD',
    'PAULA','FERNANDA','ANDREA','XIMENA','PERLA','PRISCILA','VANESSA',
    'MIRIAM','IVONNE','IVETH','ARACELI','AZUCENA','BERENICE','DENISSE',
    'FLOR','LIDIA','MIRNA','NINFA','REBECA','YESENIA','ZULEMA',
    'IRENE','ELSA','NELLY','NELY','NORA','NIDIA','NYDIA','MAYRA','ALMA',
    'EDITH','JUDITH','MAGDALENA','RAQUEL','ESTHER','NANCY','BRISA','DORA',
    'IDALIA','LUDIVINA','MARLEN','YANETT','EULALIA','HORTENCIA','EVANGELINA',
}
# Precalcular lista ordenada más largo primero para la búsqueda de prefijo
_NOMBRES_MX_SORTED = sorted(_NOMBRES_MX, key=len, reverse=True)


def _split_nombre_compuesto(nombre: str) -> str:
    """Intenta separar un nombre compuesto fusionado por OCR.

    Solo separa cuando AMBAS partes son nombres conocidos:
    'JUANANTONIO' → 'JUAN' (conocido) + 'ANTONIO' (conocido) → 'JUAN ANTONIO'.
    Si el resto no es nombre conocido (ej: 'JOSEFINA' → 'JOSE'+'FINA'), no toca.
    """
    if ' ' in nombre or len(nombre) <= 4:
        return nombre
    up = nombre.upper()
    best = None
    best_len = 0
    for n in _NOMBRES_MX_SORTED:
        if len(n) <= best_len:
            break  # ya no puede mejorar (lista ordenada de más largo a más corto)
        if up.startswith(n) and len(up) > len(n):
            rest = up[len(n):]
            if rest in _NOMBRES_MX:
                best = (n, rest)
                best_len = len(n)
    return (best[0] + ' ' + best[1]) if best else nombre


# Apellidos/nombres mexicanos con Ñ. PaddleOCR lee la Ñ como N y la MRZ tampoco
# la codifica, así que se restituye por diccionario. Estos apellidos prácticamente
# nunca existen sin Ñ en México, por lo que la corrección es segura. La clave es
# la forma SIN tilde (tal como la entrega el OCR); el valor es la forma con Ñ.
_ENIE_MAP = {
    'PENA': 'PEÑA', 'MUNOZ': 'MUÑOZ', 'NUNEZ': 'NUÑEZ', 'IBANEZ': 'IBAÑEZ',
    'YBANEZ': 'YBAÑEZ', 'ZUNIGA': 'ZUÑIGA', 'PINA': 'PIÑA', 'ORDONEZ': 'ORDOÑEZ',
    'CASTANEDA': 'CASTAÑEDA', 'ACUNA': 'ACUÑA', 'TREVINO': 'TREVIÑO',
    'AVENDANO': 'AVENDAÑO', 'QUINONES': 'QUIÑONES', 'QUINONEZ': 'QUIÑONEZ',
    'PATINO': 'PATIÑO', 'BANUELOS': 'BAÑUELOS', 'SALDANA': 'SALDAÑA',
    'BRISENO': 'BRISEÑO', 'DUENAS': 'DUEÑAS', 'MAGANA': 'MAGAÑA',
    'OCANA': 'OCAÑA', 'CARRENO': 'CARREÑO', 'MONTANO': 'MONTAÑO',
    'MONTANEZ': 'MONTAÑEZ', 'CASTANON': 'CASTAÑON', 'PENALOZA': 'PEÑALOZA',
    'MUNIZ': 'MUÑIZ', 'NINO': 'NIÑO', 'YANEZ': 'YAÑEZ', 'INIGUEZ': 'IÑIGUEZ',
    'PENUELAS': 'PEÑUELAS', 'ESPANA': 'ESPAÑA', 'CAMPANA': 'CAMPAÑA',
    'PENAFLOR': 'PEÑAFLOR', 'BEGONA': 'BEGOÑA', 'RIANO': 'RIAÑO',
    'PENARANDA': 'PEÑARANDA', 'PENATE': 'PEÑATE', 'GRANA': 'GRAÑA',
    'PENAS': 'PEÑAS', 'VINAS': 'VIÑAS', 'NUNO': 'NUÑO', 'MINO': 'MIÑO',
}


def _restituir_enie(token: str) -> str:
    """Restituye la Ñ en un apellido/nombre que el OCR entregó con N."""
    return _ENIE_MAP.get(token.upper().strip(), token) if token else token


def aplicar_correccion_enie(frente: Dict) -> None:
    """Corrige la Ñ en apellidos y nombre (el OCR la lee como N) y reconstruye
    nombre_completo. Debe llamarse ANTES de calcular el RFC, porque la Ñ cambia
    el homoclave (Ñ=40 vs N=25 en la tabla SAT)."""
    for campo in ("apellido_paterno", "apellido_materno", "nombre"):
        val = frente.get(campo, "")
        if val:
            frente[campo] = " ".join(_restituir_enie(w) for w in val.split())
    frente["nombre_completo"] = " ".join(
        p for p in [frente.get("apellido_paterno", ""),
                    frente.get("apellido_materno", ""),
                    frente.get("nombre", "")] if p
    )


def _fecha_from_curp(curp: str) -> str:
    """Extrae fecha de nacimiento del CURP (posiciones 4-9 = AAMMDD).
    Funciona como fallback para INEs antiguas donde la etiqueta no es legible."""
    if len(curp) < 10:
        return ""
    try:
        yy = int(curp[4:6])
        mm = curp[6:8]
        dd = curp[8:10]
        import datetime
        current_yy = datetime.datetime.now().year % 100
        year = 1900 + yy if yy > current_yy else 2000 + yy
        if not (1 <= int(mm) <= 12 and 1 <= int(dd) <= 31):
            return ""
        return f"{dd}/{mm}/{year}"
    except (ValueError, IndexError):
        return ""


def _is_label(text: str) -> bool:
    upper = text.upper().strip()
    if len(text) < 40 and any(label in upper for label in _LABELS):
        return True
    # Texto pegado por el OCR: comparar versión compacta (solo letras)
    compact = re.sub(r'[^A-ZÑ]', '', upper)
    if compact and any(cl in compact for cl in _COMPACT_LABELS):
        return True
    return False


def _has_structured_data(text: str) -> bool:
    """Verdadero si el bloque contiene CURP o clave de elector.
    El chequeo laxo solo aplica a tokens SIN espacios que tengan una racha
    LARGA de dígitos (≥6 seguidos). La CURP/clave tienen 6-8 dígitos seguidos;
    una línea de domicilio a lo más tiene 5 (número de calle 517, CP 67480)."""
    up = text.upper().strip()
    if _CURP_RE.search(up) or _CLAVE_RE.search(up):
        return True
    if " " not in up:
        clean = re.sub(r'[^A-Z0-9]', '', up)
        if _STRUCTURED_LENIENT.match(clean) and re.search(r'\d{6,}', clean):
            return True
    return False


# ──────────────────────────────────────────────
# Búsqueda por regex global
# ──────────────────────────────────────────────

def _scan(blocks: List[OcrBlock], pattern: Pattern) -> str:
    for b in blocks:
        m = pattern.search(b.text.upper())
        if m:
            return m.group(1) if m.groups() else m.group()
    return ""


def _find_curp(blocks: List[OcrBlock]) -> str:
    return _scan(blocks, _CURP_RE)


def _find_clave_elector(blocks: List[OcrBlock]) -> str:
    return _scan(blocks, _CLAVE_RE)


def _find_fecha(blocks: List[OcrBlock]) -> str:
    for b in blocks:
        m = _FECHA_RE.search(b.text)
        if m:
            return f"{m.group(1)}/{m.group(2)}/{m.group(3)}"
    return ""


def _find_cp(blocks: List[OcrBlock]) -> str:
    for b in blocks:
        m = _CP_RE.search(b.text)
        if m:
            val = int(m.group(1))
            if 1000 <= val <= 99999:
                return m.group(1)
    return ""


# ──────────────────────────────────────────────
# Utilidades de ancla espacial
# ──────────────────────────────────────────────

def _find_label_block(blocks: List[OcrBlock], candidates: List[str]) -> Optional[OcrBlock]:
    # 1) Coincidencia directa por substring
    for block in blocks:
        upper = block.text.upper()
        for c in candidates:
            if c.upper() in upper:
                return block
    # 2) Coincidencia compacta (solo letras) para etiquetas pegadas por el OCR:
    #    "ANODEREGISTRO", "CLAVEDEELECTOR"
    comp_candidates = [re.sub(r'[^A-ZÑ]', '', c.upper()) for c in candidates]
    comp_candidates = [c for c in comp_candidates if len(c) >= 5]
    for block in blocks:
        comp = re.sub(r'[^A-ZÑ]', '', block.text.upper())
        if comp and any(c in comp for c in comp_candidates):
            return block
    return None


def _blocks_below(anchor: OcrBlock, blocks: List[OcrBlock],
                  max_lines: int = 3, x_tolerance: float = 1.5) -> List[OcrBlock]:
    results = []
    anchor_width = max(anchor.width, 80)
    # Usar el centro de la etiqueta como referencia: las etiquetas de la INE
    # tienen bounding boxes altos que solapan con la primera línea del valor.
    below_threshold = anchor.y1 + anchor.height * 0.5
    for b in blocks:
        if b is anchor:
            continue
        if b.y1 < below_threshold:
            continue
        if b.y1 > anchor.y2 + anchor.height * 8:
            continue
        overlap_x = (min(b.x2, anchor.x2 + int(anchor_width * x_tolerance)) -
                     max(b.x1, anchor.x1 - 20))
        if overlap_x > 0:
            results.append(b)
    results.sort(key=lambda b: (b.y1, b.x1))
    return results[:max_lines]


def _blocks_below_text_only(anchor: OcrBlock, blocks: List[OcrBlock],
                             max_lines: int = 4) -> List[OcrBlock]:
    """Bloques de texto libre debajo del ancla. Para al encontrar una etiqueta
    conocida o datos estructurados (CURP/clave)."""
    all_below = _blocks_below(anchor, blocks, max_lines=max_lines * 3, x_tolerance=2.0)
    results = []
    for b in all_below:
        if _is_label(b.text):
            break
        if _has_structured_data(b.text):
            break
        results.append(b)
        if len(results) >= max_lines:
            break
    return results


def _block_to_right(anchor: OcrBlock, blocks: List[OcrBlock],
                    y_tolerance: float = 0.6) -> Optional[OcrBlock]:
    anchor_h = max(anchor.height, 15)
    candidates = []
    for b in blocks:
        if b is anchor:
            continue
        if b.x1 <= anchor.x2:
            continue
        overlap = min(b.y2, anchor.y2) - max(b.y1, anchor.y1)
        if overlap >= anchor_h * y_tolerance:
            candidates.append(b)
    return min(candidates, key=lambda b: b.x1) if candidates else None


def _strip_label(text: str, label_variants: List[str]) -> str:
    """Quita la(s) palabra(s) de etiqueta del texto del bloque."""
    up = text.upper()
    for lv in sorted(label_variants, key=len, reverse=True):
        up = up.replace(lv.upper(), " ")
    return up.strip(" :.-\t")


def _labeled_value(blocks: List[OcrBlock], label_variants: List[str],
                   pattern: Optional[Pattern] = None,
                   max_below: int = 2) -> str:
    """
    Busca el valor de un campo etiquetado en este orden:
      1. Mismo bloque que la etiqueta (quitando la etiqueta).
      2. Bloque a la derecha.
      3. Bloques debajo.
    Si se da `pattern`, extrae solo lo que matchee; si no, devuelve el texto.
    """
    label_block = _find_label_block(blocks, label_variants)
    if not label_block:
        return ""

    texts: List[str] = []
    same = _strip_label(label_block.text, label_variants)
    if same:
        texts.append(same)
    right = _block_to_right(label_block, blocks)
    if right:
        texts.append(right.text)
    for b in _blocks_below(label_block, blocks, max_lines=max_below):
        texts.append(b.text)

    for t in texts:
        if pattern:
            m = pattern.search(t.upper())
            if m:
                return m.group(1) if m.groups() else m.group()
        else:
            if t.strip():
                return t.strip()
    return ""


# ──────────────────────────────────────────────
# Campos etiquetados específicos
# ──────────────────────────────────────────────

def _find_sexo(blocks: List[OcrBlock]) -> str:
    # "SEXO M" / "SEXO H" en cualquier bloque
    for b in blocks:
        m = re.search(r'\bSEXO\s*[:\-]?\s*([MFH])\b', b.text.upper())
        if m:
            return m.group(1)
    # Etiqueta SEXO + valor a la derecha/abajo
    val = _labeled_value(blocks, ["SEXO"], re.compile(r'\b([MFH])\b'))
    return val


def _find_seccion(blocks: List[OcrBlock]) -> str:
    label = _find_label_block(blocks, ["SECCIÓN", "SECCION"])
    if not label:
        return ""
    texts = [_strip_label(label.text, ["SECCIÓN", "SECCION"])]
    right = _block_to_right(label, blocks)
    if right:
        texts.append(right.text)
    for b in _blocks_below(label, blocks, max_lines=2):
        texts.append(b.text)
    for t in texts:
        for m in _SEC_RE.finditer(t):
            val = m.group(1)
            if not _YEAR_RE.match(val):
                return val
    return ""


def _find_vigencia(blocks: List[OcrBlock]) -> str:
    label = _find_label_block(blocks, ["VIGENCIA"])
    texts: List[str] = []
    if label:
        texts.append(_strip_label(label.text, ["VIGENCIA"]))
        right = _block_to_right(label, blocks)
        if right:
            texts.append(right.text)
        for b in _blocks_below(label, blocks, max_lines=2):
            texts.append(b.text)
    # Primero buscar rango YYYY-YYYY
    for t in texts:
        m = _VIGENCIA_RANGE_RE.search(t)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    # Luego año único (IFE)
    for t in texts:
        m = _YEAR_ANY_RE.search(t)
        if m:
            return m.group(1)
    # Fallback global: rango en cualquier bloque
    for b in blocks:
        m = _VIGENCIA_RANGE_RE.search(b.text)
        if m:
            return f"{m.group(1)}-{m.group(2)}"
    return ""


def _find_anio_emision(blocks: List[OcrBlock]) -> Tuple[str, str]:
    anio, emision = "", ""
    label = _find_label_block(blocks, ["AÑO DE REGISTRO", "ANO DE REGISTRO", "REGISTRO"])
    if label:
        texts = [_strip_label(label.text, ["AÑO DE REGISTRO", "ANO DE REGISTRO", "REGISTRO"])]
        right = _block_to_right(label, blocks)
        if right:
            texts.append(right.text)
        for b in _blocks_below(label, blocks, max_lines=2):
            texts.append(b.text)
        # El INE moderno imprime "AÑO 2002 03" → el OCR lo pega como "200203"
        # (año de registro 2002 + número de emisión 03).
        for t in texts:
            m = re.search(r'((?:19|20)\d{2})(\d{0,2})', t)
            if m:
                anio = m.group(1)
                if m.group(2):
                    emision = m.group(2)
                break
    # Emisión con etiqueta separada (algunas IFE/INE la tienen aparte)
    if not emision:
        em = _labeled_value(blocks, ["EMISIÓN", "EMISION"], re.compile(r'\b(\d{1,4})\b'))
        if em:
            emision = em
    return anio, emision


# ──────────────────────────────────────────────
# Domicilio, municipio y estado
# ──────────────────────────────────────────────

# Secuencias conocidas que el OCR funde (aplicar antes de split por keywords)
_DOM_REPLACE = [
    ("SINNOMBRE", "SIN NOMBRE"),
    ("SINNUMERO", "S/N"),
    ("SINNUM",    "S/N"),
]

# Keywords de dirección que, cuando aparecen pegados a texto anterior, requieren espacio.
# SANTA/SANTO deben ir ANTES de SAN para evitar que "SAN" capture el inicio de "SANTA".
_DOM_KW_RE = re.compile(
    r"(?<=[A-ZÁÉÍÓÚÑ0-9])"
    r"(?=FRACCIONAMIENTO|FRACC|CARRETERA|BOULEVARD|BLVD|AVENIDA|"
    r"CALLEJON|CJON|PRIVADA|PRIV|COLONIA|LOCALIDAD|"
    r"MANZANA|MANZ|EJIDO|RANCHO|BARRIO|ESQUINA|ESQ|CALLE|SANTA|SANTO|SAN)",
    re.IGNORECASE,
)

# Abreviaciones/palabras clave al inicio de línea o tras espacio, pegadas al siguiente token.
# EJIDO/RANCHO/BARRIO aquí (además de en _DOM_KW_RE) para el caso en que vienen
# inmediatamente después de LOC/COL sin otra letra antes que active el lookbehind.
_DOM_SHORT_RE = re.compile(
    r"((?:^|\s)(?:COL|LOC|NUM|AV|INT|EXT|LT|KM|MANZ|EJIDO|RANCHO|BARRIO))([A-ZÁÉÍÓÚÑ\d])",
    re.IGNORECASE,
)


def _format_dom_line(line: str) -> str:
    """Inserta espacios donde el OCR fundió palabras en una línea de calle/colonia.

    Solo se aplica a las líneas de calle — NO a la línea de municipio/estado,
    porque 'C' al inicio de municipios como 'CADEREYTA' no es la abreviatura CALLE.
    """
    s = line.upper().strip()
    if not s:
        return s

    # 1. 'C' como abreviación de CALLE al inicio, pero NO cuando el inicio forma
    #    una abreviación multi-letra conocida: COL (colonia), CJON (callejón),
    #    CARR (carretera), CALLE (nombre completo).
    #    "CHIDALGO" → "C HIDALGO", pero "COLCENTRO" queda intacto para el paso 5.
    s = re.sub(r"^C(?!OL|JON|ARR|ALLE)([A-ZÁÉÍÓÚÑ])", r"C \1", s)

    # 2. Secuencias de fusión conocidas
    for old, new in _DOM_REPLACE:
        s = s.replace(old, new)

    # 3. "SIN" pegado al final de otra palabra: "NOMBRESIN" → "NOMBRE SIN"
    s = re.sub(r"(?<=[A-ZÁÉÍÓÚÑ])(SIN)(?=[^A-ZÁÉÍÓÚÑ]|$)", r" \1", s)

    # 4. Keywords largos pegados a texto anterior
    s = _DOM_KW_RE.sub(" ", s)

    # 5. Abreviaciones cortas al inicio o tras espacio
    s = _DOM_SHORT_RE.sub(lambda m: m.group(1) + " " + m.group(2), s)

    # 6. Prefijo geográfico al inicio de una palabra compuesta.
    #    SANTA/SANTO antes de SAN para evitar match parcial: "SANTACRUZ" → "SANTA CRUZ"
    s = re.sub(r"(?:^|(?<=\s))(SANTA|SANTO|SAN)([A-ZÁÉÍÓÚÑ]{3,})", r"\1 \2", s)

    # 7. "SIN" suelto no seguido de NOMBRE = sin número → "S/N"
    s = re.sub(r"\bSIN\b(?!\s*NOMBRE)", "S/N", s)

    # 8. Letras pegadas a dígitos de número de calle: "HIDALGO517" → "HIDALGO 517"
    s = re.sub(r"(?<=[A-ZÁÉÍÓÚÑ])(\d{1,4})(?!\d)", r" \1", s)

    # 9. Dígitos pegados a sufijos de orientación conocidos: "310PTE" → "310 PTE"
    #    Solo sufijos cortos para no romper "9DEAGOSTO" ni años.
    s = re.sub(r"(?<=\d)(PTE|OTE|NTE|SUR|BIS|INT|EXT|[A-ZÁÉÍÓÚÑ])(?=[^A-ZÁÉÍÓÚÑ\d]|$)",
               r" \1", s)

    return re.sub(r" {2,}", " ", s).strip()


def _split_municipio_estado(last_line: str) -> Tuple[str, str]:
    """
    Última línea del domicilio: "CADEREYTA JIMENEZ, N.L" o "CADEREYTAJIMENEZ.N.L".
    Devuelve (municipio, estado).
    """
    line = last_line.strip()
    up = line.upper()
    # 1) Abreviatura con límites de palabra ("CADEREYTA JIMENEZ, N.L.")
    m = _ESTADO_ABBR_RE.search(up)
    if m:
        estado = re.sub(r'[^A-ZÑ]', '', m.group(1))  # quitar puntos y espacios
        municipio = line[:m.start()].strip(" ,.")
        return municipio, estado
    # 2) Abreviatura pegada al final, posiblemente con puntos/espacios o ruido OCR.
    #    Trabajamos sobre la versión SOLO-LETRAS para tolerar "JUAREZN.L",
    #    "CADEREYTAJIMENEZNL", "MONTERREYANLE", etc.
    clean = re.sub(r'[^A-ZÑ]', '', up)
    tail = clean[-7:]
    for code in _STATE_CODES:  # más largo primero (rfind evita falsos cortes)
        pos = tail.rfind(code)
        if pos != -1:
            abs_pos = len(clean) - len(tail) + pos
            muni_raw = clean[:abs_pos]
            # Eliminar vocal de ruido OCR tras 'Y' ("MONTERREYA" → "MONTERREY",
            # producto de que la coma+espacio del separador se leyó como vocal).
            if len(muni_raw) >= 2 and muni_raw[-1] in 'AEI' and muni_raw[-2] == 'Y':
                muni_raw = muni_raw[:-1]
            if muni_raw:   # evitar municipio vacío (sería falso positivo)
                return muni_raw, code
    # 3) Separar por coma
    if "," in line:
        parts = [p.strip() for p in line.split(",") if p.strip()]
        if len(parts) >= 2:
            return parts[-2], parts[-1]
    return line, ""


# ──────────────────────────────────────────────
# Extractor principal del frente
# ──────────────────────────────────────────────

def extract_frente(blocks: List[OcrBlock], version: str) -> Dict[str, str]:
    result: Dict[str, str] = {
        "nombre_completo": "", "apellido_paterno": "", "apellido_materno": "",
        "nombre": "", "sexo": "", "fecha_nacimiento": "", "curp": "",
        "domicilio": "", "codigo_postal": "", "municipio": "", "estado": "",
        "clave_elector": "", "seccion": "", "anio_registro": "",
        "emision": "", "vigencia": "",
    }

    # ── Campos estructurados (regex global) ──
    result["curp"]             = _find_curp(blocks)
    result["clave_elector"]    = _find_clave_elector(blocks)
    result["fecha_nacimiento"] = _find_fecha(blocks)
    result["codigo_postal"]    = _find_cp(blocks)

    # Fallback fecha: derivar del CURP (INEs antiguas no tienen etiqueta legible)
    if not result["fecha_nacimiento"] and result["curp"]:
        result["fecha_nacimiento"] = _fecha_from_curp(result["curp"])

    # ── Campos etiquetados ──
    result["sexo"]     = _find_sexo(blocks)
    # Fallback: derivar sexo del CURP (posición 11: H=hombre, M=mujer)
    if not result["sexo"] and len(result["curp"]) >= 11 and result["curp"][10] in ("H", "M"):
        result["sexo"] = result["curp"][10]
    result["vigencia"] = _find_vigencia(blocks)
    result["seccion"]  = _find_seccion(blocks)
    anio, emision = _find_anio_emision(blocks)
    result["anio_registro"] = anio
    result["emision"]       = emision

    # ── NOMBRE (texto libre) ──
    label_nombre = _find_label_block(blocks, ["NOMBRE"])
    if label_nombre:
        name_blocks = _blocks_below_text_only(label_nombre, blocks, max_lines=3)
        lines = [b.text for b in name_blocks]
        if lines:
            result["apellido_paterno"] = lines[0] if len(lines) > 0 else ""
            result["apellido_materno"] = lines[1] if len(lines) > 1 else ""
            nombre_raw = " ".join(lines[2:]) if len(lines) > 2 else ""
            # Si el OCR fusionó un nombre compuesto (JUANANTONIO → JUAN ANTONIO)
            result["nombre"] = _split_nombre_compuesto(nombre_raw)
            result["nombre_completo"] = " ".join(
                [result["apellido_paterno"], result["apellido_materno"], result["nombre"]]
            ).strip()

    # ── DOMICILIO (texto libre) ──
    label_dom = _find_label_block(blocks, ["DOMICILIO"])
    dom_lines: List[str] = []
    if label_dom:
        # Recopilar todos los bloques bajo DOMICILIO hasta datos estructurados.
        # NO parar en etiquetas: "CALLE SIN NOMBRE" contiene "NOMBRE" y dispararía
        # un falso positivo.  El límite real es el primer bloque con CURP/clave.
        all_below = _blocks_below(label_dom, blocks, max_lines=14, x_tolerance=2.0)
        raw_lines: List[str] = []
        for b in all_below:
            if _has_structured_data(b.text):
                break
            t = b.text.strip()
            if t:
                raw_lines.append(t)

        # Localizar la línea de municipio/estado: la ÚLTIMA con código de estado.
        # Buscamos en orden inverso porque el municipio es la última línea del
        # domicilio, y evitamos que "SIN NOMBRE" (calle) se confunda con Sinaloa.
        # La línea candidata debe tener al menos 5 chars para descartar ruido corto.
        muni_idx: Optional[int] = None
        for i in range(len(raw_lines) - 1, -1, -1):
            t = raw_lines[i]
            if len(re.sub(r'[^A-ZÑ]', '', t.upper())) < 5:
                continue  # línea demasiado corta (ruido o número solo)
            _, edo = _split_municipio_estado(t)
            if edo:
                muni_idx = i
                break

        if muni_idx is not None:
            # Tomar hasta 2 líneas previas no-ruido + la línea de municipio
            prev = [t for t in raw_lines[:muni_idx] if len(re.sub(r'[^A-ZÑ0-9]', '', t.upper())) >= 4]
            street_lines = prev[-2:]
            muni_line    = raw_lines[muni_idx]
            dom_lines    = street_lines + [muni_line]   # para _split_municipio_estado
            # Formatear solo las líneas de calle (no la de municipio — "C" de CADEREYTA
            # no es la abreviación CALLE). La línea de muni se reconstruye tras parsear.
            fmt_streets = [_format_dom_line(l) for l in street_lines]
            muni_str, edo_str = _split_municipio_estado(muni_line)
            # Aplicar prefijo geográfico al nombre del municipio para el display
            # (SAN PEDRO GARZA GARCIA, no SANPEDRO GARZAGARCIA).
            muni_fmt = re.sub(r"(?:^|(?<=\s))(SANTA|SANTO|SAN)([A-ZÁÉÍÓÚÑ]{3,})",
                              r"\1 \2", muni_str.upper())
            fmt_muni = f"{muni_fmt}, {edo_str}" if muni_str and edo_str else muni_line
            result["domicilio"] = " ".join(fmt_streets + [fmt_muni])
        else:
            # Fallback: primeras 3 líneas que no sean etiqueta pura
            dom_lines = [t for t in raw_lines[:6] if t and not _is_label(t)][:3]
            result["domicilio"] = " ".join(_format_dom_line(l) for l in dom_lines)

    # ── MUNICIPIO y ESTADO desde la última línea del domicilio ──
    if dom_lines:
        municipio, estado = _split_municipio_estado(dom_lines[-1])
        result["municipio"] = municipio
        result["estado"]    = estado
        # Quitar CP de la cadena de domicilio para limpieza (aunque venga pegado)
        result["domicilio"] = re.sub(r'(?<!\d)\d{5}(?!\d)', '', result["domicilio"]).strip()

    return result


# ──────────────────────────────────────────────
# Corrección de nombre usando MRZ línea 3
# ──────────────────────────────────────────────

def _casi_iguales(a: str, b: str) -> bool:
    """True si dos cadenas del mismo largo difieren en ≤1 carácter.
    Sirve para detectar un error puntual de OCR (una letra mal leída)."""
    if len(a) != len(b) or not a:
        return False
    return sum(1 for x, y in zip(a, b) if x != y) <= 1


def _segmentar_por_mrz(merged: str, tokens: List[str]) -> str:
    """Separa un nombre fundido del frente usando los tokens del MRZ como guía
    de corte, conservando las letras del frente (la MRZ puede venir truncada a
    30 chars). Ej: "CRISTINAREBEOA" + [CRISTINA, REBE] → "CRISTINA REBEOA".

    Corta por longitud de cada token salvo el último (que en la MRZ puede estar
    incompleto): todo lo que reste del frente se asigna al último nombre.
    """
    if len(tokens) < 2:
        return merged
    up = merged
    segs: List[str] = []
    i = 0
    for t in tokens[:-1]:
        seg = up[i:i + len(t)]
        if not seg:
            break
        segs.append(seg)
        i += len(t)
    if i < len(up):
        segs.append(up[i:])
    return " ".join(segs) if len(segs) > 1 else merged


def apply_mrz_name(frente: Dict, mrz_line3: str) -> None:
    """Reconcilia el nombre del frente con la MRZ.

    El frente (texto grande, OCR limpio) es la fuente PRINCIPAL. La MRZ solo:
      - rellena un apellido/nombre que el frente no logró leer, y
      - marca una advertencia cuando frente y MRZ difieren (para revisión).
    La MRZ NO sobrescribe al frente: su tipografía pequeña genera errores
    (ej. añade letras), así que confiar ciegamente en ella corrompe el dato.
    """
    if not mrz_line3:
        return
    parts = mrz_line3.split("<<")
    if not parts:
        return
    apellidos_raw = parts[0].replace("<", " ").strip()
    nombre_raw    = " ".join(p.replace("<", " ").strip() for p in parts[1:] if p).strip()

    # Filtrar tokens de 1 carácter: son rellenos '<' que el OCR leyó como letra
    # (p.ej. "NORMA<IRENE<<K<<" → "NORMA IRENE K"). Ningún nombre o apellido real
    # tiene un componente de una sola letra, así que se descartan con seguridad.
    apellidos_raw = " ".join(t for t in apellidos_raw.split() if len(t) > 1)
    nombre_raw    = " ".join(t for t in nombre_raw.split() if len(t) > 1)

    apellidos = apellidos_raw.split()
    mrz_paterno = apellidos[0] if len(apellidos) > 0 else ""
    mrz_materno = apellidos[1] if len(apellidos) > 1 else ""

    warnings = frente.setdefault("_advertencias", [])

    def _reconcile(field: str, mrz_val: str, etiqueta: str) -> None:
        front_val = frente.get(field, "").strip()
        if not front_val and mrz_val:
            # Campo vacío en frente: usar MRZ
            frente[field] = mrz_val
        elif front_val and mrz_val:
            front_nospace = front_val.replace(" ", "")
            mrz_nospace   = mrz_val.replace(" ", "")
            if front_nospace == mrz_nospace:
                # Mismas letras: si el frente no tiene espacios y el MRZ sí,
                # el OCR fundió el nombre. Usar el MRZ que tiene separación ICAO.
                if " " not in front_val and " " in mrz_val:
                    frente[field] = mrz_val
            elif " " not in front_val and " " in mrz_val:
                # El frente vino fundido. Reconstruir la separación.
                if _casi_iguales(front_nospace, mrz_nospace):
                    # Mismo largo, ≤1 letra distinta: la MRZ está completa y trae
                    # la letra correcta → usarla ("CRISTINAREBEOA"→"CRISTINA REBECA").
                    frente[field] = mrz_val
                else:
                    # La MRZ puede venir truncada (línea de 30 chars). Usarla solo
                    # como guía de corte, conservando las letras del frente.
                    seg = _segmentar_por_mrz(front_val, mrz_val.split())
                    if seg != front_val:
                        frente[field] = seg
                    else:
                        warnings.append(
                            f"{etiqueta}: frente «{front_val}» ≠ MRZ «{mrz_val}» — verificar")
            else:
                # Letras distintas: posible error de MRZ (K en lugar de <, etc.)
                warnings.append(f"{etiqueta}: frente «{front_val}» ≠ MRZ «{mrz_val}» — verificar")

    _reconcile("apellido_paterno", mrz_paterno, "Apellido paterno")
    _reconcile("apellido_materno", mrz_materno, "Apellido materno")
    _reconcile("nombre", nombre_raw, "Nombre")

    frente["nombre_completo"] = " ".join(
        p for p in [frente.get("apellido_paterno", ""),
                    frente.get("apellido_materno", ""),
                    frente.get("nombre", "")] if p
    )

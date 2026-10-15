"""
RFC persona física — algoritmo SAT oficial.
Inputs: apellido_paterno, apellido_materno (puede estar vacío), nombre(s), fecha_nac DD/MM/YYYY
Output: RFC 13 caracteres  (4 clave + 6 fecha + 2 homoclave + 1 dígito verificador)
"""
from __future__ import annotations
import re
import unicodedata

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_PARTICLES = frozenset({
    'DA','DAS','DE','DEL','DER','DI','DIE','DD',
    'EL','LA','LAS','LOS','LE','LES',
    'MAC','MC','VAN','VON','Y',
})

_COMPOUND_PREFIXES = frozenset({'JOSE', 'MARIA', 'MA', 'J'})

_INCONVENIENT = frozenset({
    'BACA','BAKA','BUEI','BUEY','CACA','CACO','CAGA','CAGO','CAKA','CAKO',
    'COGE','COGI','COJA','COJE','COJI','COJO','COLA','CULO','FALO','FETO',
    'GETA','GUEI','GUEY','JETA','JOTO','KACA','KACO','KAGA','KAGO','KAKA',
    'KAKO','KOGE','KOGI','KOJA','KOJE','KOJI','KOJO','KOKA','KOKO','KOKU',
    'LELA','LELO','LOCA','LOCO','LOKA','LOKO','MAME','MAMO','MEAR','MEAS',
    'MEON','MIAR','MION','MOCO','MOKO','MULA','MULO','NACA','NACO','PEDA',
    'PEDO','PENE','PIPI','PITO','POPO','PUTA','PUTO','QULO','RATA','ROBA',
    'ROBE','ROBO','RUIN','SENO','TETA','VACA','VAGA','VAGO','VAKA','VUEI',
    'VUEY','WUEI','WUEY',
})

# Tabla SAT para homoclave: cada carácter se codifica como DOS dígitos.
# (codificación oficial de tarjetas perforadas; salta 20, 30, etc.)
_HOM_2DIGIT: dict[str, str] = {
    '0': '00', '1': '01', '2': '02', '3': '03', '4': '04',
    '5': '05', '6': '06', '7': '07', '8': '08', '9': '09',
    '&': '10',
    'A': '11', 'B': '12', 'C': '13', 'D': '14', 'E': '15',
    'F': '16', 'G': '17', 'H': '18', 'I': '19',
    'J': '21', 'K': '22', 'L': '23', 'M': '24', 'N': '25',
    'O': '26', 'P': '27', 'Q': '28', 'R': '29',
    'S': '32', 'T': '33', 'U': '34', 'V': '35',
    'W': '36', 'X': '37', 'Y': '38', 'Z': '39',
    'Ñ': '40', ' ': '00',
}

# Tabla de 34 caracteres para el resultado de la homoclave (sin 0 ni O)
_HOM_TABLE = '123456789ABCDEFGHIJKLMNPQRSTUVWXYZ'

# Tabla para dígito verificador (oficial: …N=23, &=24, O=25…Z=36, Ñ=37)
_VER_VALS: dict[str, int] = {str(d): d for d in range(10)}
_VER_VALS.update({
    'A': 10, 'B': 11, 'C': 12, 'D': 13, 'E': 14, 'F': 15,
    'G': 16, 'H': 17, 'I': 18, 'J': 19, 'K': 20, 'L': 21,
    'M': 22, 'N': 23, '&': 24, 'O': 25, 'P': 26, 'Q': 27,
    'R': 28, 'S': 29, 'T': 30, 'U': 31, 'V': 32, 'W': 33,
    'X': 34, 'Y': 35, 'Z': 36, 'Ñ': 37, ' ': 38,
})

_VOWELS = frozenset('AEIOU')

# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

def _normalize(s: str) -> str:
    """Uppercase + eliminar acentos, conservando Ñ."""
    s = s.upper().strip()
    # Proteger Ñ antes de NFD (NFD la descompone en N + combining tilde)
    s = s.replace('Ñ', '\x00').replace('ñ', '\x00')
    s = ''.join(
        c for c in unicodedata.normalize('NFD', s)
        if unicodedata.category(c) != 'Mn'
    )
    s = s.replace('\x00', 'Ñ')
    # Dejar solo letras, Ñ, dígitos y espacios
    return re.sub(r'[^A-ZÑ0-9 ]', '', s)


def _clean_words(s: str) -> list[str]:
    """Normalizar y eliminar partículas."""
    words = _normalize(s).split()
    return [w for w in words if w not in _PARTICLES]


# ---------------------------------------------------------------------------
# Clave de 4 letras
# ---------------------------------------------------------------------------

def _clave4(ap_words: list[str], am_words: list[str], nom_words: list[str]) -> str:
    ap1 = ap_words[0] if ap_words else ''
    if not ap1:
        return 'XXXX'

    l1 = ap1[0]
    l2 = next((c for c in ap1[1:] if c in _VOWELS), 'X')
    l3 = am_words[0][0] if am_words else 'X'

    # Nombre: saltar prefijos compuestos (JOSE, MARIA, etc.)
    nom_word = nom_words[0] if nom_words else 'X'
    if len(nom_words) > 1 and nom_words[0] in _COMPOUND_PREFIXES:
        nom_word = nom_words[1]
    l4 = nom_word[0] if nom_word else 'X'

    clave = l1 + l2 + l3 + l4
    if clave in _INCONVENIENT:
        clave = clave[0] + 'X' + clave[2:]
    return clave


# ---------------------------------------------------------------------------
# Homoclave (2 letras) — algoritmo SAT
# ---------------------------------------------------------------------------

def _homoclave(nombre_completo: str) -> str:
    """Algoritmo SAT: se antepone un espacio, cada carácter se vuelve 2 dígitos,
    y se suman los productos (par de dígitos) × (dígito siguiente).
    `nombre_completo` = 'PATERNO MATERNO NOMBRES' normalizado (CON partículas)."""
    nombre = ' ' + nombre_completo
    s = ''.join(_HOM_2DIGIT.get(c, '00') for c in nombre)

    total = 0
    for i in range(len(s) - 1):
        total += int(s[i:i + 2]) * int(s[i + 1])

    rem = total % 1000
    return _HOM_TABLE[rem // 34] + _HOM_TABLE[rem % 34]


# ---------------------------------------------------------------------------
# Dígito verificador
# ---------------------------------------------------------------------------

def _digito_verificador(rfc12: str) -> str:
    """Calcula el dígito verificador del RFC de 12 caracteres."""
    weights = list(range(13, 1, -1))  # 13, 12, 11, …, 2
    total = sum(_VER_VALS.get(c, 0) * w for c, w in zip(rfc12, weights))
    rem = 11 - (total % 11)
    if rem == 11:
        return '0'
    if rem == 10:
        return 'A'
    return str(rem)


# ---------------------------------------------------------------------------
# Función principal
# ---------------------------------------------------------------------------

def calcular_rfc(
    apellido_paterno: str,
    apellido_materno: str | None,
    nombres: str,
    fecha_nac: str,          # DD/MM/YYYY
) -> str | None:
    """
    Retorna el RFC de 13 caracteres o None si los datos son insuficientes.
    """
    if not apellido_paterno or not nombres or not fecha_nac:
        return None

    ap_words = _clean_words(apellido_paterno)
    am_words = _clean_words(apellido_materno) if apellido_materno else []
    nom_words = _clean_words(nombres)

    if not ap_words:
        return None

    # Clave 4 letras
    clave = _clave4(ap_words, am_words, nom_words)

    # Fecha AAMMDD — validar estrictamente: con año de 2 dígitos o texto no
    # numérico se generaría un RFC truncado/basura (la fecha puede venir
    # editada a mano por el operador antes de "Regenerar RFC").
    try:
        parts = fecha_nac.split('/')
        day   = parts[0].zfill(2)
        month = parts[1].zfill(2)
        year  = parts[2]
        if not (day.isdigit() and month.isdigit()
                and year.isdigit() and len(year) == 4
                and 1 <= int(day) <= 31 and 1 <= int(month) <= 12):
            return None
        date6 = year[2:] + month + day
    except (IndexError, ValueError):
        return None

    rfc10 = clave + date6

    # Homoclave: usa el nombre completo normalizado CON partículas
    nombre_completo = _normalize(
        f"{apellido_paterno} {apellido_materno or ''} {nombres}"
    )
    nombre_completo = re.sub(r'\s+', ' ', nombre_completo).strip()
    hom2 = _homoclave(nombre_completo)

    rfc12 = rfc10 + hom2
    ver   = _digito_verificador(rfc12)

    return rfc12 + ver

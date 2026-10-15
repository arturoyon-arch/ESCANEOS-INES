# -*- mode: python ; coding: utf-8 -*-
import sys
sys.setrecursionlimit(5000)

from PyInstaller.utils.hooks import collect_all, copy_metadata

# ── Recolectar TODO de paddle/paddleocr/paddlex ───────────────────────────
paddle_datas,    paddle_bins,    paddle_hidden    = collect_all('paddle')
paddleocr_datas, paddleocr_bins, paddleocr_hidden = collect_all('paddleocr')
paddlex_datas,   paddlex_bins,   paddlex_hidden   = collect_all('paddlex')

# paddleocr._models importa de forma ansiosa módulos pesados (chart parsing,
# doc-vlm) que arrastran matplotlib y otras libs. Recolectarlas completas para
# que el .exe no falle con "No module named ...".
mpl_datas, mpl_bins, mpl_hidden = collect_all('matplotlib')

# ── Metadatos de paquete (importlib.metadata) ─────────────────────────────
# PaddleX/PaddleOCR verifican dependencias con importlib.metadata.version() al
# crear el pipeline. Si falta el .dist-info de cualquiera -> "dependency error
# during pipeline creation". Solución determinista: empaquetar la metadata de
# TODOS los paquetes instalados, para que el frozen vea lo mismo que dev.
import importlib.metadata as _ilm
meta = []
_seen = set()
for _dist in _ilm.distributions():
    try:
        _name = _dist.metadata['Name']
    except Exception:
        _name = None
    if not _name or _name in _seen:
        continue
    _seen.add(_name)
    try:
        meta += copy_metadata(_name)
    except Exception:
        pass

added_datas = [
    ('LogoEmpresa.JPG', '.'),
    ('LOGONUEVO.ico',   '.'),
    ('config',          'config'),
    ('models',          'models'),
    # Caché de fuentes de matplotlib pre-construido: sin él, la primera
    # ejecución en una PC nueva escanea todas las fuentes del sistema
    # (3-5 min en PCs lentas, parece colgado). main.py lo copia al perfil
    # del usuario en el primer arranque.
    ('mpl-cache',       'mpl-cache'),
] + paddle_datas + paddleocr_datas + paddlex_datas + mpl_datas + meta

added_bins = paddle_bins + paddleocr_bins + paddlex_bins + mpl_bins

hidden = paddle_hidden + paddleocr_hidden + paddlex_hidden + mpl_hidden + [
    'customtkinter',
    'PIL._tkinter_finder',
    'PIL.Image',
    'cv2',
    'numpy',
    'reportlab',
    'reportlab.pdfgen.canvas',
    'reportlab.lib.pagesizes',
    'shapely',
    'lxml',
    'pyclipper',
    'skimage',
    'scipy',
    'aiohttp',
    'fitz',
    'certifi',
    'importlib.metadata',
    'importlib.resources',
    'pkg_resources',
]

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=added_bins,
    datas=added_datas,
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # torch/transformers/timm: librerías de IA que el OCR det+rec NO usa
    # (main.py y ocr_engine.py las bloquean en sys.modules, así que ningún
    # import las alcanza). Excluirlas recorta cientos de MB y acelera el
    # arranque en PCs con disco duro lento.
    excludes=['IPython', 'jupyter', 'notebook', 'pytest',
              'torch', 'torchvision', 'torchaudio', 'transformers', 'timm',
              'tensorboard'],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='NotaINE',
    debug=False,
    strip=False,
    upx=False,
    console=False,  # producción: sin ventana de consola
    icon='LOGONUEVO.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name='NotaINE',
)

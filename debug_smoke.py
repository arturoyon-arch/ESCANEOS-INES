import sys, time, os
sys.path.insert(0, '.')
sys.stdout.reconfigure(encoding='utf-8')
from core.pdf_loader import pdf_to_images
from core.processor import process_full

BASE = r'X:\DOÑA VANESSA\CLIENTES INE'
files = [
    'EDUARDO JAVIER ELIZONDO GONZALEZ', 'MARIA ANTONIA GUAJARDO GARZA',
    'MONICA IVETH TAMEZ GARZA', 'RUBEN VAZQUEZ OYERVIDEZ',
    'JOAQUINA REVUELTA NARIO', 'AMERICO CANTU CANTU',
    'MA. LUISA MORALES NIETO', 'CRISTINA REBECA RAMIREZ VANEGAS',
]

# warm-up del motor
p0 = pdf_to_images(os.path.join(BASE, 'FRANCISCO RIVERA DAVILA.pdf'))
process_full(p0[0], p0[1])

for nombre in files:
    path = os.path.join(BASE, nombre + '.pdf')
    if not os.path.exists(path):
        print(f'### {nombre}: NO EXISTE')
        continue
    try:
        pages = pdf_to_images(path)
        t0 = time.time()
        result = process_full(pages[0], pages[1] if len(pages) > 1 else None)
        dt = time.time() - t0
        f = result['frente']
        r = result['reverso']
        ident = r.get('identificador_post_simbolo', '') or '(vacio)'
        cic = r.get('cic', '') or '(vacio)'
        print(f'### {nombre} ({dt:.1f}s)')
        print(f'    nombre={f.get("nombre_completo","")!r} CURP={f.get("curp","")} RFC={f.get("rfc","")}')
        print(f'    fecha={f.get("fecha_nacimiento","")} muni={f.get("municipio","")} edo={f.get("estado","")}')
        print(f'    IDENTIF={ident} CIC={cic}')
    except Exception as e:
        print(f'### {nombre}: ERROR {e}')

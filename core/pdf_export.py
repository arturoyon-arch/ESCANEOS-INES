"""
Exporta los datos extraídos de la INE a un PDF, incluyendo las imágenes del
frente y reverso. Todo el procesamiento es local — no se usa ningún servicio
externo (cumple la restricción de privacidad del proyecto).
"""
from __future__ import annotations
import datetime
from typing import Dict, List, Optional, Tuple
import numpy as np

# Secciones y campos a incluir (mismo orden que la UI). Se omiten las líneas
# crudas de la MRZ por ser ruido para el documento final.
_SECTIONS: List[Tuple[str, List[Tuple[str, str]]]] = [
    ("Información Personal", [
        ("nombre_completo",  "Nombre completo"),
        ("apellido_paterno", "Apellido paterno"),
        ("apellido_materno", "Apellido materno"),
        ("nombre",           "Nombre(s)"),
        ("sexo",             "Sexo"),
        ("fecha_nacimiento", "Fecha de nacimiento"),
        ("curp",             "CURP"),
        ("rfc",              "RFC"),
    ]),
    ("Domicilio", [
        ("domicilio",     "Calle, número y colonia"),
        ("municipio",     "Municipio"),
        ("estado",        "Estado"),
        ("codigo_postal", "Código postal"),
    ]),
    ("Datos de la Credencial", [
        ("clave_elector", "Clave de elector"),
        ("seccion",       "Sección"),
        ("anio_registro", "Año de registro"),
        ("emision",       "Emisión"),
        ("vigencia",      "Vigencia"),
        ("cic",           "CIC"),
        ("identificador_post_simbolo", "Identificador"),
    ]),
]


def _wrap(text: str, font: str, size: float, max_w: float, c) -> List[str]:
    """Parte `text` en varias líneas para que cada una quepa en `max_w` puntos."""
    if c.stringWidth(text, font, size) <= max_w:
        return [text]
    lineas, actual = [], ""
    for palabra in text.split():
        prueba = f"{actual} {palabra}".strip()
        if c.stringWidth(prueba, font, size) <= max_w:
            actual = prueba
        else:
            if actual:
                lineas.append(actual)
            actual = palabra
    if actual:
        lineas.append(actual)
    return lineas or [text]


def _img_reader(img_bgr: np.ndarray):
    """Convierte un array numpy BGR (OpenCV) a un ImageReader de reportlab."""
    import cv2
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    return ImageReader(Image.fromarray(rgb)), img_bgr.shape[1], img_bgr.shape[0]


def export_to_pdf(path: str, data: Dict,
                  frente_img: Optional[np.ndarray] = None,
                  reverso_img: Optional[np.ndarray] = None) -> None:
    """Genera el PDF en `path` con los campos de `data` y las imágenes dadas."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas

    c = canvas.Canvas(path, pagesize=letter)
    W, H = letter
    mx = 18 * mm                      # margen lateral
    y = H - 16 * mm                   # cursor vertical

    azul = (0.10, 0.31, 0.61)
    gris = (0.40, 0.40, 0.40)

    # ── Encabezado ──────────────────────────────────────────────────
    c.setFillColorRGB(*azul)
    c.rect(0, H - 30 * mm, W, 30 * mm, fill=1, stroke=0)
    c.setFillColorRGB(1, 1, 1)
    c.setFont("Helvetica-Bold", 18)
    c.drawString(mx, H - 15 * mm, "NotaINE")
    c.setFont("Helvetica", 10)
    c.drawString(mx, H - 22 * mm, "Notaría Pública No. 134  —  Extracción de datos de credencial INE")
    fecha = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
    c.drawRightString(W - mx, H - 22 * mm, f"Generado: {fecha}")

    y = H - 40 * mm

    # ── Imágenes (frente y reverso, lado a lado) ────────────────────
    imgs = [im for im in (frente_img, reverso_img) if im is not None]
    if imgs:
        box_w = (W - 2 * mx - 6 * mm) / 2     # dos columnas
        box_h = 42 * mm
        x = mx
        for im in imgs[:2]:
            reader, iw, ih = _img_reader(im)
            scale = min(box_w / iw, box_h / ih)
            dw, dh = iw * scale, ih * scale
            c.setStrokeColorRGB(0.7, 0.7, 0.7)
            c.rect(x, y - box_h, box_w, box_h, fill=0, stroke=1)
            c.drawImage(reader, x + (box_w - dw) / 2, y - box_h + (box_h - dh) / 2,
                        width=dw, height=dh, preserveAspectRatio=True, mask='auto')
            x += box_w + 6 * mm
        y -= box_h + 8 * mm

    # ── Secciones de datos ──────────────────────────────────────────
    line_h = 6.5 * mm
    for titulo, campos in _SECTIONS:
        rows = [(lbl, str(data.get(k, "")).strip())
                for k, lbl in campos if str(data.get(k, "")).strip()]
        if not rows:
            continue

        # Salto de página si no cabe el encabezado + al menos una fila
        if y < 30 * mm + line_h * (len(rows) + 1):
            c.showPage()
            y = H - 20 * mm

        # Título de sección
        c.setFillColorRGB(*azul)
        c.setFont("Helvetica-Bold", 12)
        c.drawString(mx, y, titulo)
        y -= 2 * mm
        c.setStrokeColorRGB(*azul)
        c.setLineWidth(0.8)
        c.line(mx, y, W - mx, y)
        y -= line_h

        # Filas etiqueta : valor (con ajuste de línea si el valor es largo)
        val_x = mx + 48 * mm
        val_w = W - mx - val_x          # ancho disponible para el valor
        for lbl, val in rows:
            lineas = _wrap(val, "Helvetica-Bold", 10, val_w, c)
            if y < 22 * mm:
                c.showPage()
                y = H - 20 * mm
            c.setFillColorRGB(*gris)
            c.setFont("Helvetica", 9)
            c.drawString(mx, y, f"{lbl}:")
            c.setFillColorRGB(0, 0, 0)
            c.setFont("Helvetica-Bold", 10)
            for i, ln in enumerate(lineas):
                c.drawString(val_x, y - i * line_h, ln)
            y -= line_h * len(lineas)
        y -= 3 * mm

    # ── Pie de página ───────────────────────────────────────────────
    c.setFillColorRGB(*gris)
    c.setFont("Helvetica-Oblique", 8)
    c.drawCentredString(
        W / 2, 12 * mm,
        "NotaINE  •  Notaría Pública No. 134  •  Desarrollado por Alberto Torres  •  Documento generado localmente")

    c.save()

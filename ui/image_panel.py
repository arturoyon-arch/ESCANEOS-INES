import customtkinter as ctk
from PIL import Image, ImageDraw
import numpy as np

_W, _H = 286, 182


def _placeholder_image() -> Image.Image:
    """Ícono de documento dibujado con PIL (sin depender de fuentes ni emoji)."""
    img = Image.new("RGB", (_W, _H), (51, 51, 51))   # ~gray20
    d = ImageDraw.Draw(img)
    pw, ph, fold = 60, 76, 16
    x0 = (_W - pw) // 2
    y0 = (_H - ph) // 2
    # Cuerpo de la hoja con esquina doblada
    d.polygon([(x0, y0), (x0 + pw - fold, y0), (x0 + pw, y0 + fold),
               (x0 + pw, y0 + ph), (x0, y0 + ph)], fill=(92, 92, 92))
    d.polygon([(x0 + pw - fold, y0), (x0 + pw - fold, y0 + fold),
               (x0 + pw, y0 + fold)], fill=(122, 122, 122))
    # Líneas de texto simuladas
    for i in range(4):
        ly = y0 + 30 + i * 12
        d.line([(x0 + 11, ly), (x0 + pw - 11, ly)], fill=(63, 63, 63), width=3)
    return img


class ImagePanel(ctk.CTkFrame):
    """Preview de una página de INE — imagen grande, sin etiqueta de texto.

    Usa UNA sola CTkImage persistente durante toda la sesión. Nunca se libera
    ni se reasigna, así su PhotoImage interna jamás queda colgada en el label
    de tkinter. Esto evita el TclError 'image "pyimageN" doesn't exist' que
    aparecía al recargar una INE después de pulsar Limpiar.
    """

    def __init__(self, parent, on_load_callback=None, **kwargs):
        super().__init__(parent, corner_radius=10,
                         fg_color=("gray86", "gray17"), **kwargs)
        self.on_load_callback = on_load_callback
        self.current_img: np.ndarray | None = None

        # Un solo canal (dark_image): la app está en modo oscuro forzado y así
        # evitamos el chequeo de tamaños light==dark, que falla en el estado
        # intermedio de configure() cuando el thumbnail mide distinto al placeholder.
        self._placeholder = _placeholder_image()
        self._ctk_img = ctk.CTkImage(
            light_image=None,
            dark_image=self._placeholder, size=(_W, _H))

        self._preview = ctk.CTkLabel(
            self, text="", image=self._ctk_img,
            width=_W, height=_H, corner_radius=8,
            fg_color=("gray80", "gray20"))
        self._preview.pack(padx=3, pady=3)

    def _set_from_array(self, img_cv2: np.ndarray):
        import cv2
        self.current_img = img_cv2
        rgb = cv2.cvtColor(img_cv2, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        pil.thumbnail((_W, _H))
        # Reconfigurar la MISMA CTkImage: el label se actualiza por callback con
        # una PhotoImage nueva y válida dentro de esta misma llamada.
        self._ctk_img.configure(dark_image=pil, size=(pil.width, pil.height))

    def clear(self):
        self.current_img = None
        self._ctk_img.configure(dark_image=self._placeholder, size=(_W, _H))

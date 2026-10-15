import customtkinter as ctk
import tkinter as tk
from typing import Dict, List, Tuple, Optional

_FONT = "Segoe UI"

# Paleta
_CARD_BG   = ("gray91", "gray16")
_LABEL_CLR = ("gray45", "gray58")
_CONF = {
    "high": ("#16a34a", "#4ade80"),
    "mid":  ("#d97706", "#fbbf24"),
    "low":  ("#dc2626", "#f87171"),
}

# ── Secciones de campos ────────────────────────────────────────────────────────
# (key, label_visible, span_cols)  span: 1=mitad, 2=ancho completo
_SECTIONS: List[Tuple[str, str, List[Tuple[str, str, int]]]] = [
    ("Información Personal", "👤", [
        ("nombre_completo",  "Nombre Completo",       2),
        ("apellido_paterno", "Apellido Paterno",       1),
        ("apellido_materno", "Apellido Materno",       1),
        ("nombre",           "Nombre(s)",              1),
        ("sexo",             "Sexo",                   1),
        ("fecha_nacimiento", "Fecha de Nacimiento",    1),
        ("curp",             "CURP",                   1),
        ("rfc",              "RFC",                    1),
    ]),
    ("Domicilio", "🏠", [
        ("domicilio",    "Calle, Número y Colonia",  2),
        ("municipio",    "Municipio",                1),
        ("estado",       "Estado",                   1),
        ("codigo_postal","Código Postal",            1),
    ]),
    ("Datos de la Credencial", "🪪", [
        ("clave_elector", "Clave de Elector",  2),
        ("seccion",       "Sección",           1),
        ("anio_registro", "Año de Registro",   1),
        ("emision",       "Emisión",           1),
        ("vigencia",      "Vigencia",          1),
    ]),
    ("MRZ / Reverso", "🔍", [
        ("cic",                       "CIC",           1),
        ("identificador_post_simbolo","Identificador", 1),
        ("ocr_linea1",                "Línea MRZ 1",   2),
        ("ocr_linea2",                "Línea MRZ 2",   2),
        ("ocr_linea3",                "Línea MRZ 3",   2),
    ]),
]

_ALL_FIELDS = [k for _, _, fields in _SECTIONS for k, _, _ in fields]
FIELD_LABELS = {k: lbl for _, _, fields in _SECTIONS for k, lbl, _ in fields}


class _FieldWidget(ctk.CTkFrame):
    """Etiqueta + campo de valor + botón copiar."""

    # Fonts compartidos (se crean una sola vez por instancia de Tk)
    _f_label: Optional[ctk.CTkFont] = None
    _f_value: Optional[ctk.CTkFont] = None

    def __init__(self, parent, key: str, label: str, **kwargs):
        super().__init__(parent, fg_color="transparent", **kwargs)
        self.key = key
        self._var = tk.StringVar()

        # Crear fonts la primera vez
        if _FieldWidget._f_label is None:
            _FieldWidget._f_label = ctk.CTkFont(family=_FONT, size=10)
            _FieldWidget._f_value = ctk.CTkFont(family=_FONT, size=13)

        self.columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=label,
                     font=_FieldWidget._f_label,
                     text_color=_LABEL_CLR,
                     anchor="w").grid(row=0, column=0, sticky="w")

        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.grid(row=1, column=0, sticky="ew")
        row2.columnconfigure(0, weight=1)

        self._entry = ctk.CTkEntry(
            row2, textvariable=self._var,
            font=_FieldWidget._f_value,
            height=32, corner_radius=6,
            border_width=1,
            border_color=("gray76", "gray33"))
        self._entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))

        self._dot = ctk.CTkLabel(row2, text="", width=12,
                                  font=ctk.CTkFont(family=_FONT, size=14))
        self._dot.grid(row=0, column=1, padx=(0, 2))

        ctk.CTkButton(
            row2, text="📋", width=32, height=32,
            corner_radius=6,
            fg_color=("gray84", "gray26"),
            hover_color=("gray76", "gray32"),
            text_color=("gray30", "gray72"),
            font=ctk.CTkFont(family=_FONT, size=13),
            command=self._copy).grid(row=0, column=2)

    def set_value(self, value: str, confidence: Optional[float] = None):
        self._var.set(value)
        if confidence is not None:
            tier = "high" if confidence >= 0.9 else ("mid" if confidence >= 0.7 else "low")
            self._dot.configure(text="●", text_color=_CONF[tier])
        else:
            self._dot.configure(text="")

    def _copy(self):
        v = self._var.get()
        if v:
            self.clipboard_clear()
            self.clipboard_append(v)


class ResultsPanel(ctk.CTkFrame):
    def __init__(self, parent, export_callback=None, **kwargs):
        super().__init__(parent, corner_radius=14, **kwargs)
        self._widgets: Dict[str, _FieldWidget] = {}
        self._export_callback = export_callback
        self._build_ui()

    # ──────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # Cabecera fija
        top = ctk.CTkFrame(self, fg_color="transparent", height=46)
        top.pack(fill="x", padx=16, pady=(12, 0))
        top.pack_propagate(False)

        ctk.CTkLabel(top, text="Resultados de extracción",
                     font=ctk.CTkFont(family=_FONT, size=14, weight="bold")
                     ).pack(side="left", pady=8)

        ctk.CTkButton(
            top, text="📄  Copiar todo",
            font=ctk.CTkFont(family=_FONT, size=12),
            height=34, width=120, corner_radius=8,
            fg_color="transparent", border_width=1,
            border_color=("gray60", "gray42"),
            text_color=("gray35", "gray70"),
            hover_color=("gray88", "gray24"),
            command=self._copy_all).pack(side="right", padx=(8, 0), pady=6)

        ctk.CTkButton(
            top, text="⬇  Exportar PDF",
            font=ctk.CTkFont(family=_FONT, size=12, weight="bold"),
            height=34, width=140, corner_radius=8,
            command=self._export).pack(side="right", pady=6)

        # ── Aviso permanente de verificación ──────────────────────────
        aviso = ctk.CTkFrame(self, corner_radius=8,
                             fg_color=("#fef3c7", "#3a2f12"),
                             border_width=1, border_color=("#f59e0b", "#a16207"))
        aviso.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(
            aviso,
            text=("⚠  Verifique que los datos coincidan con la credencial "
                  "escaneada. El OCR puede unir nombres o apellidos y eso "
                  "afecta el RFC. Si corrige algún campo, pulse «Regenerar RFC» "
                  "y valídelo en el SAT."),
            font=ctk.CTkFont(family=_FONT, size=11),
            text_color=("#92400e", "#fcd34d"),
            wraplength=620, justify="left", anchor="w"
        ).pack(fill="x", padx=12, pady=8)

        # Área scrollable
        self._scroll = ctk.CTkScrollableFrame(
            self, corner_radius=0, fg_color="transparent")
        self._scroll.pack(fill="both", expand=True, padx=8, pady=(6, 8))
        self._scroll.columnconfigure(0, weight=1)

        for title, icon, fields in _SECTIONS:
            self._build_section(title, icon, fields)
            # Tras los datos personales, botón para recalcular el RFC con los
            # valores actuales (por si el usuario corrigió nombre/apellidos).
            if title == "Información Personal":
                self._add_rfc_button()

        # Advertencias
        self._warn = ctk.CTkLabel(
            self._scroll, text="", wraplength=580,
            justify="left", anchor="w",
            font=ctk.CTkFont(family=_FONT, size=11),
            text_color=("darkorange", "#fbbf24"))
        self._warn.pack(fill="x", padx=4, pady=(4, 8))

    def _build_section(self, title: str, icon: str,
                        fields: List[Tuple[str, str, int]]):
        # Encabezado de sección
        hdr = ctk.CTkFrame(self._scroll, fg_color="transparent", height=28)
        hdr.pack(fill="x", padx=4, pady=(12, 4))
        hdr.pack_propagate(False)

        ctk.CTkLabel(hdr,
                     text=f"{icon}  {title}",
                     font=ctk.CTkFont(family=_FONT, size=12, weight="bold"),
                     text_color=("gray28", "gray78")
                     ).pack(side="left", pady=2)
        ctk.CTkFrame(hdr, height=1,
                     fg_color=("gray76", "gray32")
                     ).pack(side="left", fill="x", expand=True,
                            padx=(10, 0), pady=13)

        # Tarjeta de la sección
        card = ctk.CTkFrame(self._scroll, corner_radius=10, fg_color=_CARD_BG)
        card.pack(fill="x", padx=4, pady=(0, 2))
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        row_idx = 0
        col_idx = 0
        for key, label, span in fields:
            w = _FieldWidget(card, key, label)
            self._widgets[key] = w

            if span == 2:
                if col_idx != 0:
                    col_idx = 0
                    row_idx += 1
                w.grid(row=row_idx, column=0, columnspan=2,
                       padx=12, pady=7, sticky="ew")
                col_idx = 0
                row_idx += 1
            else:
                w.grid(row=row_idx, column=col_idx,
                       padx=12, pady=7, sticky="ew")
                col_idx += 1
                if col_idx >= 2:
                    col_idx = 0
                    row_idx += 1

    def _add_rfc_button(self):
        bar = ctk.CTkFrame(self._scroll, fg_color="transparent")
        bar.pack(fill="x", padx=4, pady=(2, 0))

        self._rfc_msg = ctk.CTkLabel(
            bar, text="", anchor="e",
            font=ctk.CTkFont(family=_FONT, size=10))
        self._rfc_msg.pack(side="left", fill="x", expand=True)

        ctk.CTkButton(
            bar, text="🔄  Regenerar RFC",
            font=ctk.CTkFont(family=_FONT, size=12),
            height=32, width=160, corner_radius=8,
            fg_color=("#0d9488", "#0f766e"),
            hover_color=("#0f766e", "#115e59"),
            command=self._regenerate_rfc).pack(side="right", padx=(8, 0))

        ctk.CTkButton(
            bar, text="🌐  Validar en SAT",
            font=ctk.CTkFont(family=_FONT, size=12),
            height=32, width=150, corner_radius=8,
            fg_color="transparent", border_width=1,
            border_color=("#0d9488", "#14b8a6"),
            text_color=("#0f766e", "#5eead4"),
            hover_color=("#ccfbf1", "#134e4a"),
            command=self._validar_sat).pack(side="right")

    _SAT_URL = "https://agsc.siat.sat.gob.mx/PTSC/ValidaRFC/index.jsf"

    def _validar_sat(self):
        """Abre el validador oficial del SAT en el navegador y copia el RFC al
        portapapeles para pegarlo. No se envía nada automáticamente: el usuario
        valida manualmente (los datos del cliente no salen de la app)."""
        import webbrowser
        rfc = self._widgets["rfc"]._var.get().strip()
        if rfc:
            self.clipboard_clear()
            self.clipboard_append(rfc)
            self._rfc_msg.configure(
                text="RFC copiado — pégalo en la página del SAT",
                text_color=("#0f766e", "#5eead4"))
        webbrowser.open(self._SAT_URL)

    def _regenerate_rfc(self):
        """Recalcula el RFC usando los valores ACTUALES de los campos editables.
        Permite al usuario corregir nombre/apellidos a mano y obtener el RFC bien."""
        from core.rfc_calculator import calcular_rfc
        ap    = self._widgets["apellido_paterno"]._var.get().strip()
        am    = self._widgets["apellido_materno"]._var.get().strip()
        nom   = self._widgets["nombre"]._var.get().strip()
        fecha = self._widgets["fecha_nacimiento"]._var.get().strip()

        rfc = calcular_rfc(ap, am, nom, fecha)
        if rfc:
            self._widgets["rfc"].set_value(rfc)
            self._rfc_msg.configure(text="✓ RFC actualizado",
                                    text_color=("#15803d", "#4ade80"))
        else:
            self._rfc_msg.configure(
                text="Faltan datos (apellido paterno, nombre y fecha)",
                text_color=("#d97706", "#fbbf24"))

    # ──────────────────────────────────────────────────────────────────
    def update_results(self, result: Dict):
        frente     = result.get("frente", {})
        reverso    = result.get("reverso", {})
        confidence = result.get("confianza", {})
        warnings   = result.get("advertencias", [])
        cross      = result.get("cross_validacion", "")

        all_data = {**frente, **reverso}
        for key, w in self._widgets.items():
            w.set_value(str(all_data.get(key, "")), confidence.get(key))

        parts = list(warnings)
        if cross and cross != "OK":
            parts.append(f"Cross-validación: {cross}")
        self._warn.configure(
            text=("⚠️  " + "   •   ".join(parts)) if parts else "")
        self._rfc_msg.configure(text="")

    def clear(self):
        for w in self._widgets.values():
            w.set_value("")
        self._warn.configure(text="")
        self._rfc_msg.configure(text="")

    def get_all_values(self) -> Dict[str, str]:
        """Devuelve los valores ACTUALES de todos los campos (ya editados)."""
        return {k: w._var.get().strip() for k, w in self._widgets.items()}

    def _export(self):
        if self._export_callback:
            self._export_callback(self.get_all_values())

    def _copy_all(self):
        lines = [
            f"{FIELD_LABELS.get(k, k)}: {self._widgets[k]._var.get()}"
            for k in _ALL_FIELDS
            if k in self._widgets
            and self._widgets[k]._var.get().strip()
            and k not in ("ocr_linea1", "ocr_linea2", "ocr_linea3")
        ]
        if lines:
            self.clipboard_clear()
            self.clipboard_append("\n".join(lines))

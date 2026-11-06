"""Genera el informe PDF de una auditoría (CA-4.2)."""
from typing import Optional

from fpdf import FPDF

from ..models import Auditoria, Tienda

COLORES = {"Alta": (192, 57, 43), "Media": (211, 132, 0), "Baja": (39, 128, 80)}


def _t(texto) -> str:
    """Las fuentes base de PDF usan Latin-1: reemplaza los caracteres que no existan."""
    return str(texto if texto is not None else "").replace("—", "-").replace("·", "-") \
        .encode("latin-1", "replace").decode("latin-1")


def etiqueta_puntaje(valor: Optional[int]) -> str:
    if valor is None:
        return "No disponible"
    return "Bueno" if valor >= 90 else "Necesita mejora" if valor >= 50 else "Crítico"


def etiqueta_lcp(lcp: Optional[float]) -> str:
    if lcp is None:
        return "No disponible"
    return "Bueno" if lcp <= 2.5 else "Necesita mejora" if lcp <= 4 else "Crítico"


class ReportePDF(FPDF):
    def header(self):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(120, 120, 120)
        self.cell(0, 6, _t("Auditor SEO & PageSpeed AI - Informe de auditoría"), new_x="LMARGIN", new_y="NEXT")
        self.ln(2)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, _t(f"Página {self.page_no()}"), align="C")


class GeneradorReportePDF:
    def generar(self, a: Auditoria, tienda: Tienda) -> bytes:
        pdf = ReportePDF()
        pdf.set_auto_page_break(True, margin=18)
        pdf.add_page()

        pdf.set_text_color(20, 20, 20)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 10, _t(f"Reporte #{a.codigo}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 10)
        for linea in (f"Tienda: {tienda.nombre}", f"URL auditada: {a.url}",
                      f"Fecha: {a.fecha}   -   Duración: {a.duracion_s}s   -   Estado HTTP: {a.http_status}"):
            pdf.multi_cell(0, 5, _t(linea), new_x="LMARGIN", new_y="NEXT")
        pdf.ln(4)

        # Tarjetas de métricas
        tarjetas = [
            ("Rendimiento Mobile", f"{a.rendimiento} / 100" if a.rendimiento is not None else "N/D", etiqueta_puntaje(a.rendimiento)),
            ("SEO On-Page", f"{a.seo} / 100", etiqueta_puntaje(a.seo)),
            ("Core Web Vitals (LCP)", f"{a.lcp_s}s" if a.lcp_s is not None else "N/D", etiqueta_lcp(a.lcp_s)),
        ]
        ancho = (pdf.w - pdf.l_margin - pdf.r_margin) / 3
        y = pdf.get_y()
        for i, (titulo, valor, estado) in enumerate(tarjetas):
            x = pdf.l_margin + i * ancho
            pdf.set_fill_color(241, 239, 233)
            pdf.rect(x + 1, y, ancho - 2, 26, style="F")
            pdf.set_xy(x + 3, y + 2)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(ancho - 6, 5, _t(titulo))
            pdf.set_xy(x + 3, y + 8)
            pdf.set_font("Helvetica", "B", 15)
            pdf.cell(ancho - 6, 8, _t(valor))
            pdf.set_xy(x + 3, y + 18)
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(ancho - 6, 5, _t(estado))
        pdf.set_xy(pdf.l_margin, y + 30)

        if a.pagespeed_error:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(160, 60, 40)
            pdf.multi_cell(0, 5, _t(f"Métricas de velocidad no disponibles: {a.pagespeed_error}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(20, 20, 20)
            pdf.ln(2)

        # Plan de acción
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _t("Plan de acción priorizado"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(110, 110, 110)
        pdf.multi_cell(0, 5, _t(f"Generado por: {a.ia_fuente}"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(20, 20, 20)
        pdf.ln(2)
        if not a.recomendaciones:
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, _t("No se detectaron problemas relevantes."), new_x="LMARGIN", new_y="NEXT")
        for r in a.recomendaciones:
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*COLORES.get(r["severidad"], (60, 60, 60)))
            pdf.multi_cell(0, 5, _t(f"[{r['severidad']} - {r['categoria']}] {r['titulo']}"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(20, 20, 20)
            pdf.set_font("Helvetica", "", 10)
            pdf.multi_cell(0, 5, _t(r["accion"]), new_x="LMARGIN", new_y="NEXT")
            pdf.ln(2)

        # Datos técnicos
        s = a.scraper
        pdf.ln(2)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, _t("Datos técnicos extraídos"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        filas = [
            ("Title", s.get("title") or "(vacío)"),
            ("Meta description", s.get("meta_description") or "(ausente)"),
            ("H1", ", ".join(s.get("encabezados", {}).get("h1", [])) or "(ausente)"),
            ("H2 / H3", f"{len(s.get('encabezados', {}).get('h2', []))} / {len(s.get('encabezados', {}).get('h3', []))}"),
            ("Imágenes sin alt", f"{s.get('imagenes_sin_alt', 0)} de {s.get('imagenes_total', 0)}"),
            ("Canonical", s.get("canonical") or "(ausente)"),
            ("Idioma (lang)", s.get("lang") or "(ausente)"),
            ("Etiquetas meta", s.get("etiquetas_meta_total", 0)),
            ("Palabras en la página", s.get("palabras", 0)),
        ]
        if a.pagespeed:
            filas += [("CLS", a.cls), ("Total Blocking Time", f"{a.tbt_ms} ms")]
        for etiqueta, valor in filas:
            pdf.set_font("Helvetica", "B", 9)
            pdf.cell(45, 5, _t(etiqueta))
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(0, 5, _t(valor), new_x="LMARGIN", new_y="NEXT")

        return bytes(pdf.output())

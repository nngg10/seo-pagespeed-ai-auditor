"""Convierte los datos crudos del scraper y de PageSpeed en hallazgos con severidad y un puntaje SEO."""
from dataclasses import asdict, dataclass
from typing import Optional

ORDEN_SEVERIDAD = {"Alta": 0, "Media": 1, "Baja": 2}


@dataclass
class Hallazgo:
    severidad: str   # Alta | Media | Baja
    categoria: str   # SEO | Velocidad
    problema: str
    accion: str
    penalizacion: int = 0

    def a_dict(self) -> dict:
        d = asdict(self)
        d.pop("penalizacion")
        return d


class EvaluadorSEO:
    """Reglas On-Page. Cada problema resta puntos a un puntaje base de 100."""

    def evaluar(self, s: dict) -> list[Hallazgo]:
        h: list[Hallazgo] = []
        titulo, desc = s["title"], s["meta_description"]

        if not titulo:
            h.append(Hallazgo("Alta", "SEO", "La página no tiene etiqueta <title>.",
                              "Agrega un título único de 30 a 60 caracteres que incluya la palabra clave principal.", 20))
        elif not 30 <= s["title_longitud"] <= 65:
            h.append(Hallazgo("Baja", "SEO", f"El título mide {s['title_longitud']} caracteres (recomendado 30-60).",
                              "Ajusta la longitud del título para que Google no lo corte ni quede demasiado corto.", 5))

        if desc is None or desc == "":
            h.append(Hallazgo("Alta", "SEO", 'Ausencia de etiqueta <meta name="description">.',
                              "Redacta una meta descripción de 70 a 160 caracteres que invite al clic.", 15))
        elif not 70 <= len(desc) <= 160:
            h.append(Hallazgo("Baja", "SEO", f"La meta descripción mide {len(desc)} caracteres (recomendado 70-160).",
                              "Ajusta la meta descripción al rango recomendado.", 5))

        h1 = s["encabezados"]["h1"]
        if not h1:
            h.append(Hallazgo("Alta", "SEO", "La página no tiene encabezado H1.",
                              "Agrega un único H1 que describa el producto o la categoría.", 15))
        elif len(h1) > 1:
            h.append(Hallazgo("Media", "SEO", f"La página tiene {len(h1)} encabezados H1.",
                              "Deja un solo H1 y convierte los demás en H2.", 5))
        if not s["encabezados"]["h2"]:
            h.append(Hallazgo("Baja", "SEO", "No hay encabezados H2.",
                              "Estructura el contenido con subtítulos H2/H3 (descripción, características, opiniones).", 5))

        n = s["imagenes_sin_alt"]
        if n:
            h.append(Hallazgo("Alta" if n >= 5 else "Media", "SEO",
                              f"Faltan {n} atributo{'s' if n != 1 else ''} alt en imágenes.",
                              "Agrega un texto alternativo descriptivo a cada imagen de producto.", min(15, n * 2)))

        if not s["meta_viewport"]:
            h.append(Hallazgo("Alta", "SEO", "No hay meta viewport: la página no está adaptada a móviles.",
                              'Agrega <meta name="viewport" content="width=device-width, initial-scale=1">.', 10))
        if s["meta_robots"] and "noindex" in s["meta_robots"].lower():
            h.append(Hallazgo("Alta", "SEO", "La página tiene meta robots 'noindex' y no aparecerá en Google.",
                              "Quita 'noindex' si la página debe posicionar.", 25))
        if not s["canonical"]:
            h.append(Hallazgo("Media", "SEO", "No hay etiqueta canonical.",
                              "Agrega <link rel=\"canonical\"> para evitar contenido duplicado entre variantes de producto.", 5))
        if not s["lang"]:
            h.append(Hallazgo("Media", "SEO", "La etiqueta <html> no declara el idioma (lang).",
                              'Agrega lang="es" a la etiqueta <html>.', 5))
        if not s["open_graph"]:
            h.append(Hallazgo("Baja", "SEO", "No hay etiquetas Open Graph.",
                              "Agrega og:title, og:description y og:image para que el enlace se vea bien en redes sociales.", 3))
        return h

    @staticmethod
    def puntaje(hallazgos: list[Hallazgo]) -> int:
        return max(0, 100 - sum(x.penalizacion for x in hallazgos if x.categoria == "SEO"))


class EvaluadorRendimiento:
    def evaluar(self, p: Optional[dict]) -> list[Hallazgo]:
        if not p:
            return []
        h: list[Hallazgo] = []
        r = p.get("rendimiento")
        if r is not None and r < 90:
            h.append(Hallazgo("Alta" if r < 50 else "Media", "Velocidad",
                              f"El rendimiento móvil es {r}/100.",
                              "Prioriza las oportunidades de velocidad listadas abajo.", 0))
        lcp = p.get("lcp_s")
        if lcp is not None and lcp > 2.5:
            h.append(Hallazgo("Alta" if lcp > 4 else "Media", "Velocidad",
                              f"El LCP es {lcp}s (bueno: 2.5s o menos).",
                              "Comprime la imagen principal (WebP/AVIF), precárgala y evita bloquear el renderizado.", 0))
        cls = p.get("cls")
        if cls is not None and cls > 0.1:
            h.append(Hallazgo("Alta" if cls > 0.25 else "Media", "Velocidad",
                              f"El CLS es {cls} (bueno: 0.1 o menos).",
                              "Define ancho y alto en imágenes y banners para evitar saltos de contenido.", 0))
        tbt = p.get("tbt_ms")
        if tbt is not None and tbt > 200:
            h.append(Hallazgo("Alta" if tbt > 600 else "Media", "Velocidad",
                              f"El tiempo de bloqueo total es {tbt} ms (bueno: 200 ms o menos).",
                              "Reduce y difiere el JavaScript de terceros (chats, píxeles, widgets).", 0))
        for o in p.get("oportunidades", [])[:3]:
            if o["ahorro_ms"] >= 300:
                h.append(Hallazgo("Media", "Velocidad", f"Oportunidad PageSpeed: {o['titulo']}.",
                                  f"Corregirla podría ahorrar cerca de {o['ahorro_ms'] / 1000:.1f}s de carga.", 0))
        return h


def ordenar(hallazgos: list[dict]) -> list[dict]:
    return sorted(hallazgos, key=lambda x: ORDEN_SEVERIDAD.get(x.get("severidad"), 3))

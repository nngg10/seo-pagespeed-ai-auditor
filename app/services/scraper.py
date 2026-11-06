"""Módulo 2: Web Scraper propio. Descarga el HTML y extrae las etiquetas SEO On-Page."""
import re
import time
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup


class ScraperError(Exception):
    """La URL no es válida, no responde o no devuelve HTML (CA-3.2)."""


class WebScraper:
    USER_AGENT = "Mozilla/5.0 (compatible; SEO-PageSpeed-AI-Auditor/1.0; prototipo academico)"

    def __init__(self, timeout: float = 15):
        self.timeout = timeout

    async def analizar(self, url: str) -> dict:
        inicio = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout, follow_redirects=True, headers={"User-Agent": self.USER_AGENT}
            ) as cliente:
                r = await cliente.get(url)
        except httpx.InvalidURL:
            raise ScraperError("La URL no tiene un formato válido.")
        except httpx.TimeoutException:
            raise ScraperError(f"El sitio no respondió en {self.timeout:.0f} segundos.")
        except httpx.ConnectError:
            raise ScraperError("No se pudo conectar con el sitio (dominio inexistente o servidor caído).")
        except httpx.RequestError as e:
            raise ScraperError(f"No se pudo acceder a la URL ({e.__class__.__name__}).")

        if r.status_code >= 400:
            raise ScraperError(f"El sitio respondió con estado HTTP {r.status_code}; no se puede auditar.")
        if "html" not in r.headers.get("content-type", "").lower():
            raise ScraperError("La URL no devuelve una página HTML.")

        respuesta_ms = round((time.perf_counter() - inicio) * 1000)
        return self._extraer(r.text, str(r.url), r.status_code, respuesta_ms, len(r.history) > 0)

    # ------------------------------------------------------------------ parsing
    def _extraer(self, html: str, url_final: str, status: int, respuesta_ms: int, redirigida: bool) -> dict:
        soup = BeautifulSoup(html, "lxml")

        def meta_nombre(nombre):
            tag = soup.find("meta", attrs={"name": re.compile(f"^{nombre}$", re.I)})
            return (tag.get("content") or "").strip() if tag else None

        titulo = soup.title.get_text(strip=True) if soup.title else ""
        canonical = soup.find("link", rel=lambda v: v and "canonical" in [x.lower() for x in (v if isinstance(v, list) else [v])])
        og = {
            t.get("property"): (t.get("content") or "").strip()
            for t in soup.find_all("meta", attrs={"property": re.compile(r"^og:", re.I)})
        }
        encabezados = {
            f"h{n}": [h.get_text(" ", strip=True)[:120] for h in soup.find_all(f"h{n}")] for n in (1, 2, 3)
        }

        imagenes = soup.find_all("img")
        sin_alt = [
            urljoin(url_final, img.get("src") or img.get("data-src") or "")
            for img in imagenes if img.get("alt") is None
        ]

        metas = soup.find_all("meta")
        dominio = urlparse(url_final).netloc
        enlaces = [a.get("href", "") for a in soup.find_all("a", href=True)]
        internos = sum(1 for h in enlaces if urlparse(urljoin(url_final, h)).netloc == dominio)

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        palabras = len((soup.body or soup).get_text(" ", strip=True).split())

        return {
            "url_final": url_final,
            "http_status": status,
            "redirigida": redirigida,
            "tiempo_respuesta_ms": respuesta_ms,
            "title": titulo,
            "title_longitud": len(titulo),
            "meta_description": meta_nombre("description"),
            "meta_robots": meta_nombre("robots"),
            "meta_viewport": meta_nombre("viewport"),
            "canonical": canonical.get("href") if canonical else None,
            "lang": soup.html.get("lang") if soup.html else None,
            "open_graph": og,
            "encabezados": encabezados,
            "imagenes_total": len(imagenes),
            "imagenes_sin_alt": len(sin_alt),
            "imagenes_sin_alt_ejemplos": sin_alt[:5],
            "etiquetas_meta_total": len(metas),
            "enlaces_internos": internos,
            "enlaces_externos": len(enlaces) - internos,
            "palabras": palabras,
        }

"""Módulo 1: cliente HTTP de la API Google PageSpeed Insights v5."""
import httpx

from ..config import PAGESPEED_API_KEY, PAGESPEED_TIMEOUT


class PageSpeedError(Exception):
    """La API de PageSpeed no respondió o devolvió un error."""


class ClientePageSpeed:
    ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"

    def __init__(self, api_key: str = PAGESPEED_API_KEY, timeout: float = PAGESPEED_TIMEOUT):
        self.api_key = api_key
        self.timeout = timeout

    async def consultar(self, url: str, estrategia: str = "mobile") -> dict:
        params = [("url", url), ("strategy", estrategia), ("category", "performance"), ("category", "seo"), ("locale", "es")]
        if self.api_key:
            params.append(("key", self.api_key))
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as cliente:
                r = await cliente.get(self.ENDPOINT, params=params)
        except httpx.TimeoutException:
            raise PageSpeedError(f"Google PageSpeed no respondió en {self.timeout:.0f} segundos.")
        except httpx.RequestError as e:
            raise PageSpeedError(f"No se pudo contactar a Google PageSpeed ({e.__class__.__name__}).")

        if r.status_code == 429:
            if self.api_key:
                raise PageSpeedError("Se superó la cuota de consultas de tu API key de PageSpeed. Intenta más tarde.")
            raise PageSpeedError(
                "La cuota anónima de Google PageSpeed está agotada. Crea una API key gratuita "
                "(https://developers.google.com/speed/docs/insights/v5/get-started) y colócala en PAGESPEED_API_KEY del archivo .env."
            )
        if r.status_code != 200:
            try:
                mensaje = r.json()["error"]["message"]
            except Exception:
                mensaje = r.text[:200]
            raise PageSpeedError(f"PageSpeed devolvió HTTP {r.status_code}: {mensaje}")
        return self._extraer_metricas(r.json())

    @staticmethod
    def _extraer_metricas(datos: dict) -> dict:
        lh = datos.get("lighthouseResult", {})
        cats = lh.get("categories", {})
        audits = lh.get("audits", {})

        def score(cat):
            s = cats.get(cat, {}).get("score")
            return round(s * 100) if s is not None else None

        def valor(audit_id):
            return audits.get(audit_id, {}).get("numericValue")

        lcp_ms = valor("largest-contentful-paint")
        oportunidades = []
        for a in audits.values():
            detalles = a.get("details") or {}
            if detalles.get("type") == "opportunity" and (a.get("score") is not None and a["score"] < 0.9):
                ahorro = detalles.get("overallSavingsMs") or 0
                oportunidades.append({"titulo": a.get("title", ""), "ahorro_ms": round(ahorro)})
        oportunidades.sort(key=lambda o: o["ahorro_ms"], reverse=True)

        campo = datos.get("loadingExperience", {}).get("metrics", {})
        inp = campo.get("INTERACTION_TO_NEXT_PAINT", {}).get("percentile")

        return {
            "rendimiento": score("performance"),
            "seo_lighthouse": score("seo"),
            "lcp_s": round(lcp_ms / 1000, 2) if lcp_ms is not None else None,
            "cls": round(valor("cumulative-layout-shift"), 3) if valor("cumulative-layout-shift") is not None else None,
            "tbt_ms": round(valor("total-blocking-time")) if valor("total-blocking-time") is not None else None,
            "fcp_s": round(valor("first-contentful-paint") / 1000, 2) if valor("first-contentful-paint") else None,
            "speed_index_s": round(valor("speed-index") / 1000, 2) if valor("speed-index") else None,
            "inp_ms_campo": inp,
            "oportunidades": oportunidades[:5],
        }

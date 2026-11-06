"""Orquesta una auditoría completa: scraper y PageSpeed en paralelo, evaluación y diagnóstico IA."""
import asyncio
import time

from .ai_agent import AgenteIA
from .evaluador import EvaluadorRendimiento, EvaluadorSEO, ordenar
from .pagespeed import ClientePageSpeed, PageSpeedError
from .scraper import ScraperError, WebScraper  # noqa: F401  (ScraperError se re-exporta)


class ServicioAuditoria:
    def __init__(self, scraper: WebScraper | None = None, pagespeed: ClientePageSpeed | None = None,
                 agente: AgenteIA | None = None):
        self.scraper = scraper or WebScraper()
        self.pagespeed = pagespeed or ClientePageSpeed()
        self.agente = agente or AgenteIA()
        self.eval_seo = EvaluadorSEO()
        self.eval_rendimiento = EvaluadorRendimiento()

    async def ejecutar(self, url: str) -> dict:
        inicio = time.perf_counter()
        tarea_psi = asyncio.create_task(self.pagespeed.consultar(url))
        try:
            scraping = await self.scraper.analizar(url)
        except ScraperError:
            tarea_psi.cancel()
            raise

        psi, psi_error = None, None
        try:
            psi = await tarea_psi
        except PageSpeedError as e:
            psi_error = str(e)

        hallazgos_seo = self.eval_seo.evaluar(scraping)
        hallazgos = ordenar([h.a_dict() for h in hallazgos_seo + self.eval_rendimiento.evaluar(psi)])
        diagnostico = await self.agente.diagnosticar(url, scraping, psi, hallazgos)

        return {
            "url": url,
            "duracion_s": round(time.perf_counter() - inicio, 1),
            "http_status": scraping["http_status"],
            "rendimiento": psi.get("rendimiento") if psi else None,
            "seo": self.eval_seo.puntaje(hallazgos_seo),
            "lcp_s": psi.get("lcp_s") if psi else None,
            "cls": psi.get("cls") if psi else None,
            "tbt_ms": psi.get("tbt_ms") if psi else None,
            "pagespeed_error": psi_error,
            "pagespeed": psi or {},
            "scraper": scraping,
            "hallazgos": hallazgos,
            "recomendaciones": diagnostico.recomendaciones,
            "ia_fuente": diagnostico.fuente,
            "ia_aviso": diagnostico.aviso,
            "ia_fallo": diagnostico.fallo,
        }

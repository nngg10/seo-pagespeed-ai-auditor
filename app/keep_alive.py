"""Mantiene despierto el servicio en el plan gratuito de Render.

Render apaga el servicio tras 15 minutos sin tráfico entrante. Esta tarea visita la
URL pública del propio servicio cada 10 minutos. Solo se activa cuando existe la
variable RENDER_EXTERNAL_URL, que Render define automáticamente; en local no hace nada.
"""
import asyncio
import logging
import os
from typing import Optional

import httpx

log = logging.getLogger("uvicorn.error")


class KeepAlive:
    def __init__(self, url_base: Optional[str], intervalo_s: int = 600):
        self.url = f"{url_base.rstrip('/')}/api/salud" if url_base else None
        self.intervalo_s = intervalo_s
        self._tarea: Optional[asyncio.Task] = None

    @classmethod
    def desde_entorno(cls) -> "KeepAlive":
        return cls(os.getenv("RENDER_EXTERNAL_URL"), int(os.getenv("KEEP_ALIVE_SEGUNDOS") or 600))

    async def _bucle(self) -> None:
        async with httpx.AsyncClient(timeout=30) as cliente:
            while True:
                await asyncio.sleep(self.intervalo_s)
                try:
                    r = await cliente.get(self.url)
                    log.info("keep-alive: %s -> %s", self.url, r.status_code)
                except httpx.HTTPError as e:
                    log.warning("keep-alive falló: %s", e.__class__.__name__)

    def iniciar(self) -> None:
        if self.url and self._tarea is None:
            log.info("keep-alive activo: %s cada %s s", self.url, self.intervalo_s)
            self._tarea = asyncio.create_task(self._bucle())

    async def detener(self) -> None:
        if self._tarea:
            self._tarea.cancel()
            try:
                await self._tarea
            except asyncio.CancelledError:
                pass

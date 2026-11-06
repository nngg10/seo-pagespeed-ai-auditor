"""Módulo 3: Agente IA. Sintetiza los hallazgos técnicos en un plan de acción en lenguaje natural.

Proveedores: Gemini (GEMINI_API_KEY) u OpenAI (OPENAI_API_KEY). Sin clave, o si el servicio
falla, se usa un motor de reglas local y se informa al usuario (CA-4.3).
"""
import json
from dataclasses import dataclass, field
from typing import Optional

import httpx

from ..config import GEMINI_API_KEY, GEMINI_MODEL, OPENAI_API_KEY, OPENAI_MODEL
from .evaluador import ORDEN_SEVERIDAD, ordenar

FUENTE_REGLAS = "Motor de reglas local"


@dataclass
class Diagnostico:
    recomendaciones: list = field(default_factory=list)
    fuente: str = FUENTE_REGLAS
    aviso: Optional[str] = None
    fallo: bool = False


class ProveedorLLM:
    nombre = "LLM"

    async def generar(self, prompt: str) -> str:
        raise NotImplementedError


class ProveedorGemini(ProveedorLLM):
    def __init__(self, api_key: str, modelo: str):
        self.api_key, self.modelo = api_key, modelo
        self.nombre = f"Google Gemini ({modelo})"

    async def generar(self, prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.modelo}:generateContent"
        cuerpo = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.3},
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post(url, json=cuerpo, headers={"x-goog-api-key": self.api_key})
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]


class ProveedorOpenAI(ProveedorLLM):
    def __init__(self, api_key: str, modelo: str):
        self.api_key, self.modelo = api_key, modelo
        self.nombre = f"OpenAI ({modelo})"

    async def generar(self, prompt: str) -> str:
        cuerpo = {
            "model": self.modelo,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
            "temperature": 0.3,
        }
        async with httpx.AsyncClient(timeout=30) as c:
            r = await c.post("https://api.openai.com/v1/chat/completions", json=cuerpo,
                             headers={"Authorization": f"Bearer {self.api_key}"})
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"]


class AgenteIA:
    def __init__(self, proveedor: Optional[ProveedorLLM] = None):
        if proveedor is not None:
            self.proveedor = proveedor
        elif GEMINI_API_KEY:
            self.proveedor = ProveedorGemini(GEMINI_API_KEY, GEMINI_MODEL)
        elif OPENAI_API_KEY:
            self.proveedor = ProveedorOpenAI(OPENAI_API_KEY, OPENAI_MODEL)
        else:
            self.proveedor = None

    async def diagnosticar(self, url: str, scraper: dict, pagespeed: Optional[dict], hallazgos: list[dict]) -> Diagnostico:
        if self.proveedor is None:
            return Diagnostico(
                self._por_reglas(hallazgos), FUENTE_REGLAS,
                "No hay una API key de IA configurada (GEMINI_API_KEY u OPENAI_API_KEY). "
                "Las recomendaciones se generaron con el motor de reglas local.",
            )
        try:
            texto = await self.proveedor.generar(self._prompt(url, scraper, pagespeed, hallazgos))
            recomendaciones = self._parsear(texto)
            return Diagnostico(recomendaciones, self.proveedor.nombre)
        except Exception as e:  # cualquier fallo del servicio externo -> respaldo local
            motivo = "tiempo de espera agotado" if isinstance(e, httpx.TimeoutException) else e.__class__.__name__
            if isinstance(e, httpx.HTTPStatusError):
                motivo = f"HTTP {e.response.status_code}"
            return Diagnostico(
                self._por_reglas(hallazgos), FUENTE_REGLAS,
                f"El servicio de IA ({self.proveedor.nombre}) no respondió ({motivo}). "
                "Se muestran las métricas técnicas y recomendaciones del motor de reglas local. Puedes reintentar.",
                fallo=True,
            )

    # ----------------------------------------------------------------- helpers
    @staticmethod
    def _por_reglas(hallazgos: list[dict]) -> list[dict]:
        return [
            {"severidad": h["severidad"], "categoria": h["categoria"], "titulo": h["problema"], "accion": h["accion"]}
            for h in ordenar(hallazgos)
        ]

    @staticmethod
    def _prompt(url: str, scraper: dict, pagespeed: Optional[dict], hallazgos: list[dict]) -> str:
        resumen_scraper = {k: scraper[k] for k in (
            "title", "meta_description", "encabezados", "imagenes_total", "imagenes_sin_alt",
            "canonical", "lang", "meta_robots", "palabras") if k in scraper}
        return (
            "Eres un consultor SEO y de rendimiento web para PYMES de comercio electrónico en Latinoamérica.\n"
            f"Analizaste la página {url}.\n\n"
            f"Datos On-Page extraídos por el scraper:\n{json.dumps(resumen_scraper, ensure_ascii=False)}\n\n"
            f"Métricas de Google PageSpeed (móvil):\n{json.dumps(pagespeed, ensure_ascii=False) if pagespeed else 'No disponibles'}\n\n"
            f"Hallazgos técnicos detectados:\n{json.dumps(hallazgos, ensure_ascii=False)}\n\n"
            "Redacta un plan de acción priorizado, en español claro y sin tecnicismos innecesarios, "
            "para el dueño de la tienda y su equipo de desarrollo. Usa solo los datos anteriores; no inventes métricas.\n"
            'Responde ÚNICAMENTE con JSON con esta forma: {"recomendaciones": [{"severidad": "Alta|Media|Baja", '
            '"categoria": "SEO|Velocidad", "titulo": "problema en una frase", "accion": "qué hacer, en 1-2 frases"}]}\n'
            "Ordena de mayor a menor severidad e incluye entre 3 y 8 recomendaciones."
        )

    @staticmethod
    def _parsear(texto: str) -> list[dict]:
        texto = texto.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        datos = json.loads(texto)
        lista = datos.get("recomendaciones", []) if isinstance(datos, dict) else datos
        limpias = []
        for r in lista:
            sev = str(r.get("severidad", "")).capitalize()
            if sev not in ORDEN_SEVERIDAD or not r.get("accion"):
                continue
            limpias.append({
                "severidad": sev,
                "categoria": str(r.get("categoria") or "SEO"),
                "titulo": str(r.get("titulo") or ""),
                "accion": str(r["accion"]),
            })
        if not limpias:
            raise ValueError("La IA no devolvió recomendaciones válidas")
        return ordenar(limpias)

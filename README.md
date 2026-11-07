# Auditor SEO & PageSpeed AI

Prototipo funcional de la Actividad 4 de *Análisis y Modelación de Sistemas de Software*
(Corporación Universitaria Iberoamericana). Es un sistema que audita el SEO On-Page y el
rendimiento web de tiendas e-commerce de PYMES y entrega un plan de acción priorizado.

## Módulos

| Módulo | Tecnología | Archivo |
|---|---|---|
| 0. Autenticación | FastAPI + JWT (PyJWT), contraseñas PBKDF2-SHA256 | `app/security.py` |
| 1. Rendimiento | API Google PageSpeed Insights v5 (estrategia móvil) | `app/services/pagespeed.py` |
| 2. Web Scraper | httpx + BeautifulSoup4 (lxml) | `app/services/scraper.py` |
| 3. Agente IA | Gemini u OpenAI (REST); motor de reglas local como respaldo | `app/services/ai_agent.py` |

Más: evaluador de hallazgos y puntaje SEO (`app/services/evaluador.py`), orquestador que ejecuta
el scraper y PageSpeed en paralelo (`app/services/auditor.py`), informe PDF con fpdf2
(`app/services/pdf_report.py`), entidades y repositorios POO sobre SQLite (`app/models.py`) e
interfaz web en HTML/CSS/JS (`app/static/`).

## Instalación y ejecución

```bash
git clone https://github.com/nngg10/seo-pagespeed-ai-auditor.git
cd seo-pagespeed-ai-auditor
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt
python main.py
```

Abrir **http://localhost:8000**. La base de datos SQLite se crea sola en `data/auditor.db`.

## Configuración opcional (`.env`)

Copiar `.env.example` como `.env`:

- `PAGESPEED_API_KEY`: sin clave, Google usa una cuota anónima compartida que suele estar agotada.
  Se obtiene gratis en https://developers.google.com/speed/docs/insights/v5/get-started.
  Si PageSpeed no responde, la auditoría continúa con el análisis On-Page e indica el motivo.
- `GEMINI_API_KEY` u `OPENAI_API_KEY`: activa el agente IA. Sin clave (o si el servicio falla)
  las recomendaciones salen del motor de reglas local y la pantalla lo indica, con opción de reintentar.

## Despliegue en Render

- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.api:app --host 0.0.0.0 --port $PORT`
- Variables: `OPENAI_API_KEY`, `PAGESPEED_API_KEY`, `JWT_SECRET`.

En Render la aplicación visita su propia URL (`/api/salud`) cada 10 minutos para que el plan
gratuito no la suspenda por inactividad (`app/keep_alive.py`). En local esta función no se activa.
La base SQLite de Render es temporal: se reinicia con cada despliegue.

## Historias de usuario cubiertas

| HU | Funcionalidad |
|---|---|
| HU-00 | Registro de usuarios (correo duplicado, validación de contraseña) |
| HU-01 | Login con JWT (credenciales incorrectas rechazadas) |
| HU-02 | Dashboard con tiendas y última auditoría (estado vacío) |
| HU-03 | Auditoría de URL: scraper + PageSpeed en paralelo; error claro si la URL no responde |
| HU-04 | Plan de acción con severidad Alta/Media/Baja y exportación a PDF |
| HU-05 | Agregar, editar y eliminar tiendas (URL inválida o duplicada) |
| HU-06 | Historial por tienda con variación de puntajes frente a la auditoría anterior |
| HU-07 | Cierre de sesión y expiración del token a los 60 minutos (HTTP 401) |

Documentación interactiva de la API: http://localhost:8000/docs

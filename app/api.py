"""API REST (FastAPI) y servidor de la interfaz web."""
import re
from contextlib import asynccontextmanager
from typing import Optional
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import STATIC_DIR
from .database import db
from .keep_alive import KeepAlive
from .models import AuditoriaRepositorio, TiendaRepositorio, Usuario, UsuarioRepositorio
from .security import contrasenas, tokens, usuario_actual
from .services.ai_agent import AgenteIA
from .services.auditor import ScraperError, ServicioAuditoria
from .services.pdf_report import GeneradorReportePDF


@asynccontextmanager
async def ciclo_de_vida(_app):
    db.inicializar()
    keep_alive = KeepAlive.desde_entorno()
    keep_alive.iniciar()
    yield
    await keep_alive.detener()


app = FastAPI(title="Auditor SEO & PageSpeed AI", version="1.0.0", lifespan=ciclo_de_vida)

usuarios = UsuarioRepositorio(db)
tiendas = TiendaRepositorio(db)
auditorias = AuditoriaRepositorio(db)
servicio_auditoria = ServicioAuditoria()
generador_pdf = GeneradorReportePDF()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def error(codigo: int, mensaje: str) -> HTTPException:
    return HTTPException(status_code=codigo, detail=mensaje)


def normalizar_url(url: str) -> str:
    url = (url or "").strip()
    p = urlparse(url)
    if p.scheme not in ("http", "https") or not p.netloc or ("." not in p.netloc and "localhost" not in p.netloc):
        raise error(422, "La URL no es válida. Debe empezar por http:// o https:// (ej. https://mitienda.com).")
    return url.rstrip("/") if p.path in ("", "/") and not p.query else url


# ------------------------------------------------------------------ Esquemas
class RegistroIn(BaseModel):
    nombre: str = ""
    email: str = ""
    password: str = ""
    confirmacion: str = ""


class LoginIn(BaseModel):
    email: str = ""
    password: str = ""


class TiendaIn(BaseModel):
    nombre: str = ""
    url: str = ""


class AuditoriaIn(BaseModel):
    tienda_id: int
    url: Optional[str] = None


# ------------------------------------------------------- HU-00 / HU-01 Auth
@app.post("/api/auth/registro", status_code=201)
def registrar(datos: RegistroIn):
    nombre, email = datos.nombre.strip(), datos.email.strip().lower()
    if len(nombre) < 3:
        raise error(422, "Ingresa tu nombre completo.")
    if not EMAIL_RE.match(email):
        raise error(422, "Ingresa un correo electrónico válido.")
    if len(datos.password) < 8:
        raise error(422, "La contraseña debe tener al menos 8 caracteres.")
    if datos.password != datos.confirmacion:
        raise error(422, "Las contraseñas no coinciden.")
    if usuarios.por_email(email):
        raise error(409, "El correo ya está en uso. Inicia sesión o usa otro correo.")
    usuario = usuarios.crear(nombre, email, contrasenas.generar_hash(datos.password))
    return {"mensaje": "Cuenta creada correctamente.", "usuario": usuario.a_dict()}


@app.post("/api/auth/login")
def login(datos: LoginIn):
    usuario = usuarios.por_email(datos.email.strip())
    if not usuario or not contrasenas.verificar(datos.password, usuario.password_hash):
        raise error(401, "Correo o contraseña incorrectos.")
    token, expira_en = tokens.crear(usuario.id)
    return {"access_token": token, "token_type": "bearer", "expira_en": expira_en, "usuario": usuario.a_dict()}


@app.get("/api/auth/yo")
def yo(usuario: Usuario = Depends(usuario_actual)):
    return usuario.a_dict()


# ---------------------------------------------------- HU-02 / HU-05 Tiendas
def _tienda_con_resumen(t) -> dict:
    historial = auditorias.listar_por_tienda(t.id)
    d = t.a_dict()
    d["total_auditorias"] = len(historial)
    d["ultima_auditoria"] = historial[0].resumen() if historial else None
    return d


@app.get("/api/tiendas")
def listar_tiendas(usuario: Usuario = Depends(usuario_actual)):
    return [_tienda_con_resumen(t) for t in tiendas.listar(usuario.id)]


def _validar_tienda(usuario: Usuario, datos: TiendaIn, excluir_id: Optional[int] = None) -> tuple[str, str]:
    nombre = datos.nombre.strip()
    if len(nombre) < 2:
        raise error(422, "Ingresa el nombre de la tienda.")
    url = normalizar_url(datos.url)
    if tiendas.existe_url(usuario.id, url, excluir_id):
        raise error(409, "Esa URL ya está registrada en tu cuenta.")
    return nombre, url


@app.post("/api/tiendas", status_code=201)
def crear_tienda(datos: TiendaIn, usuario: Usuario = Depends(usuario_actual)):
    nombre, url = _validar_tienda(usuario, datos)
    return tiendas.crear(usuario.id, nombre, url).a_dict()


@app.put("/api/tiendas/{tienda_id}")
def editar_tienda(tienda_id: int, datos: TiendaIn, usuario: Usuario = Depends(usuario_actual)):
    if not tiendas.obtener(usuario.id, tienda_id):
        raise error(404, "Tienda no encontrada.")
    nombre, url = _validar_tienda(usuario, datos, excluir_id=tienda_id)
    return tiendas.actualizar(usuario.id, tienda_id, nombre, url).a_dict()


@app.delete("/api/tiendas/{tienda_id}", status_code=204)
def eliminar_tienda(tienda_id: int, usuario: Usuario = Depends(usuario_actual)):
    if not tiendas.eliminar(usuario.id, tienda_id):
        raise error(404, "Tienda no encontrada.")
    return Response(status_code=204)


# ----------------------------------------------------------- HU-06 Historial
@app.get("/api/tiendas/{tienda_id}/auditorias")
def historial(tienda_id: int, usuario: Usuario = Depends(usuario_actual)):
    tienda = tiendas.obtener(usuario.id, tienda_id)
    if not tienda:
        raise error(404, "Tienda no encontrada.")
    lista = auditorias.listar_por_tienda(tienda_id)
    salida = []
    for i, a in enumerate(lista):
        d = a.resumen()
        previa = lista[i + 1] if i + 1 < len(lista) else None
        d["variacion"] = _variacion(a, previa)
        salida.append(d)
    return {"tienda": tienda.a_dict(), "auditorias": salida}


def _variacion(a, previa) -> Optional[dict]:
    if not previa:
        return None
    dif = lambda x, y: (x - y) if x is not None and y is not None else None  # noqa: E731
    return {"codigo_anterior": previa.codigo, "rendimiento": dif(a.rendimiento, previa.rendimiento),
            "seo": dif(a.seo, previa.seo)}


# ------------------------------------------------- HU-03 / HU-04 Auditorías
@app.post("/api/auditorias", status_code=201)
async def ejecutar_auditoria(datos: AuditoriaIn, usuario: Usuario = Depends(usuario_actual)):
    tienda = tiendas.obtener(usuario.id, datos.tienda_id)
    if not tienda:
        raise error(404, "Tienda no encontrada.")
    url = normalizar_url(datos.url or tienda.url)
    try:
        resultado = await servicio_auditoria.ejecutar(url)
    except ScraperError as e:
        raise error(422, f"No se pudo auditar la URL: {e}")
    return _detalle(auditorias.guardar(tienda.id, resultado))


def _detalle(a) -> dict:
    d = a.a_dict()
    d["variacion"] = _variacion(a, auditorias.anterior(a))
    return d


@app.get("/api/auditorias/{auditoria_id}")
def ver_auditoria(auditoria_id: int, usuario: Usuario = Depends(usuario_actual)):
    a = auditorias.obtener(usuario.id, auditoria_id)
    if not a:
        raise error(404, "Auditoría no encontrada.")
    d = _detalle(a)
    d["tienda"] = tiendas.obtener(usuario.id, a.tienda_id).a_dict()
    return d


@app.post("/api/auditorias/{auditoria_id}/diagnostico")
async def reintentar_diagnostico(auditoria_id: int, usuario: Usuario = Depends(usuario_actual)):
    a = auditorias.obtener(usuario.id, auditoria_id)
    if not a:
        raise error(404, "Auditoría no encontrada.")
    diag = await AgenteIA().diagnosticar(a.url, a.scraper, a.pagespeed or None, a.hallazgos)
    auditorias.actualizar_diagnostico(a.id, diag.recomendaciones, diag.fuente, diag.aviso, diag.fallo)
    return ver_auditoria(auditoria_id, usuario)


@app.get("/api/auditorias/{auditoria_id}/pdf")
def exportar_pdf(auditoria_id: int, usuario: Usuario = Depends(usuario_actual)):
    a = auditorias.obtener(usuario.id, auditoria_id)
    if not a:
        raise error(404, "Auditoría no encontrada.")
    contenido = generador_pdf.generar(a, tiendas.obtener(usuario.id, a.tienda_id))
    return Response(contenido, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="Reporte-{a.codigo}.pdf"'})


@app.get("/api/salud", include_in_schema=False)
def salud():
    return {"estado": "ok"}


# --------------------------------------------------------------- Interfaz
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def inicio():
    return FileResponse(STATIC_DIR / "index.html")

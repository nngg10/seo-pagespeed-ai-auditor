"""Acceso a la base de datos SQLite (sin servidor externo, ideal para el prototipo)."""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .config import DB_PATH

ESQUEMA = """
CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre        TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    creado        TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS tiendas (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    usuario_id INTEGER NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    nombre     TEXT NOT NULL,
    url        TEXT NOT NULL,
    creado     TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (usuario_id, url)
);

CREATE TABLE IF NOT EXISTS auditorias (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    tienda_id        INTEGER NOT NULL REFERENCES tiendas(id) ON DELETE CASCADE,
    codigo           TEXT,
    url              TEXT NOT NULL,
    fecha            TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    duracion_s       REAL,
    http_status      INTEGER,
    rendimiento      INTEGER,
    seo              INTEGER,
    lcp_s            REAL,
    cls              REAL,
    tbt_ms           REAL,
    pagespeed_error  TEXT,
    pagespeed_json   TEXT,
    scraper_json     TEXT,
    hallazgos_json   TEXT,
    recomendaciones_json TEXT,
    ia_fuente        TEXT,
    ia_aviso         TEXT,
    ia_fallo         INTEGER NOT NULL DEFAULT 0
);
"""


class BaseDeDatos:
    """Encapsula la conexión a SQLite y la creación del esquema."""

    def __init__(self, ruta: Path):
        self.ruta = ruta

    def _conectar(self) -> sqlite3.Connection:
        conexion = sqlite3.connect(self.ruta)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        return conexion

    @contextmanager
    def sesion(self):
        conexion = self._conectar()
        try:
            yield conexion
            conexion.commit()
        except Exception:
            conexion.rollback()
            raise
        finally:
            conexion.close()

    def inicializar(self) -> None:
        with self.sesion() as c:
            c.executescript(ESQUEMA)


db = BaseDeDatos(DB_PATH)

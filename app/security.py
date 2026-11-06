"""Módulo 0: autenticación. Hash de contraseñas (PBKDF2) y tokens JWT con expiración."""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import JWT_ALGORITHM, JWT_EXPIRE_MINUTES, JWT_SECRET
from .database import db
from .models import Usuario, UsuarioRepositorio


class GestorContrasenas:
    """Hash PBKDF2-SHA256 con sal aleatoria (librería estándar de Python)."""

    ITERACIONES = 200_000

    def generar_hash(self, contrasena: str) -> str:
        sal = secrets.token_bytes(16)
        derivada = hashlib.pbkdf2_hmac("sha256", contrasena.encode(), sal, self.ITERACIONES)
        return "pbkdf2_sha256${}${}${}".format(
            self.ITERACIONES, base64.b64encode(sal).decode(), base64.b64encode(derivada).decode()
        )

    def verificar(self, contrasena: str, hash_guardado: str) -> bool:
        try:
            _, iteraciones, sal_b64, derivada_b64 = hash_guardado.split("$")
            derivada = hashlib.pbkdf2_hmac(
                "sha256", contrasena.encode(), base64.b64decode(sal_b64), int(iteraciones)
            )
            return hmac.compare_digest(derivada, base64.b64decode(derivada_b64))
        except (ValueError, TypeError):
            return False


class GestorTokens:
    """Emite y valida tokens JWT firmados (HS256) con vigencia limitada."""

    def __init__(self, secreto: str, algoritmo: str, minutos: int):
        self.secreto, self.algoritmo, self.minutos = secreto, algoritmo, minutos

    def crear(self, usuario_id: int) -> tuple[str, int]:
        expira = datetime.now(timezone.utc) + timedelta(minutes=self.minutos)
        token = jwt.encode({"sub": str(usuario_id), "exp": expira}, self.secreto, algorithm=self.algoritmo)
        return token, self.minutos * 60

    def decodificar(self, token: str) -> int:
        datos = jwt.decode(token, self.secreto, algorithms=[self.algoritmo])
        return int(datos["sub"])


contrasenas = GestorContrasenas()
tokens = GestorTokens(JWT_SECRET, JWT_ALGORITHM, JWT_EXPIRE_MINUTES)
_bearer = HTTPBearer(auto_error=False)


def usuario_actual(credenciales: HTTPAuthorizationCredentials = Depends(_bearer)) -> Usuario:
    """Dependencia de FastAPI: exige un JWT válido; si falta o expiró responde 401 (CA-7.2)."""
    no_autorizado = lambda detalle: HTTPException(  # noqa: E731
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detalle, headers={"WWW-Authenticate": "Bearer"}
    )
    if credenciales is None:
        raise no_autorizado("Debes iniciar sesión.")
    try:
        usuario_id = tokens.decodificar(credenciales.credentials)
    except jwt.ExpiredSignatureError:
        raise no_autorizado("Tu sesión ha expirado. Inicia sesión nuevamente.")
    except jwt.InvalidTokenError:
        raise no_autorizado("Token inválido. Inicia sesión nuevamente.")
    usuario = UsuarioRepositorio(db).por_id(usuario_id)
    if usuario is None:
        raise no_autorizado("El usuario ya no existe.")
    return usuario

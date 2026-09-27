"""
Autenticación y roles del Observatorio — CONTRATO compartido.

Este módulo es el ÚNICO lugar donde se define quién es Admin. El resto del
backend lo consume, no lo redefine:

    from auth import requiere_admin
    @app.post("/algo", dependencies=[Depends(requiere_admin)])

Roles
-----
- **admin**   : ha iniciado sesión con las credenciales de `.env`
                (`ADMIN_EMAIL` / `ADMIN_PASSWORD`). Puede recolectar, actualizar
                el histórico, curar informes y generar insights.
- **usuario** : cualquier visitante sin sesión. Solo lectura de análisis, más
                subir y consultar sus propios PDFs.

Contrato HTTP (lo consume `src/lib/auth.tsx` en el frontend)
------------------------------------------------------------
    POST /auth/login   {email, password}  -> {token, rol: "admin", expira_en}
    GET  /auth/yo      Authorization: Bearer <token> -> {rol}
    (cualquier endpoint protegido)  Authorization: Bearer <token>
        401 si falta o es inválido · 403 si el rol no alcanza

Cómo funciona el token
----------------------
No hay tabla de sesiones ni librería externa (ni JWT ni OAuth): un único Admin
con credenciales en `.env` no lo justifica. El token es
`<payload_b64url>.<firma_b64url>`: el payload es JSON ({rol, email, iat, exp})
y la firma es HMAC-SHA256 del payload con `AUTH_SECRET`. Sin el secreto no se
puede fabricar ni alterar un token, y como la expiración va DENTRO del payload
firmado, tampoco se puede estirar. El servidor no guarda nada: "cerrar sesión"
es simplemente que el navegador olvide el token.

Variables de `.env` (ver `.env.example`):
    ADMIN_EMAIL, ADMIN_PASSWORD  credenciales del único Admin.
    AUTH_SECRET                  clave de firma. Si falta se genera una
                                 aleatoria por proceso (ver `_resolver_secreto`).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

# Idempotente (no pisa variables ya cargadas). Se repite aquí, y no solo en
# config.py, porque el secreto se resuelve al importar ESTE módulo y no
# queremos depender del orden de imports de main.py para que AUTH_SECRET exista.
load_dotenv()

router = APIRouter(prefix="/auth", tags=["auth"])

# Vigencia de cada sesión de Admin. 12 h cubre una jornada completa sin obligar
# a re-autenticarse a media tarea y, a la vez, garantiza que un token filtrado
# (p. ej. en un equipo compartido) deje de servir ese mismo día.
TOKEN_VIGENCIA_SEG = 12 * 60 * 60

# Acompaña a todo 401: le dice al cliente qué esquema se espera (RFC 7235).
_WWW_AUTHENTICATE = {"WWW-Authenticate": "Bearer"}


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenInvalido(Exception):
    """Firma incorrecta, formato roto o payload ilegible."""


class TokenExpirado(TokenInvalido):
    """Firma válida pero la sesión ya caducó. Se distingue para poder decírselo al usuario."""


# ─────────────────────────────────────────────────────────────────────────────
# Secreto de firma
# ─────────────────────────────────────────────────────────────────────────────

def _resolver_secreto() -> bytes:
    """Clave HMAC: `AUTH_SECRET` del `.env` o, si falta, una aleatoria por proceso.

    La alternativa sería negarse a arrancar, pero eso tumbaría TODO el backend
    (Tendencias, Informes…) por una variable que solo afecta al login. Mejor
    arrancar y avisar bien claro de la consecuencia.
    """
    secreto = (os.getenv("AUTH_SECRET") or "").strip()
    if secreto:
        return secreto.encode("utf-8")
    print(
        "[!] AUTH_SECRET no está definido en src/backend/.env: se usará un secreto "
        "aleatorio por proceso. Las sesiones de Admin CADUCAN cada vez que el backend "
        "se reinicia (o recarga con --reload). Para sesiones estables agrega "
        "AUTH_SECRET=<cadena aleatoria larga> al .env (ver .env.example)."
    )
    return secrets.token_bytes(32)


_SECRETO = _resolver_secreto()


def _credenciales_admin() -> tuple[str | None, str | None]:
    """Credenciales del Admin, leídas de `.env` (nunca escritas en el código)."""
    return os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")


# ─────────────────────────────────────────────────────────────────────────────
# Token: emitir y validar
# ─────────────────────────────────────────────────────────────────────────────

def _b64url(datos: bytes) -> str:
    """base64 apto para cabeceras/URLs, sin '=' de relleno (como hace JWT)."""
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _des_b64url(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _firmar(payload_b64: str) -> str:
    return _b64url(hmac.new(_SECRETO, payload_b64.encode("utf-8"), hashlib.sha256).digest())


def _iso_utc(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def emitir_token(email: str) -> tuple[str, int]:
    """Crea un token de Admin para `email`. Devuelve (token, epoch de expiración)."""
    ahora = int(time.time())
    expira = ahora + TOKEN_VIGENCIA_SEG
    payload = {"rol": "admin", "email": email, "iat": ahora, "exp": expira}
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    return f"{payload_b64}.{_firmar(payload_b64)}", expira


def validar_token(token: str) -> dict:
    """Devuelve el payload si la firma es correcta y la sesión no ha caducado.

    Lanza TokenExpirado o TokenInvalido. La firma se comprueba ANTES de leer el
    payload: nada de lo que manda el cliente se interpreta sin verificar.
    """
    payload_b64, separador, firma = token.partition(".")
    if not separador or not payload_b64 or not firma:
        raise TokenInvalido()
    # compare_digest en tiempo constante: que nadie pueda adivinar la firma byte
    # a byte midiendo cuánto tarda la respuesta. En bytes porque la variante
    # para str rechaza caracteres no ASCII, y la cabecera viene de fuera.
    if not hmac.compare_digest(_firmar(payload_b64).encode("ascii"), firma.encode("utf-8")):
        raise TokenInvalido()
    try:
        payload = json.loads(_des_b64url(payload_b64))
    except ValueError:  # cubre binascii.Error, JSONDecodeError y UnicodeDecodeError
        raise TokenInvalido()
    if not isinstance(payload, dict) or not isinstance(payload.get("exp"), (int, float)):
        raise TokenInvalido()
    if time.time() >= payload["exp"]:
        raise TokenExpirado()
    return payload


def _token_desde_cabecera(authorization: str | None) -> str | None:
    """Saca el token de `Authorization: Bearer <token>`; None si no viene bien formado."""
    if not authorization:
        return None
    esquema, _, token = authorization.strip().partition(" ")
    token = token.strip()
    if esquema.lower() != "bearer" or not token:
        return None
    return token


# ─────────────────────────────────────────────────────────────────────────────
# Dependencia y rutas
# ─────────────────────────────────────────────────────────────────────────────

def requiere_admin(authorization: str | None = Header(default=None)) -> dict:
    """Dependencia FastAPI: deja pasar solo a un Admin autenticado.

    Devuelve el contexto de sesión ({"rol": "admin", "email": ...}) para quien
    quiera usarlo. Lanza 401 sin token válido y 403 si el rol no alcanza.
    Los mensajes del 401 sí distinguen "falta", "inválido" y "expirado": no
    revelan nada sobre las credenciales y le ahorran al Admin adivinar por qué
    dejó de funcionar (casi siempre, porque venció la sesión).
    """
    token = _token_desde_cabecera(authorization)
    if token is None:
        raise HTTPException(
            status_code=401,
            detail="Esta acción requiere iniciar sesión como Administrador",
            headers=_WWW_AUTHENTICATE,
        )
    try:
        sesion = validar_token(token)
    except TokenExpirado:
        raise HTTPException(
            status_code=401,
            detail="La sesión expiró; vuelve a iniciar sesión",
            headers=_WWW_AUTHENTICATE,
        )
    except TokenInvalido:
        raise HTTPException(status_code=401, detail="Token de sesión inválido", headers=_WWW_AUTHENTICATE)
    if sesion.get("rol") != "admin":
        raise HTTPException(status_code=403, detail="Esta acción es solo para el Administrador")
    return {"rol": "admin", "email": sesion.get("email")}


@router.post("/login")
def login(req: LoginRequest) -> dict:
    """Emite un token de Admin si las credenciales coinciden con `.env`.

    El 401 usa un mensaje neutro (no dice si falló el correo o la contraseña) y
    se evalúan SIEMPRE las dos comparaciones, en tiempo constante, para que ni
    el texto ni el tiempo de respuesta delaten cuál de las dos acertó.
    """
    email_admin, password_admin = _credenciales_admin()
    if not email_admin or not password_admin:
        # Es un problema de despliegue, no del usuario: decirlo claro ahorra
        # una hora de depuración a quien levante el backend sin .env.
        raise HTTPException(
            status_code=503,
            detail="El acceso de Administrador no está configurado en el servidor (ADMIN_EMAIL / ADMIN_PASSWORD)",
        )
    # El correo no distingue mayúsculas (alumni@ y Alumni@ son la misma cuenta);
    # la contraseña sí, tal cual se escribió.
    coincide_email = hmac.compare_digest(
        req.email.strip().lower().encode("utf-8"), email_admin.strip().lower().encode("utf-8")
    )
    coincide_password = hmac.compare_digest(req.password.encode("utf-8"), password_admin.encode("utf-8"))
    if not (coincide_email and coincide_password):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")
    token, expira = emitir_token(email_admin.strip().lower())
    return {"token": token, "rol": "admin", "expira_en": _iso_utc(expira)}


@router.get("/yo")
def yo(authorization: str | None = Header(default=None)) -> dict:
    """Rol de la sesión actual. Sin token válido responde {"rol": "usuario"}.

    Nunca responde 401: es una consulta ("¿quién soy?"), no un acceso. El
    frontend la usa al cargar para descartar tokens caducados sin ruido.
    """
    token = _token_desde_cabecera(authorization)
    if token is None:
        return {"rol": "usuario"}
    try:
        sesion = validar_token(token)
    except TokenInvalido:
        return {"rol": "usuario"}
    if sesion.get("rol") != "admin":
        return {"rol": "usuario"}
    return {"rol": "admin", "email": sesion.get("email"), "expira_en": _iso_utc(sesion["exp"])}

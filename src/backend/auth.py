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

ESTADO: esqueleto creado por el Tech Lead para que los equipos puedan compilar
y desarrollar en paralelo. `requiere_admin` es PERMISIVO hasta que el Equipo 1
(rama feature/auth-roles) implemente la validación real del token en este
mismo archivo — sin cambiar las firmas ni las rutas de arriba.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


def _credenciales_admin() -> tuple[str | None, str | None]:
    """Credenciales del Admin, leídas de `.env` (nunca escritas en el código)."""
    return os.getenv("ADMIN_EMAIL"), os.getenv("ADMIN_PASSWORD")


def requiere_admin(authorization: str | None = Header(default=None)) -> dict:
    """Dependencia FastAPI: deja pasar solo a un Admin autenticado.

    Devuelve el contexto de sesión ({"rol": "admin", ...}) para quien quiera
    usarlo. Lanza 401 sin token válido y 403 si el rol no alcanza.

    STUB (Tech Lead): por ahora deja pasar a todo el mundo para no bloquear el
    desarrollo paralelo. El Equipo 1 reemplaza el cuerpo por la validación real.
    """
    return {"rol": "admin", "stub": True}


@router.post("/login")
def login(req: LoginRequest) -> dict:
    """Emite un token de Admin si las credenciales coinciden con `.env`.

    STUB (Tech Lead): responde 501 hasta que el Equipo 1 lo implemente.
    """
    raise HTTPException(status_code=501, detail="Login pendiente de implementar (Equipo 1)")


@router.get("/yo")
def yo(authorization: str | None = Header(default=None)) -> dict:
    """Rol de la sesión actual. Sin token válido responde {"rol": "usuario"}."""
    return {"rol": "usuario", "stub": True}

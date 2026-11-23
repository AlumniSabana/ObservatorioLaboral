"""Configuración común de las pruebas del backend.

Las pruebas NO tocan la red ni Supabase: las variables de entorno se fijan a
valores ficticios ANTES de importar la app (el módulo de Adzuna crea el cliente
de Supabase al importarse) y los servicios que sí consultan la BD se prueban
con dependencias simuladas.
"""
import os
import sys
from pathlib import Path

# Valores ficticios: bastan para construir el cliente, nunca se hace una petición.
os.environ.setdefault("SUPABASE_URL", "https://prueba.supabase.co")
os.environ.setdefault(
    "SUPABASE_SERVICE_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJyb2xlIjoic2VydmljZV9yb2xlIn0.firma-de-prueba",
)
os.environ["AUTH_SECRET"] = "secreto-solo-para-pruebas"
os.environ["ADMIN_EMAIL"] = "admin@prueba.test"
os.environ["ADMIN_PASSWORD"] = "clave-de-prueba"

# Permite `import traducciones`, `import auth`, etc. como lo hace uvicorn.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

"""Configuración. Se puede sobreescribir con variables de entorno o config.json."""
from __future__ import annotations

import json
import os
from pathlib import Path

BASE = Path(os.environ.get("OFERTAS_HOME", Path.home() / ".ofertas-super"))
BASE.mkdir(parents=True, exist_ok=True)

_DEFAULT = {
    "codigo_postal": "87130",          # Cd. Victoria, Tamaulipas
    "estado": "TAMAULIPAS",
    "municipio": "VICTORIA",
    "tiendas": ["walmart", "aurrera", "heb", "chedraui", "soriana"],
    "umbral_oferta_pct": 15,          # % bajo la mediana histórica para considerarla "buena"
    "dias_historial": 90,
    "tolerancia_precio_antes_pct": 5, # si el "antes" supera el máximo real visto +5% -> sospechoso
    "pausa_segundos": 2.0,            # cortesía entre consultas a cada tienda
    "telegram_token": "",
    "telegram_chat_id": "",
    "smtp": {"host": "", "puerto": 587, "usuario": "", "password": "", "para": ""},
}


def cargar() -> dict:
    cfg = dict(_DEFAULT)
    archivo = BASE / "config.json"
    if archivo.exists():
        cfg.update(json.loads(archivo.read_text(encoding="utf-8")))
    for k in ("telegram_token", "telegram_chat_id", "codigo_postal"):
        v = os.environ.get(f"OFERTAS_{k.upper()}")
        if v:
            cfg[k] = v
    return cfg


def guardar_plantilla() -> Path:
    archivo = BASE / "config.json"
    if not archivo.exists():
        archivo.write_text(json.dumps(_DEFAULT, indent=2, ensure_ascii=False), encoding="utf-8")
    return archivo


DB_PATH = BASE / "precios.sqlite3"
EVIDENCIA_DIR = BASE / "evidencia"

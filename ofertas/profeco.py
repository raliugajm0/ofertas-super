"""Importa datos abiertos de Profeco "Quién es Quién en los Precios" (QQP).

Descarga los CSV mensuales en https://datos.profeco.gob.mx/datos_abiertos/qqp.php
(o datos.gob.mx) y ejecútalos con:  ofertas importar-profeco archivo.csv
Sólo se guardan los registros de tu estado/municipio y de las cadenas configuradas.
"""
from __future__ import annotations

import csv
import io
import unicodedata
import zipfile
from datetime import datetime
from pathlib import Path

from .db import DB
from .modelos import Producto

COLUMNAS = ["producto", "presentacion", "marca", "categoria", "catalogo", "precio", "fecharegistro",
            "cadenacomercial", "giro", "nombrecomercial", "direccion", "estado", "municipio",
            "latitud", "longitud"]

CADENAS = {"walmart": "WALMART", "aurrera": "BODEGA AURRERA", "heb": "HEB", "chedraui": "CHEDRAUI",
           "soriana": "SORIANA", "grand": "GRAND", "lacomer": "LA COMER", "sams": "SAMS"}


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return " ".join(s.upper().replace("'", "").replace(".", " ").replace("-", " ").split())


def _filas(ruta: Path):
    if ruta.suffix.lower() == ".zip":
        with zipfile.ZipFile(ruta) as z:
            for nombre in z.namelist():
                if nombre.lower().endswith(".csv"):
                    with z.open(nombre) as f:
                        yield from _leer(io.TextIOWrapper(f, encoding="latin-1", errors="replace"))
    else:
        with open(ruta, encoding="latin-1", errors="replace", newline="") as f:
            yield from _leer(f)


def _leer(f):
    lector = csv.reader(f)
    primera = next(lector, None)
    if primera is None:
        return
    cab = [_norm(c).lower().replace(" ", "") for c in primera]
    if "producto" in cab and "precio" in cab:
        idx = {c: cab.index(c) for c in COLUMNAS if c in cab}
    else:
        idx = {c: i for i, c in enumerate(COLUMNAS)}
        yield _fila(primera, idx)
    for r in lector:
        yield _fila(r, idx)


def _fila(r, idx):
    return {c: (r[i] if i < len(r) else "") for c, i in idx.items()}


def _cadena(nombre: str, permitidas: list[str]) -> str | None:
    n = _norm(nombre)
    for clave in permitidas:
        patron = CADENAS.get(clave, clave.upper())
        if n.startswith(patron) or (clave == "walmart" and "WAL MART" in n):
            if clave == "walmart" and "AURRERA" in n:
                continue
            return clave
    return None


def importar(ruta: str | Path, db: DB, cfg: dict) -> int:
    estado, municipio = _norm(cfg["estado"]), _norm(cfg["municipio"])
    n = 0
    for f in _filas(Path(ruta)):
        if _norm(f.get("estado", "")) != estado or municipio not in _norm(f.get("municipio", "")):
            continue
        tienda = _cadena(f.get("cadenacomercial", ""), cfg["tiendas"])
        if not tienda:
            continue
        try:
            precio = float(f["precio"])
            fecha = datetime.fromisoformat(f["fecharegistro"][:10])
        except (KeyError, ValueError):
            continue
        nombre = f"{f['producto']} {f.get('presentacion', '')}".strip()
        db.registrar(Producto(tienda=f"profeco:{tienda}", sku=_norm(f"{nombre}|{f.get('marca', '')}"),
                              nombre=nombre, precio=precio, marca=f.get("marca", ""), fecha=fecha),
                     fuente="profeco")
        n += 1
    return n

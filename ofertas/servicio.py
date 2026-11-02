"""Búsqueda simultánea en todas las tiendas + evaluación."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from .adaptadores import TIENDAS
from .analisis import Veredicto, evaluar, guardar_evidencia
from .db import DB
from .modelos import Producto
from .units import precio_unitario

log = logging.getLogger(__name__)


@dataclass
class Resultado:
    producto: Producto
    pid: int
    unitario: tuple[float, str] | None
    veredicto: Veredicto
    evidencia: str | None = None


@dataclass
class Busqueda:
    consulta: str
    resultados: list[Resultado]
    errores: dict[str, str]
    referencia_profeco: list


def _palabras_coinciden(consulta: str, nombre: str) -> bool:
    n = nombre.lower()
    return all(w in n for w in consulta.lower().split() if len(w) > 2 and not w[0].isdigit())


def buscar(consulta: str, db: DB, cfg: dict, tiendas: list[str] | None = None, limite: int = 20) -> Busqueda:
    tiendas = [t for t in (tiendas or cfg["tiendas"]) if t in TIENDAS]
    errores: dict[str, str] = {}

    def una(clave):
        try:
            return TIENDAS[clave](cfg).buscar(consulta, limite)
        except Exception as e:  # noqa: BLE001 - se reporta al usuario
            log.warning("%s falló: %s", clave, e)
            errores[clave] = f"{type(e).__name__}: {e}"[:200]
            return []

    with ThreadPoolExecutor(max_workers=len(tiendas) or 1) as ex:
        listas = list(ex.map(una, tiendas))

    resultados = [evaluar_y_guardar(p, db, cfg) for lista in listas for p in lista]
    resultados.sort(key=clave_orden)
    return Busqueda(consulta, resultados, errores, referencia_profeco(consulta, db))


def evaluar_y_guardar(p: Producto, db: DB, cfg: dict) -> Resultado:
    pid = db.registrar(p)
    hist = [h for h in db.historial(pid, cfg.get("dias_historial", 90))
            if h["fecha"][:10] != p.fecha.strftime("%Y-%m-%d")]
    v = evaluar(p, hist, cfg)
    r = Resultado(p, pid, precio_unitario(p.precio, p.nombre), v)
    if v.sospechosa:
        r.evidencia = guardar_evidencia(p, v)
    return r


def clave_orden(r: Resultado):
    # primero por unidad (kg, l, pz, sin unidad) y luego precio unitario
    if r.unitario:
        return (0, r.unitario[1], r.unitario[0])
    return (1, "", r.producto.precio)


def referencia_profeco(consulta: str, db: DB, dias: int = 120) -> list:
    """Precios levantados por Profeco en tu municipio que coinciden con la búsqueda."""
    filas = db.c.execute(
        "SELECT p.tienda, p.nombre, p.marca, MIN(pr.precio) minimo, MAX(pr.fecha) fecha FROM productos p "
        "JOIN precios pr ON pr.producto_id=p.id WHERE pr.fuente='profeco' AND pr.fecha>=date('now', ?) "
        "GROUP BY p.id ORDER BY minimo", (f"-{dias} day",)).fetchall()
    return [f for f in filas if _palabras_coinciden(consulta, f"{f['nombre']} {f['marca'] or ''}")][:15]

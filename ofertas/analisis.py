"""Evaluación de ofertas: ¿vale la pena? ¿el descuento es real?"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from statistics import median

from .config import EVIDENCIA_DIR
from .modelos import Producto


@dataclass
class Veredicto:
    calificacion: str = "sin historial"   # excelente | buena | normal | cara | sin historial
    ahorro_vs_mediana_pct: float | None = None
    mediana: float | None = None
    minimo: float | None = None
    maximo: float | None = None
    observaciones: int = 0
    alertas: list[str] = field(default_factory=list)  # banderas de posible oferta engañosa

    @property
    def sospechosa(self) -> bool:
        return bool(self.alertas)


def evaluar(p: Producto, historial: list, cfg: dict) -> Veredicto:
    """`historial`: filas con 'precio' y 'precio_antes' (sin incluir la observación actual)."""
    v = Veredicto()
    precios = [float(h["precio"]) for h in historial]
    v.observaciones = len(precios)
    if precios:
        v.mediana, v.minimo, v.maximo = round(median(precios), 2), min(precios), max(precios)
        v.ahorro_vs_mediana_pct = round(100 * (v.mediana - p.precio) / v.mediana, 1)
        umbral = cfg.get("umbral_oferta_pct", 15)
        if p.precio < v.minimo and v.ahorro_vs_mediana_pct >= umbral:
            v.calificacion = "excelente"
        elif v.ahorro_vs_mediana_pct >= umbral:
            v.calificacion = "buena"
        elif v.ahorro_vs_mediana_pct <= -umbral / 2:
            v.calificacion = "cara"
        else:
            v.calificacion = "normal"

    # --- detección de descuentos simulados (arts. 32 y 43 LFPC) ---
    desc = p.descuento_anunciado
    if desc and len(precios) >= 3:
        tol = 1 + cfg.get("tolerancia_precio_antes_pct", 5) / 100
        if p.precio_antes > v.maximo * tol:
            v.alertas.append(
                f"Precio 'antes' ${p.precio_antes:,.2f} nunca se observó: el máximo real en "
                f"{len(precios)} registros fue ${v.maximo:,.2f}.")
        if p.precio >= v.mediana:
            v.alertas.append(
                f"Anuncia {desc}% de descuento, pero el precio actual ${p.precio:,.2f} no es menor "
                f"a su precio habitual (${v.mediana:,.2f}).")
    return v


def guardar_evidencia(p: Producto, v: Veredicto) -> str:
    """Deja constancia fechada para queja ante Profeco o para exigir el precio en caja."""
    EVIDENCIA_DIR.mkdir(parents=True, exist_ok=True)
    ruta = EVIDENCIA_DIR / f"{datetime.now():%Y%m%d-%H%M%S}-{p.tienda}-{p.sku[:40].replace('/', '_')}.json"
    datos = {"capturado": datetime.now().isoformat(timespec="seconds"),
             "producto": {**asdict(p), "fecha": p.fecha.isoformat()},
             "veredicto": asdict(v)}
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(ruta)

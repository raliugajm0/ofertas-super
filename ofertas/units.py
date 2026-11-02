"""Normalización de presentaciones a precio unitario (kg, l, pz)."""
from __future__ import annotations

import re
from dataclasses import dataclass

_NUM = r"(\d+(?:[.,]\d+)?)"

# factor para convertir a la unidad base
_MASA = {"kg": 1.0, "kilo": 1.0, "kilos": 1.0, "g": 0.001, "gr": 0.001, "grs": 0.001, "gramos": 0.001, "mg": 1e-6}
_VOL = {"l": 1.0, "lt": 1.0, "lts": 1.0, "litro": 1.0, "litros": 1.0, "ml": 0.001, "cc": 0.001}
_PZ = {"pz": 1.0, "pza": 1.0, "pzas": 1.0, "piezas": 1.0, "pieza": 1.0, "unidades": 1.0, "u": 1.0,
       "rollos": 1.0, "rollo": 1.0, "hojas": 1.0, "tabletas": 1.0, "capsulas": 1.0, "cápsulas": 1.0}


@dataclass(frozen=True)
class Cantidad:
    valor: float  # en unidad base
    unidad: str   # "kg", "l" o "pz"


def _num(s: str) -> float:
    return float(s.replace(",", "."))


def parse_cantidad(texto: str) -> Cantidad | None:
    """Extrae la cantidad total de un nombre/presentación.

    Soporta multipacks: "6 pzas de 355 ml", "Paquete 4 x 1 kg", "12x330ml".
    """
    if not texto:
        return None
    t = texto.lower().replace(" ", " ")

    unidades = "|".join(sorted({**_MASA, **_VOL}.keys(), key=len, reverse=True))
    # multipack: N x Q unidad  /  N pzas de Q unidad
    m = re.search(rf"{_NUM}\s*(?:x|pzas?\.? de|piezas de|latas de|botellas de)\s*{_NUM}\s*({unidades})\b", t)
    if m:
        n, q, u = _num(m.group(1)), _num(m.group(2)), m.group(3)
        return _crear(n * q, u)

    m = re.search(rf"{_NUM}\s*({unidades})\b", t)
    if m:
        return _crear(_num(m.group(1)), m.group(2))

    pzs = "|".join(sorted(_PZ.keys(), key=len, reverse=True))
    m = re.search(rf"{_NUM}\s*({pzs})\b", t)
    if m:
        return Cantidad(_num(m.group(1)), "pz")
    return None


def _crear(valor: float, u: str) -> Cantidad:
    if u in _MASA:
        return Cantidad(valor * _MASA[u], "kg")
    return Cantidad(valor * _VOL[u], "l")


def precio_unitario(precio: float, texto: str) -> tuple[float, str] | None:
    c = parse_cantidad(texto)
    if not c or c.valor <= 0:
        return None
    return round(precio / c.valor, 2), c.unidad

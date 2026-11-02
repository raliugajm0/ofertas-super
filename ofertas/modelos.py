from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Producto:
    tienda: str
    sku: str
    nombre: str
    precio: float
    precio_antes: float | None = None  # precio "antes" que anuncia la tienda
    marca: str = ""
    url: str = ""
    imagen: str = ""
    disponible: bool = True
    fecha: datetime = field(default_factory=datetime.now)

    @property
    def descuento_anunciado(self) -> float | None:
        if self.precio_antes and self.precio_antes > self.precio:
            return round(100 * (1 - self.precio / self.precio_antes), 1)
        return None

"""Soriana (experimental): lee los datos estructurados (JSON-LD) y, si no hay,
los atributos de las tarjetas de producto de la búsqueda."""
from __future__ import annotations

import html as htmlmod
import json
import re
from urllib.parse import quote

from ..modelos import Producto
from .base import Adaptador, a_float, json_ld_productos


class Soriana(Adaptador):
    clave, nombre, base = "soriana", "Soriana", "https://www.soriana.com"

    def buscar(self, consulta: str, limite: int = 20) -> list[Producto]:
        html = self.html(f"{self.base}/buscar?q={quote(consulta)}")
        return (json_ld_productos(html, self.clave, self.base) or parsear_tiles(html, self.base))[:limite]


def parsear_tiles(html: str, base: str) -> list[Producto]:
    """Tarjetas SFCC con data-gtm / data-product-tile JSON."""
    salida = []
    for attr in re.findall(r'data-(?:gtm|gtmdata|product)="([^"]+)"', html):
        try:
            d = json.loads(htmlmod.unescape(attr))
        except ValueError:
            continue
        if isinstance(d, dict) and "ecommerce" in d:
            d = (d["ecommerce"].get("items") or [{}])[0]
        precio = a_float(d.get("price"))
        nombre = d.get("name") or d.get("item_name")
        if not (precio and nombre):
            continue
        salida.append(Producto(tienda="soriana", sku=str(d.get("id") or d.get("item_id") or nombre),
                               nombre=nombre, precio=precio, marca=d.get("brand") or d.get("item_brand") or ""))
    return salida

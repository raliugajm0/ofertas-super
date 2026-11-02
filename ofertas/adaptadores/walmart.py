"""Walmart México y Bodega Aurrera (misma plataforma de Walmex).

La página de búsqueda incluye un bloque <script id="__NEXT_DATA__"> con JSON.
Se buscan recursivamente los objetos que tienen "name" y "priceInfo", para
no depender de la ruta exacta (que Walmart cambia con frecuencia).
"""
from __future__ import annotations

import json
import re
from urllib.parse import quote

from ..modelos import Producto
from .base import Adaptador, _recorrer, a_float, json_ld_productos


class WalmartMX(Adaptador):
    clave, nombre, base = "walmart", "Walmart", "https://www.walmart.com.mx"

    def buscar(self, consulta: str, limite: int = 20) -> list[Producto]:
        html = self.html(f"{self.base}/search?q={quote(consulta)}")
        productos = parsear(html, self.clave, self.base) or json_ld_productos(html, self.clave, self.base)
        return productos[:limite]


class BodegaAurrera(WalmartMX):
    clave, nombre, base = "aurrera", "Bodega Aurrera", "https://despensa.bodegaaurrera.com.mx"


def _precio(info, *llaves):
    for k in llaves:
        v = info.get(k) if isinstance(info, dict) else None
        if isinstance(v, dict):
            v = v.get("price") or v.get("priceString")
        f = a_float(v)
        if f:
            return f
    return None


def parsear(html: str, tienda: str, base: str) -> list[Producto]:
    m = re.search(r'<script[^>]*id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return []
    try:
        data = json.loads(m.group(1))
    except ValueError:
        return []
    vistos, salida = set(), []
    for n in _recorrer(data):
        if not (isinstance(n, dict) and n.get("name") and isinstance(n.get("priceInfo"), dict)):
            continue
        sku = str(n.get("usItemId") or n.get("id") or n.get("name"))
        if sku in vistos:
            continue
        precio = _precio(n["priceInfo"], "currentPrice", "linePrice", "itemPrice")
        if not precio:
            continue
        vistos.add(sku)
        antes = _precio(n["priceInfo"], "wasPrice", "listPrice", "comparisonPrice")
        url = n.get("canonicalUrl") or ""
        if url.startswith("/"):
            url = base + url
        img = (n.get("imageInfo") or {}).get("thumbnailUrl") or n.get("image") or ""
        disp = str((n.get("availabilityStatusV2") or {}).get("value") or n.get("availabilityStatus") or "IN_STOCK")
        salida.append(Producto(
            tienda=tienda, sku=sku, nombre=n["name"], precio=precio,
            precio_antes=antes if antes and antes > precio else None,
            marca=n.get("brand") or "", url=url, imagen=img,
            disponible="OUT" not in disp.upper(),
        ))
    return salida

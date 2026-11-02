"""Tiendas sobre la plataforma VTEX (HEB México, Chedraui).

VTEX expone un buscador público de catálogo:
  /api/catalog_system/pub/products/search?ft=<texto>&_from=0&_to=19[&sc=<canal>]
El parámetro `sc` (sales channel) define la región/sucursal de precios; si tu
sucursal maneja precios distintos, configúralo en config.json -> "vtex_sc".
"""
from __future__ import annotations

from urllib.parse import quote

from ..modelos import Producto
from .base import Adaptador, a_float


class VTEX(Adaptador):
    host = ""

    def buscar(self, consulta: str, limite: int = 20) -> list[Producto]:
        url = (f"https://{self.host}/api/catalog_system/pub/products/search"
               f"?ft={quote(consulta)}&_from=0&_to={max(0, min(limite, 50) - 1)}")
        sc = (self.cfg.get("vtex_sc") or {}).get(self.clave)
        if sc:
            url += f"&sc={sc}"
        return parsear(self.get(url, headers={"Accept": "application/json"}).json(), self.clave, self.host)


def parsear(data: list, tienda: str, host: str) -> list[Producto]:
    salida = []
    for p in data or []:
        for item in (p.get("items") or [])[:1]:
            sellers = item.get("sellers") or []
            if not sellers:
                continue
            of = sellers[0].get("commertialOffer") or {}
            precio = a_float(of.get("Price"))
            if not precio:
                continue
            antes = a_float(of.get("ListPrice")) or a_float(of.get("PriceWithoutDiscount"))
            imgs = item.get("images") or []
            link = p.get("link") or ""
            if link.startswith("/"):
                link = f"https://{host}{link}"
            salida.append(Producto(
                tienda=tienda,
                sku=str(item.get("itemId") or p.get("productId")),
                nombre=p.get("productName") or item.get("name", ""),
                precio=precio,
                precio_antes=antes if antes and antes > precio else None,
                marca=p.get("brand", ""),
                url=link,
                imagen=imgs[0].get("imageUrl", "") if imgs else "",
                disponible=bool(of.get("IsAvailable", (of.get("AvailableQuantity") or 0) > 0)),
            ))
    return salida


class HEB(VTEX):
    clave, nombre, host = "heb", "HEB", "www.heb.com.mx"


class Chedraui(VTEX):
    clave, nombre, host = "chedraui", "Chedraui", "www.chedraui.com.mx"

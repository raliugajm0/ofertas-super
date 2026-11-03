"""Tiendas sobre la plataforma VTEX (HEB México, Chedraui).

Se intentan, en orden, tres rutas, porque cada tienda VTEX habilita distintas:
  1. API de catálogo:      /api/catalog_system/pub/products/search?ft=...
  2. Intelligent Search:   /api/io/_v/api/intelligent-search/product_search/?query=...
  3. Página de búsqueda:   /busca?ft=<texto>  o  /<texto>?_q=<texto>&map=ft  (JSON-LD)
Si la tienda responde con un reto antibot, se detiene y lo reporta; no se intenta evadirlo.
El parámetro `sc` (sales channel) define la región/sucursal de precios; si tu
sucursal maneja precios distintos, configúralo en config.json -> "vtex_sc".
"""
from __future__ import annotations

import logging
from urllib.parse import quote

from ..modelos import Producto
from .base import Adaptador, Bloqueado, a_float, json_ld_productos

log = logging.getLogger(__name__)


class SinDatos(Exception):
    """La tienda respondió, pero no con datos de productos."""


def _describir(r) -> str:
    tipo = r.headers.get("Content-Type", "?").split(";")[0]
    inicio = " ".join(r.text[:120].split())
    return f"HTTP {r.status_code}, {tipo}: «{inicio}…»"


class VTEX(Adaptador):
    host = ""

    def _sc(self) -> str:
        sc = (self.cfg.get("vtex_sc") or {}).get(self.clave)
        return f"&sc={sc}" if sc else ""

    def _json(self, url: str):
        r = self.get(url, headers={"Accept": "application/json"})
        try:
            return r.json()
        except ValueError:
            raise SinDatos(_describir(r)) from None

    def ruta_catalogo(self, consulta: str, limite: int) -> list[Producto]:
        url = (f"https://{self.host}/api/catalog_system/pub/products/search"
               f"?ft={quote(consulta)}&_from=0&_to={max(0, min(limite, 50) - 1)}{self._sc()}")
        data = self._json(url)
        if not isinstance(data, list):
            raise SinDatos(f"respuesta inesperada: {str(data)[:120]}")
        return parsear(data, self.clave, self.host)

    def ruta_intelligent_search(self, consulta: str, limite: int) -> list[Producto]:
        url = (f"https://{self.host}/api/io/_v/api/intelligent-search/product_search/"
               f"?query={quote(consulta)}&count={min(limite, 50)}&page=1&locale=es-MX{self._sc()}")
        data = self._json(url)
        if not isinstance(data, dict) or "products" not in data:
            raise SinDatos(f"respuesta inesperada: {str(data)[:120]}")
        return parsear(data["products"], self.clave, self.host)

    def ruta_pagina(self, consulta: str, limite: int) -> list[Producto]:
        q = quote(consulta)
        for url in (f"https://{self.host}/busca?ft={q}", f"https://{self.host}/{q}?_q={q}&map=ft"):
            try:
                productos = json_ld_productos(self.html(url), self.clave, f"https://{self.host}")
            except Bloqueado:
                raise
            except Exception:  # noqa: BLE001 - p. ej. 404 en un formato de URL; se prueba el otro
                continue
            if productos:
                return productos
        raise SinDatos("la página de búsqueda no trae datos de productos legibles")

    def buscar(self, consulta: str, limite: int = 20) -> list[Producto]:
        fallas = []
        for ruta in (self.ruta_catalogo, self.ruta_intelligent_search, self.ruta_pagina):
            try:
                productos = ruta(consulta, limite)
            except Bloqueado:
                raise  # antibot: se respeta y se reporta tal cual
            except SinDatos as e:
                fallas.append(f"{ruta.__name__}: {e}")
                continue
            except Exception as e:  # noqa: BLE001 - se intenta la siguiente ruta
                fallas.append(f"{ruta.__name__}: {type(e).__name__}: {e}")
                continue
            if productos:
                return productos[:limite]
            fallas.append(f"{ruta.__name__}: 0 productos")
        raise SinDatos(f"{self.nombre} no entregó productos por ninguna ruta. " + " | ".join(fallas))


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

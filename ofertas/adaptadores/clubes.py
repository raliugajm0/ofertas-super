"""Clubes de precio: Sam's Club México y City Club.

No publican API. Se prueba su página de búsqueda (varios formatos de URL) y se
leen los datos estructurados (__NEXT_DATA__ o JSON-LD). Si responden con
antibot, se reporta y no se insiste (ver Bloqueado).
"""
from __future__ import annotations

from urllib.parse import quote

from ..modelos import Producto
from . import walmart
from .base import Adaptador, Bloqueado, json_ld_productos


class SinResultadosLegibles(Exception):
    pass


class PorPagina(Adaptador):
    base = ""
    rutas: tuple[str, ...] = ()

    def urls(self, consulta: str) -> list[str]:
        return [self.base + r.format(q=quote(consulta)) for r in self.rutas]

    def buscar(self, consulta: str, limite: int = 20) -> list[Producto]:
        fallas = []
        for url in self.urls(consulta):
            try:
                html = self.html(url)
            except Bloqueado:
                raise
            except Exception as e:  # noqa: BLE001 - 404 en ese formato; se prueba el siguiente
                fallas.append(f"{url}: {type(e).__name__}")
                continue
            productos = walmart.parsear(html, self.clave, self.base) or json_ld_productos(html, self.clave, self.base)
            if productos:
                return productos[:limite]
            fallas.append(f"{url}: sin datos de productos")
        raise SinResultadosLegibles(f"{self.nombre}: " + " | ".join(fallas))


class SamsMX(PorPagina):
    clave, nombre, base = "sams", "Sam's Club", "https://www.sams.com.mx"
    rutas = ("/search?q={q}", "/search/Ntt={q}", "/buscar?q={q}")


class CityClub(PorPagina):
    clave, nombre, base = "cityclub", "City Club", "https://www.cityclub.com.mx"
    rutas = ("/search?q={q}", "/buscar?q={q}", "/catalogsearch/result/?q={q}", "/{q}?_q={q}&map=ft")

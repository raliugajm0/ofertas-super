"""Utilidades comunes a todos los adaptadores de tienda."""
from __future__ import annotations

import json
import logging
import re
import time
from abc import ABC, abstractmethod

import requests

from ..modelos import Producto

log = logging.getLogger(__name__)

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


class Bloqueado(Exception):
    """La tienda rechaza consultas automatizadas (403/429, captcha o reto antibot).

    No se intenta evadir: la tienda se reporta como no disponible y sus precios
    pueden capturarse a mano o tomarse de Profeco.
    """


# Páginas de reto antibot que responden "200 OK" en lugar de datos:
#  - Akamai Bot Manager inyecta <script src="/palabras-con-guiones-sin-extension" async>
#  - PerimeterX, DataDome y Cloudflare tienen marcadores propios
_RETO = re.compile(
    r'<script[^>]+src="/[a-zA-Z0-9]+(?:-[a-zA-Z0-9]+){4,}"|_pxCaptcha|px-captcha|captcha-delivery|'
    r'cf-challenge|challenge-platform|bm-verify|sec-if-cpt', re.I)


def es_reto_antibot(texto: str) -> bool:
    return bool(_RETO.search(texto[:20000])) or "captcha" in texto[:5000].lower()


class Adaptador(ABC):
    clave: str = ""
    nombre: str = ""

    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.s = requests.Session()
        self.s.headers.update({
            "User-Agent": UA,
            "Accept-Language": "es-MX,es;q=0.9",
            "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
        })
        self._ultima = 0.0

    def _pausa(self):
        espera = self.cfg.get("pausa_segundos", 2.0) - (time.time() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        self._ultima = time.time()

    def get(self, url: str, **kw) -> requests.Response:
        self._pausa()
        r = self.s.get(url, timeout=25, **kw)
        if r.status_code in (403, 429) or es_reto_antibot(r.text):
            raise Bloqueado(f"{self.nombre} bloquea las consultas automatizadas (sistema antibot). "
                            f"Captura sus precios a mano o usa los datos de Profeco.")
        r.raise_for_status()
        return r

    def html(self, url: str) -> str:
        return self.get(url).text

    @abstractmethod
    def buscar(self, consulta: str, limite: int = 20) -> list[Producto]: ...


def a_float(v) -> float | None:
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    m = re.search(r"\d[\d,]*(?:\.\d+)?", str(v))
    return float(m.group(0).replace(",", "")) if m else None


def json_ld_productos(html: str, tienda: str, base_url: str = "") -> list[Producto]:
    """Extrae productos de bloques JSON-LD (schema.org Product / ItemList)."""
    salida: list[Producto] = []
    for bloque in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(bloque.strip())
        except ValueError:
            continue
        for nodo in _recorrer(data):
            if not isinstance(nodo, dict) or nodo.get("@type") not in ("Product", ["Product"]):
                continue
            ofertas = nodo.get("offers") or {}
            if isinstance(ofertas, list):
                ofertas = ofertas[0] if ofertas else {}
            precio = a_float(ofertas.get("price") or ofertas.get("lowPrice"))
            if precio is None:
                continue
            url = nodo.get("url") or ofertas.get("url") or ""
            if url.startswith("/"):
                url = base_url + url
            marca = nodo.get("brand")
            if isinstance(marca, dict):
                marca = marca.get("name", "")
            img = nodo.get("image")
            if isinstance(img, list):
                img = img[0] if img else ""
            salida.append(Producto(
                tienda=tienda, sku=str(nodo.get("sku") or nodo.get("productID") or url or nodo.get("name")),
                nombre=nodo.get("name", ""), precio=precio, marca=marca or "", url=url, imagen=img or "",
                disponible="OutOfStock" not in str(ofertas.get("availability", "")),
            ))
    return salida


def _recorrer(x):
    yield x
    if isinstance(x, dict):
        for v in x.values():
            yield from _recorrer(v)
    elif isinstance(x, list):
        for v in x:
            yield from _recorrer(v)

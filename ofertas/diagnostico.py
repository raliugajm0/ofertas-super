"""Guarda lo que responde cada tienda para poder ajustar su adaptador."""
from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import quote

from . import config
from .adaptadores import TIENDAS
from .adaptadores.base import Adaptador


def urls(clave: str, consulta: str) -> list[str]:
    cls = TIENDAS[clave]
    q = quote(consulta)
    if hasattr(cls, "host"):
        h = cls.host
        return [f"https://{h}/api/catalog_system/pub/products/search?ft={q}&_from=0&_to=4",
                f"https://{h}/api/io/_v/api/intelligent-search/product_search/?query={q}&count=5&page=1",
                f"https://{h}/{q}?_q={q}&map=ft"]
    if clave == "soriana":
        return [f"{cls.base}/buscar?q={q}"]
    return [f"{cls.base}/search?q={q}"]


def diagnosticar(clave: str, consulta: str) -> str:
    carpeta = config.BASE / "diagnostico"
    carpeta.mkdir(parents=True, exist_ok=True)
    ad: Adaptador = TIENDAS[clave](config.cargar())
    reporte = {"tienda": clave, "consulta": consulta, "fecha": datetime.now().isoformat(timespec="seconds"),
               "respuestas": []}
    for i, url in enumerate(urls(clave, consulta), 1):
        info = {"url": url}
        try:
            r = ad.s.get(url, timeout=25)
            info.update(status=r.status_code, tipo=r.headers.get("Content-Type"), final=r.url,
                        bytes=len(r.content), inicio=r.text[:1500])
            (carpeta / f"{clave}-{i}.txt").write_text(r.text, encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            info["error"] = f"{type(e).__name__}: {e}"
        reporte["respuestas"].append(info)
    salida = carpeta / f"{clave}-reporte.json"
    salida.write_text(json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(salida)

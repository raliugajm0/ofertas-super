"""Línea de comandos:  ofertas <comando>"""
from __future__ import annotations

import argparse
import logging
import time

from . import config
from .db import DB


def main(argv=None):
    ap = argparse.ArgumentParser(prog="ofertas", description="Comparador de ofertas de supermercado (CP 87130)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("buscar", help="compara un producto en todas las tiendas")
    b.add_argument("consulta", nargs="+")
    b.add_argument("-t", "--tienda", action="append", help="limitar a tienda(s): walmart, aurrera, heb, chedraui, soriana")
    w = sub.add_parser("web", help="abre la interfaz web")
    w.add_argument("--puerto", type=int, default=5000)
    w.add_argument("--host", default="127.0.0.1")
    a = sub.add_parser("alertas", help="revisa la lista de vigilancia y envía avisos")
    a.add_argument("--cada", type=int, metavar="MINUTOS", help="repetir indefinidamente cada N minutos")
    v = sub.add_parser("vigilar", help="agrega un producto a vigilancia")
    v.add_argument("consulta", nargs="+")
    v.add_argument("--objetivo", type=float)
    p = sub.add_parser("importar-profeco", help="importa CSV/ZIP de Quién es Quién en los Precios")
    p.add_argument("archivos", nargs="+")
    sub.add_parser("config", help="crea config.json editable y muestra su ruta")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    cfg = config.cargar()

    if args.cmd == "config":
        print(f"Edita: {config.guardar_plantilla()}")
        return
    db = DB(config.DB_PATH)

    if args.cmd == "buscar":
        from .servicio import buscar
        r = buscar(" ".join(args.consulta), db, cfg, args.tienda)
        for t, e in r.errores.items():
            print(f"[!] {t}: {e}")
        for x in r.resultados:
            p_, v_ = x.producto, x.veredicto
            unit = f"{x.unitario[0]:>9,.2f}/{x.unitario[1]:<2}" if x.unitario else " " * 12
            antes = f" (antes {p_.precio_antes:,.2f})" if p_.precio_antes else ""
            print(f"{p_.tienda:<9} ${p_.precio:>9,.2f} {unit}  {v_.calificacion:<13} {p_.nombre[:60]}{antes}")
            for al in v_.alertas:
                print(f"{'':>10}⚠ {al}")
        for f in r.referencia_profeco:
            print(f"profeco   ${f['minimo']:>9,.2f}  {f['tienda'][8:]:<9} {f['nombre'][:60]}")
    elif args.cmd == "web":
        from .web import crear_app
        print(f"Abre http://{args.host}:{args.puerto}")
        crear_app(db, cfg).run(host=args.host, port=args.puerto)
    elif args.cmd == "alertas":
        from .alertas import revisar
        while True:
            n = revisar(db, cfg)
            print(f"{time.strftime('%Y-%m-%d %H:%M')} — {len(n)} aviso(s)")
            if not args.cada:
                break
            time.sleep(args.cada * 60)
    elif args.cmd == "vigilar":
        db.vigilar(" ".join(args.consulta), args.objetivo)
        print("Agregado.")
    elif args.cmd == "importar-profeco":
        from .profeco import importar
        for f in args.archivos:
            print(f"{f}: {importar(f, db, cfg)} registros de {cfg['municipio']}, {cfg['estado']}")


if __name__ == "__main__":
    main()

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
    c = sub.add_parser("capturar", help="registra un precio de folleto/anaquel (p. ej. GranD)")
    c.add_argument("precio", type=float)
    c.add_argument("producto", nargs="+")
    c.add_argument("--tienda", default="grand")
    c.add_argument("--antes", type=float, help="precio 'antes' que anuncia el folleto")
    c.add_argument("--marca", default="")
    tg = sub.add_parser("telegram", help="asistente para conectar las alertas a tu Telegram")
    tg.add_argument("--token", help="token que te dio @BotFather")
    sub.add_parser("probar-alerta", help="envía un mensaje de prueba a tus canales configurados")
    pr = sub.add_parser("programar", help="revisión automática diaria (Windows, Mac o Linux)")
    pr.add_argument("horas", nargs="*", type=int, help="horas del día, p. ej. 8 19 (por defecto 8 y 19)")
    pr.add_argument("--quitar", action="store_true", help="desactiva la revisión automática")
    pr.add_argument("--estado", action="store_true", help="muestra los horarios programados")
    sub.add_parser("config", help="crea config.json editable y muestra su ruta")
    args = ap.parse_args(argv)

    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    cfg = config.cargar()

    if args.cmd == "config":
        print(f"Edita: {config.guardar_plantilla()}")
        return
    if args.cmd == "telegram":
        return asistente_telegram(args.token)
    if args.cmd == "probar-alerta":
        from .alertas import enviar
        enviar("✅ Prueba de Ofertas Súper: las alertas están funcionando.", cfg)
        print("Enviado (si no configuraste Telegram ni correo, se muestra aquí arriba).")
        return
    if args.cmd == "programar":
        from . import programador
        if args.estado:
            h = programador.estado()
            print("Programado a las: " + ", ".join(h) if h else "No hay revisión automática programada.")
        elif args.quitar:
            print(programador.quitar())
        else:
            try:
                print(programador.programar(args.horas or [8, 19]))
                print(f"Bitácora de cada revisión: {config.LOG_PATH}")
            except (ValueError, RuntimeError, OSError) as e:
                print(f"✗ No pude programar la revisión: {e}")
            except Exception as e:  # noqa: BLE001 - schtasks/crontab con error
                print(f"✗ No pude programar la revisión: {type(e).__name__}: {e}")
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
            try:
                n = revisar(db, cfg)
                linea = f"{time.strftime('%Y-%m-%d %H:%M')} — {len(n)} aviso(s)"
            except Exception as e:  # noqa: BLE001 - que la tarea programada deje rastro
                linea = f"{time.strftime('%Y-%m-%d %H:%M')} — ERROR {type(e).__name__}: {e}"
            print(linea)
            with open(config.LOG_PATH, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
            if not args.cada:
                break
            time.sleep(args.cada * 60)
    elif args.cmd == "vigilar":
        db.vigilar(" ".join(args.consulta), args.objetivo)
        print("Agregado.")
    elif args.cmd == "capturar":
        from .servicio import registrar_captura
        registrar_captura(db, args.tienda, " ".join(args.producto), args.precio, args.antes, args.marca)
        print("Precio registrado.")
    elif args.cmd == "importar-profeco":
        from .profeco import importar
        for f in args.archivos:
            print(f"{f}: {importar(f, db, cfg)} registros de {cfg['municipio']}, {cfg['estado']}")


def asistente_telegram(token: str | None = None) -> None:
    from . import telegram
    print("1) En Telegram busca @BotFather, envíale /newbot y sigue las instrucciones.")
    print("2) Copia el token que te entrega (se ve como 123456789:AAH...).")
    token = (token or input("Pega aquí el token: ")).strip()
    try:
        bot = telegram.validar_bot(token)
    except telegram.ErrorTelegram as e:
        print(f"✗ {e}")
        return
    print(f"✓ Bot válido: @{bot}")
    print(f"3) Abre https://t.me/{bot} en tu celular, toca INICIAR (o envíale 'hola'). Espero hasta 2 minutos...")
    chat = telegram.detectar_chat(token, espera_seg=120)
    if not chat:
        print("✗ No recibí tu mensaje. Escríbele al bot y vuelve a correr: ofertas telegram")
        return
    config.guardar({"telegram_token": token, "telegram_chat_id": chat[0]})
    telegram.enviar(token, chat[0], "✅ Listo. Aquí te avisaré de las ofertas que valen la pena.")
    print(f"✓ Conectado con {chat[1] or 'tu chat'}. Te envié un mensaje de prueba.")


if __name__ == "__main__":
    main()

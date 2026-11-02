"""Interfaz web local: http://127.0.0.1:5000"""
from __future__ import annotations

from flask import Flask, abort, redirect, render_template, request, url_for

from . import config
from .adaptadores import TIENDAS
from .alertas import NOMBRES, revisar
from .analisis import evaluar
from .db import DB
from .modelos import Producto
from .servicio import buscar, recientes_manual, registrar_captura

MANUALES = {"grand": "GranD"}


def crear_app(db: DB | None = None, cfg: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config["db"] = db or DB(config.DB_PATH)
    app.config["cfg"] = cfg or config.cargar()
    app.jinja_env.globals.update(NOMBRES=NOMBRES, TIENDAS=TIENDAS, MANUALES=MANUALES)
    app.jinja_env.filters["mxn"] = lambda v: "" if v is None else f"${v:,.2f}"

    def D() -> DB:
        return app.config["db"]

    def C() -> dict:
        return app.config["cfg"]

    @app.get("/")
    def inicio():
        q = request.args.get("q", "").strip()
        sel = request.args.getlist("t") or C()["tiendas"]
        b = buscar(q, D(), C(), sel) if q else None
        return render_template("inicio.html", q=q, b=b, sel=sel, cfg=C())

    @app.get("/ofertas")
    def ofertas():
        filas = []
        for f in D().ultimos(dias=2):
            if f["tienda"].startswith("profeco:"):
                continue
            p = Producto(tienda=f["tienda"], sku=f["sku"], nombre=f["nombre"], precio=f["precio"],
                         precio_antes=f["precio_antes"], url=f["url"] or "")
            hist = [h for h in D().historial(f["id"], C()["dias_historial"]) if h["fecha"] != f["fecha"]]
            v = evaluar(p, hist, C())
            if v.calificacion in ("excelente", "buena") or v.sospechosa:
                filas.append((f, p, v))
        filas.sort(key=lambda x: -(x[2].ahorro_vs_mediana_pct or 0))
        return render_template("ofertas.html", filas=filas, cfg=C())

    @app.route("/captura", methods=["GET", "POST"])
    def captura():
        aviso = None
        if request.method == "POST":
            f = request.form
            try:
                precio = float(f["precio"])
                antes = float(f["antes"]) if f.get("antes", "").strip() else None
            except ValueError:
                aviso = "Precio inválido."
            else:
                if f.get("nombre", "").strip():
                    registrar_captura(D(), f.get("tienda", "grand"), f["nombre"], precio, antes, f.get("marca", ""))
                    return redirect(url_for("captura", ok=1))
        return render_template("captura.html", filas=recientes_manual(D()), aviso=aviso,
                               ok=request.args.get("ok"), cfg=C())

    @app.route("/ajustes", methods=["GET", "POST"])
    def ajustes():
        from . import programador, telegram
        ok = error = None
        if request.method == "POST":
            accion = request.form.get("accion")
            cfg = C()
            try:
                if accion == "token":
                    token = request.form.get("token", "").strip()
                    bot = telegram.validar_bot(token)
                    config.guardar({"telegram_token": token, "telegram_bot": bot})
                    cfg.update(telegram_token=token, telegram_bot=bot)
                    ok = f"Bot @{bot} conectado. Ahora abre el bot en Telegram, toca INICIAR y luego «Detectar mi chat»."
                elif accion == "detectar":
                    chat = telegram.detectar_chat(cfg.get("telegram_token", ""))
                    if not chat:
                        error = "Aún no veo tu mensaje. Abre el bot en Telegram, toca INICIAR o escríbele «hola», y vuelve a intentar."
                    else:
                        config.guardar({"telegram_chat_id": chat[0]})
                        cfg["telegram_chat_id"] = chat[0]
                        telegram.enviar(cfg["telegram_token"], chat[0],
                                        "✅ Listo. Aquí te avisaré de las ofertas que valen la pena.")
                        ok = f"Conectado con {chat[1] or 'tu chat'}. Revisa tu Telegram: te llegó un mensaje de prueba."
                elif accion == "prueba":
                    telegram.enviar(cfg.get("telegram_token", ""), cfg.get("telegram_chat_id", ""),
                                    "✅ Prueba de Ofertas Súper: las alertas están funcionando.")
                    ok = "Mensaje de prueba enviado."
                elif accion == "programar":
                    horas = [int(h) for h in request.form.getlist("hora")]
                    ok = programador.programar(horas)
                elif accion == "quitar":
                    ok = programador.quitar()
            except (telegram.ErrorTelegram, ValueError, RuntimeError, OSError) as e:
                error = str(e)
            except Exception as e:  # noqa: BLE001 - p. ej. schtasks/crontab con error
                error = f"{type(e).__name__}: {e}"
        bitacora = []
        if config.LOG_PATH.exists():
            bitacora = config.LOG_PATH.read_text(encoding="utf-8").splitlines()[-10:][::-1]
        return render_template("ajustes.html", ok=ok, error=error, cfg=C(),
                               programado=programador.estado(), bitacora=bitacora)

    @app.get("/producto/<int:pid>")
    def producto(pid):
        prod = D().producto(pid) or abort(404)
        hist = D().historial(pid, 365)
        return render_template("producto.html", prod=prod, hist=hist, cfg=C())

    @app.route("/vigilancia", methods=["GET", "POST"])
    def vigilancia():
        if request.method == "POST":
            if request.form.get("borrar"):
                D().borrar_vigilancia(int(request.form["borrar"]))
            elif request.form.get("consulta", "").strip():
                obj = request.form.get("objetivo", "").strip()
                D().vigilar(request.form["consulta"], float(obj) if obj else None)
            return redirect(url_for("vigilancia"))
        return render_template("vigilancia.html", lista=D().vigilancias(), avisos=None, cfg=C())

    @app.post("/vigilancia/revisar")
    def revisar_ahora():
        avisos = revisar(D(), C())
        return render_template("vigilancia.html", lista=D().vigilancias(), avisos=avisos, cfg=C())

    return app

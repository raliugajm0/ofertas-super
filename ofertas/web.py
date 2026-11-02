"""Interfaz web local: http://127.0.0.1:5000"""
from __future__ import annotations

from flask import Flask, abort, redirect, render_template, request, url_for

from . import config
from .adaptadores import TIENDAS
from .alertas import NOMBRES, revisar
from .analisis import evaluar
from .db import DB
from .modelos import Producto
from .servicio import buscar


def crear_app(db: DB | None = None, cfg: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config["db"] = db or DB(config.DB_PATH)
    app.config["cfg"] = cfg or config.cargar()
    app.jinja_env.globals.update(NOMBRES=NOMBRES, TIENDAS=TIENDAS)
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

"""Historial de precios en SQLite."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from .modelos import Producto

ESQUEMA = """
CREATE TABLE IF NOT EXISTS productos(
  id INTEGER PRIMARY KEY, tienda TEXT NOT NULL, sku TEXT NOT NULL, nombre TEXT NOT NULL,
  marca TEXT, url TEXT, imagen TEXT, UNIQUE(tienda, sku));
CREATE TABLE IF NOT EXISTS precios(
  producto_id INTEGER NOT NULL REFERENCES productos(id), fecha TEXT NOT NULL,
  precio REAL NOT NULL, precio_antes REAL, fuente TEXT DEFAULT 'tienda');
CREATE INDEX IF NOT EXISTS ix_precios ON precios(producto_id, fecha);
CREATE TABLE IF NOT EXISTS vigilancia(
  id INTEGER PRIMARY KEY, consulta TEXT NOT NULL, precio_objetivo REAL,
  activo INTEGER DEFAULT 1, creado TEXT);
CREATE TABLE IF NOT EXISTS avisos(
  vigilancia_id INTEGER, producto_id INTEGER, dia TEXT, precio REAL,
  UNIQUE(vigilancia_id, producto_id, dia));
"""


class DB:
    def __init__(self, ruta: Path | str):
        self.c = sqlite3.connect(str(ruta), check_same_thread=False)
        self.c.row_factory = sqlite3.Row
        self.c.executescript(ESQUEMA)

    # --- productos y precios ---
    def registrar(self, p: Producto, fuente: str = "tienda") -> int:
        cur = self.c.execute(
            "INSERT INTO productos(tienda,sku,nombre,marca,url,imagen) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(tienda,sku) DO UPDATE SET nombre=excluded.nombre, "
            "url=COALESCE(NULLIF(excluded.url,''),url), imagen=COALESCE(NULLIF(excluded.imagen,''),imagen) "
            "RETURNING id",
            (p.tienda, p.sku, p.nombre, p.marca, p.url, p.imagen))
        pid = cur.fetchone()[0]
        dia = p.fecha.strftime("%Y-%m-%d")
        # una observación por producto y día (la última gana)
        self.c.execute("DELETE FROM precios WHERE producto_id=? AND substr(fecha,1,10)=? AND fuente=?",
                       (pid, dia, fuente))
        self.c.execute("INSERT INTO precios VALUES(?,?,?,?,?)",
                       (pid, p.fecha.isoformat(timespec="seconds"), p.precio, p.precio_antes, fuente))
        self.c.commit()
        return pid

    def historial(self, pid: int, dias: int = 90) -> list[sqlite3.Row]:
        desde = (datetime.now() - timedelta(days=dias)).isoformat()
        return self.c.execute("SELECT fecha, precio, precio_antes FROM precios WHERE producto_id=? "
                              "AND fecha>=? ORDER BY fecha", (pid, desde)).fetchall()

    def producto(self, pid: int):
        return self.c.execute("SELECT * FROM productos WHERE id=?", (pid,)).fetchone()

    def ultimos(self, dias: int = 2) -> list[sqlite3.Row]:
        desde = (datetime.now() - timedelta(days=dias)).isoformat()
        return self.c.execute(
            "SELECT p.*, pr.precio, pr.precio_antes, pr.fecha FROM productos p JOIN precios pr "
            "ON pr.producto_id=p.id WHERE pr.fecha=(SELECT MAX(fecha) FROM precios WHERE producto_id=p.id) "
            "AND pr.fecha>=?", (desde,)).fetchall()

    # --- vigilancia ---
    def vigilar(self, consulta: str, objetivo: float | None) -> int:
        cur = self.c.execute("INSERT INTO vigilancia(consulta,precio_objetivo,creado) VALUES(?,?,?)",
                             (consulta.strip(), objetivo, datetime.now().isoformat(timespec="seconds")))
        self.c.commit()
        return cur.lastrowid

    def vigilancias(self, solo_activas: bool = True):
        q = "SELECT * FROM vigilancia" + (" WHERE activo=1" if solo_activas else "") + " ORDER BY id"
        return self.c.execute(q).fetchall()

    def borrar_vigilancia(self, vid: int):
        self.c.execute("DELETE FROM vigilancia WHERE id=?", (vid,))
        self.c.commit()

    def ya_avisado(self, vid: int, pid: int, precio: float) -> bool:
        dia = datetime.now().strftime("%Y-%m-%d")
        try:
            self.c.execute("INSERT INTO avisos VALUES(?,?,?,?)", (vid, pid, dia, precio))
            self.c.commit()
            return False
        except sqlite3.IntegrityError:
            return True

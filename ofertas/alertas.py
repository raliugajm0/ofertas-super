"""Alertas: revisa la lista de vigilancia y avisa por Telegram, correo o consola."""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage

from . import telegram
from .db import DB
from .servicio import buscar

log = logging.getLogger(__name__)
NOMBRES = {"walmart": "Walmart", "aurrera": "Bodega Aurrera", "heb": "HEB", "chedraui": "Chedraui",
           "soriana": "Soriana", "grand": "GranD"}


def revisar(db: DB, cfg: dict) -> list[str]:
    mensajes = []
    for vig in db.vigilancias():
        b = buscar(vig["consulta"], db, cfg)
        for r in b.resultados:
            p, v = r.producto, r.veredicto
            if not p.disponible:
                continue
            objetivo = vig["precio_objetivo"]
            motivo = None
            if objetivo and p.precio <= objetivo:
                motivo = f"bajó a tu precio objetivo (${objetivo:,.2f})"
            elif v.calificacion in ("excelente", "buena") and not v.sospechosa:
                motivo = f"{v.ahorro_vs_mediana_pct}% bajo su precio habitual"
            if motivo and not db.ya_avisado(vig["id"], r.pid, p.precio):
                unit = f" (${r.unitario[0]:,.2f}/{r.unitario[1]})" if r.unitario else ""
                mensajes.append(f"🛒 {NOMBRES.get(p.tienda, p.tienda)}: {p.nombre} a ${p.precio:,.2f}{unit} "
                                f"— {motivo}\n{p.url}")
    if mensajes:
        enviar("\n\n".join(mensajes), cfg)
    return mensajes


def enviar(texto: str, cfg: dict) -> None:
    enviado = False
    if cfg.get("telegram_token") and cfg.get("telegram_chat_id"):
        try:
            telegram.enviar(cfg["telegram_token"], cfg["telegram_chat_id"], texto)
            enviado = True
        except telegram.ErrorTelegram as e:
            log.error("Telegram falló: %s", e)
    smtp = cfg.get("smtp") or {}
    if smtp.get("host") and smtp.get("para"):
        try:
            msg = EmailMessage()
            msg["Subject"], msg["From"], msg["To"] = "Ofertas que valen la pena", smtp["usuario"], smtp["para"]
            msg.set_content(texto)
            with smtplib.SMTP(smtp["host"], int(smtp.get("puerto", 587)), timeout=30) as s:
                s.starttls()
                s.login(smtp["usuario"], smtp["password"])
                s.send_message(msg)
            enviado = True
        except (OSError, smtplib.SMTPException) as e:
            log.error("Correo falló: %s", e)
    if not enviado:
        print(texto)

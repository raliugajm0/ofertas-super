"""Conexión con Telegram: validar el bot, detectar tu chat y enviar prueba."""
from __future__ import annotations

import time

import requests

API = "https://api.telegram.org/bot{token}/{metodo}"


class ErrorTelegram(Exception):
    pass


def _llamar(token: str, metodo: str, **params) -> dict | list:
    try:
        r = requests.post(API.format(token=token.strip(), metodo=metodo), data=params, timeout=30)
        data = r.json()
    except (requests.RequestException, ValueError) as e:
        raise ErrorTelegram(f"No pude conectar con Telegram: {e}") from e
    if not data.get("ok"):
        if r.status_code == 401:
            raise ErrorTelegram("El token no es válido. Cópialo completo del mensaje de @BotFather.")
        raise ErrorTelegram(data.get("description", "Error desconocido de Telegram"))
    return data["result"]


def validar_bot(token: str) -> str:
    """Devuelve el @usuario del bot si el token es correcto."""
    return _llamar(token, "getMe")["username"]


def detectar_chat(token: str, espera_seg: int = 0) -> tuple[str, str] | None:
    """Busca el último chat que le escribió al bot. Devuelve (chat_id, nombre) o None."""
    limite = time.time() + espera_seg
    while True:
        for upd in reversed(_llamar(token, "getUpdates", timeout=0)):
            msg = upd.get("message") or upd.get("my_chat_member") or upd.get("channel_post") or {}
            chat = msg.get("chat")
            if chat:
                nombre = chat.get("first_name") or chat.get("title") or chat.get("username") or ""
                return str(chat["id"]), nombre
        if time.time() >= limite:
            return None
        time.sleep(3)


def enviar(token: str, chat_id: str, texto: str) -> None:
    _llamar(token, "sendMessage", chat_id=chat_id, text=texto[:4000], disable_web_page_preview=True)

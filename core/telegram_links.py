"""Vinculación de Telegram con las cuentas de Igris.

Cómo funciona, de principio a fin:

  1. El usuario entra en /u, sección «Conexiones», y pide un código.
  2. Le envía al bot:  /start 123456
  3. Este módulo comprueba que el código existe, no ha caducado y no se ha usado,
     y guarda su chat_id en telegram_links.
  4. A partir de ahí, sus mensajes de Telegram se atienden como SU usuario
     (con sus permisos y sus datos), y sus recordatorios le llegan a ese chat.

Por qué con código y no con el chat_id a secas: si bastara con decir "soy Laura",
cualquiera podría recibir los recordatorios de Laura y preguntarle a Igris por su
correo. El código lo genera el servidor para un usuario ya autenticado y solo
sirve una vez.

La tabla tiene UNIQUE en user_id y en chat_id: una cuenta no puede tener dos
Telegram y un Telegram no puede servir a dos cuentas.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Optional

from core import database
from core.database import TelegramLink, User

logger = logging.getLogger(__name__)


def link_chat(code: str, chat_id: int, username: Optional[str] = None) -> tuple[Optional[int], str]:
    """Vincula un chat al usuario dueño del código.

    Devuelve (user_id, mensaje). Si user_id es None, el mensaje explica el motivo
    para que se lo podamos contestar al usuario por Telegram.
    """
    code = (code or "").strip()
    if not code:
        return None, "Falta el código."

    with database.SessionLocal() as db:
        link = db.query(TelegramLink).filter(TelegramLink.link_code == code).first()
        if link is None:
            return None, (
                "Ese código no es válido. Pídelo de nuevo en la sección «Conexiones» "
                "de tu página de Igris."
            )

        if link.code_expires_at is None or link.code_expires_at < datetime.utcnow():
            link.link_code = None
            link.code_expires_at = None
            db.commit()
            return None, (
                "Ese código ya caducó. Genera uno nuevo en la sección «Conexiones» "
                "de tu página de Igris."
            )

        user = db.query(User).filter(User.id == link.user_id).first()
        if user is None or not user.is_active:
            return None, "Tu cuenta de Igris ya no está activa. Habla con el administrador."

        # Este chat podría estar vinculado antes a otra cuenta. En vez de fallar
        # por la restricción UNIQUE, se suelta de la cuenta anterior: el usuario
        # que escribe ahora es el dueño del chat.
        previous = db.query(TelegramLink).filter(
            TelegramLink.chat_id == chat_id, TelegramLink.user_id != link.user_id
        ).first()
        if previous is not None:
            previous.chat_id = None
            previous.username = None
            previous.linked_at = None
            logger.info("Chat de Telegram %s movido de la cuenta %s a la %s",
                        chat_id, previous.user_id, link.user_id)

        link.chat_id = chat_id
        link.username = username
        link.linked_at = datetime.utcnow()
        # Un solo uso: el código desaparece al vincularse.
        link.link_code = None
        link.code_expires_at = None
        db.commit()

        logger.info("Telegram vinculado: usuario %s <-> chat %s", link.user_id, chat_id)
        return link.user_id, "Listo, tu Telegram quedó vinculado."


def resolve_user(chat_id: int) -> Optional[User]:
    """Usuario dueño de este chat, o None si nadie lo ha vinculado."""
    with database.SessionLocal() as db:
        link = db.query(TelegramLink).filter(TelegramLink.chat_id == chat_id).first()
        if link is None:
            return None
        user = db.query(User).filter(User.id == link.user_id).first()
        if user is None or not user.is_active:
            return None
        # Se devuelve desligado de la sesión de base de datos para poder usarlo
        # después de cerrarla.
        db.expunge(user)
        return user


def chat_for_user(user_id: int) -> Optional[int]:
    """Chat de Telegram vinculado a este usuario (o None)."""
    with database.SessionLocal() as db:
        link = db.query(TelegramLink).filter(TelegramLink.user_id == user_id).first()
        return link.chat_id if link is not None else None


def unlink_chat(chat_id: int) -> Optional[int]:
    """Suelta un chat de su cuenta. Devuelve el user_id que lo tenía."""
    with database.SessionLocal() as db:
        link = db.query(TelegramLink).filter(TelegramLink.chat_id == chat_id).first()
        if link is None:
            return None
        user_id = link.user_id
        link.chat_id = None
        link.username = None
        link.linked_at = None
        db.commit()
        logger.info("Telegram desvinculado: chat %s (usuario %s)", chat_id, user_id)
        return user_id


def is_linked(chat_id: int) -> bool:
    with database.SessionLocal() as db:
        return (
            db.query(TelegramLink).filter(TelegramLink.chat_id == chat_id).first()
            is not None
        )

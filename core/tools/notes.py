"""Notas de IGRIS: anotar, listar, buscar y borrar.

El contenido de una nota es DATO del usuario (puede incluir texto pegado de terceros):
nunca se trata como instrucciones. No se escribe el texto de las notas en los logs
(pueden contener claves).
"""

import asyncio
import logging

from core import database
from core.database import Note
from core.tools._common import (
    THIRD_PARTY_NOTICE, check_delete, format_date_local, normalize, register_delete,
)

logger = logging.getLogger(__name__)

MAX_NOTE_CHARS = 1000
MAX_LISTED = 10
MAX_FOUND = 5
LIST_PREVIEW = 160     # en listas se recorta
FOUND_PREVIEW = 400    # al buscar se muestra casi completa (p. ej. para leer una clave)
SCAN_LIMIT = 1000      # notas más recientes que se revisan al buscar


def _preview(text: str, limit: int) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def rank_notes(rows: list, query: str) -> list:
    """rows: [(id, text, created_at)] del más nuevo al más viejo. Devuelve las que contienen
    alguna palabra de la búsqueda (sin tildes ni mayúsculas), las más completas primero."""
    words = [w for w in normalize(query).split() if len(w) >= 2]
    if not words:
        return []
    scored = []
    for order, (nid, text, created) in enumerate(rows):
        hay = normalize(text)
        score = sum(1 for w in words if w in hay)
        if score:
            scored.append((-score, order, nid, text, created))
    scored.sort()
    return [(nid, text, created) for _, _, nid, text, created in scored]


async def add_note(text: str) -> dict:
    text = (text or "").strip()
    if not text:
        return {"error": "Falta el texto de la nota"}
    truncated = len(text) > MAX_NOTE_CHARS
    text = text[:MAX_NOTE_CHARS]

    def _save():
        with database.SessionLocal() as db:
            n = Note(text=text)
            db.add(n)
            db.commit()
            return n.id

    nid = await asyncio.to_thread(_save)
    logger.info(f"Nota {nid} guardada")
    out = {"estado": "guardada", "id": nid}
    if truncated:
        out["aviso"] = f"La nota era muy larga y se recortó a {MAX_NOTE_CHARS} caracteres"
    return out


async def list_notes() -> dict:
    """Las notas más recientes."""

    def _load():
        with database.SessionLocal() as db:
            total = db.query(Note).count()
            rows = db.query(Note).order_by(Note.created_at.desc(), Note.id.desc()).limit(MAX_LISTED).all()
            return total, [(n.id, n.text, n.created_at) for n in rows]

    total, rows = await asyncio.to_thread(_load)
    if not total:
        return {"total": 0, "mensaje": "No hay notas guardadas"}
    return {
        "total": total,
        "mostradas": len(rows),
        "notas": [
            {"id": nid, "texto": _preview(text, LIST_PREVIEW), "anotada": format_date_local(created)}
            for nid, text, created in rows
        ],
        "aviso": THIRD_PARTY_NOTICE,
    }


async def search_notes(query: str) -> dict:
    """Busca notas por palabras (sin importar tildes ni mayúsculas)."""
    if not normalize(query or ""):
        return {"error": "Falta qué buscar"}

    def _load():
        with database.SessionLocal() as db:
            rows = db.query(Note).order_by(Note.created_at.desc(), Note.id.desc()).limit(SCAN_LIMIT).all()
            return [(n.id, n.text, n.created_at) for n in rows]

    ranked = rank_notes(await asyncio.to_thread(_load), query)
    if not ranked:
        return {"total": 0, "mensaje": "No encontré notas sobre eso"}
    return {
        "total": len(ranked),
        "mostradas": min(len(ranked), MAX_FOUND),
        "notas": [
            {"id": nid, "texto": _preview(text, FOUND_PREVIEW), "anotada": format_date_local(created)}
            for nid, text, created in ranked[:MAX_FOUND]
        ],
        "aviso": THIRD_PARTY_NOTICE,
    }


async def delete_note(id: int, _session=None) -> dict:
    """Borra UNA nota por su id (borrado real, no se puede deshacer)."""
    blocked = check_delete(_session)
    if blocked:
        return blocked
    try:
        nid = int(id)
    except (TypeError, ValueError):
        return {"error": "El id de la nota debe ser un número"}

    def _delete():
        with database.SessionLocal() as db:
            n = db.query(Note).filter(Note.id == nid).first()
            if n is None:
                return None
            text = n.text
            db.delete(n)
            db.commit()
            return text

    text = await asyncio.to_thread(_delete)
    if text is None:
        return {"error": "No hay una nota con ese número. Revisa la lista con list_notes"}
    register_delete(_session)
    logger.info(f"Nota {nid} borrada")
    return {"estado": "borrada", "id": nid, "texto": _preview(text, LIST_PREVIEW)}

"""Herramienta para crear documentos Word de verdad.

Devuelve siempre lo que ha pasado: si el archivo se escribió, con qué nombre y
con qué enlace de descarga; si no se pudo, el motivo. El modelo recibe esto como
JSON y debe repetirlo tal cual, sin adornarlo. Así se evita que afirme haber
creado un documento que no existe.
"""

import asyncio
import logging

from core import documents
from core.tools._common import require_user, session_user_id

logger = logging.getLogger(__name__)


async def create_document(
    title: str,
    sections: list = None,
    subtitle: str = "",
    author: str = "",
    cover: bool = True,
    _session=None,
) -> dict:
    """Crea un .docx real en el servidor y devuelve su enlace de descarga."""
    error = require_user(_session)
    if error:
        return error

    user_id = session_user_id(_session)
    title = (title or "").strip()
    if not title:
        return {"error": "Falta el título del documento."}

    if not documents._available():
        # Mensaje explícito: es un fallo del servidor, no del usuario, y no se
        # puede prometer el archivo.
        return {
            "error": (
                "El servidor no tiene instalado python-docx, así que no puedo "
                "crear documentos Word. Avisa al administrador."
            )
        }

    try:
        content = await asyncio.to_thread(
            documents.build_docx,
            title=title,
            subtitle=subtitle or "",
            author=author or "",
            sections=sections or [],
            cover=bool(cover),
        )
    except Exception as exc:
        logger.exception("No se pudo generar el documento")
        return {"error": f"No se pudo generar el documento: {exc}"}

    filename = documents.make_filename(title)
    try:
        path = await asyncio.to_thread(
            documents.save_document, user_id, title, content, filename
        )
    except Exception as exc:
        logger.exception("No se pudo guardar el documento")
        return {"error": f"No se pudo guardar el documento: {exc}"}

    size = len(content)
    result = {
        "ok": True,
        "filename": filename,
        "title": title,
        "sections": documents.section_count(sections or []),
        "size_bytes": size,
        "download_path": f"/api/user/documents/{filename}",
        "message": (
            f"Documento creado: {filename} "
            f"({documents.section_count(sections or [])} secciones, "
            f"{max(1, round(size / 1024))} KB)."
        ),
    }

    # Se guarda en la sesión para que /api/user/chat lo devuelva aparte y la
    # interfaz muestre el botón de descarga sin depender de lo que escriba el modelo.
    registry = getattr(_session, "documents", None)
    if isinstance(registry, list):
        registry.append({
            "filename": filename,
            "title": title,
            "url": result["download_path"],
            "size_bytes": size,
        })

    return result

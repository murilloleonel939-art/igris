"""Herramienta para crear documentos Word de verdad.

Devuelve siempre lo que ha pasado: si el archivo se escribió, con qué nombre y
con qué enlace de descarga; si no se pudo, el motivo. El modelo recibe esto como
JSON y debe repetirlo tal cual, sin adornarlo. Así se evita que afirme haber
creado un documento que no existe.
"""

import asyncio
import base64
import logging

from core import documents
from core.local_agent import hub, run_local_action
from core.tools._common import require_user, session_user_id

logger = logging.getLogger(__name__)


async def _send_to_user_pc(user_id, filename: str, content: bytes, open_after: bool) -> dict:
    """Copia el .docx al computador del usuario a través del agente conectado.

    Devuelve {"ok": True, "path": ...} si se escribió, o {"ok": False, "error": ...}
    con el motivo. Nunca finge que se guardó.
    """
    if not hub.connected:
        return {"ok": False, "error": "El computador del usuario no está conectado."}
    if hub.owner_user_id is not None and hub.owner_user_id != user_id:
        return {"ok": False, "error": "El computador conectado pertenece a otro usuario."}
    try:
        result = await run_local_action(
            "save_document",
            filename=filename,
            content_base64=base64.b64encode(content).decode("ascii"),
            open=bool(open_after),
        )
    except Exception as exc:
        logger.exception("Fallo enviando el documento al equipo")
        return {"ok": False, "error": f"No se pudo enviar al equipo: {exc}"}
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error") or "El equipo rechazó el guardado."}
    return {"ok": True, "path": result.get("path", "")}


async def create_document(
    title: str,
    sections: list = None,
    subtitle: str = "",
    author: str = "",
    cover: bool = True,
    save_to_computer: bool = True,
    open_after: bool = False,
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
    size = len(content)

    # 1) Se intenta dejar el archivo en el computador del usuario, que es donde
    #    debe estar. Copia propia en el servidor solo como respaldo descargable
    #    mientras la sesión siga abierta.
    saved_local = False
    local_path = ""
    local_error = ""
    if save_to_computer:
        sent = await _send_to_user_pc(user_id, filename, content, open_after)
        saved_local = bool(sent.get("ok"))
        local_path = sent.get("path", "")
        local_error = sent.get("error", "")

    try:
        await asyncio.to_thread(
            documents.save_document, user_id, title, content, filename
        )
    except Exception as exc:
        logger.warning("No se pudo guardar la copia en el servidor: %s", exc)

    sections_count = documents.section_count(sections or [])
    if saved_local:
        message = (
            f"Documento guardado en el computador: {local_path} "
            f"({sections_count} secciones, {max(1, round(size / 1024))} KB)."
        )
        if open_after:
            message += " Se abrió en pantalla."
    else:
        message = (
            f"Documento generado, pero NO se guardó en el computador"
            + (f": {local_error}" if local_error else ".")
            + " Queda disponible para descargar."
        )

    result = {
        "ok": True,
        "filename": filename,
        "title": title,
        "sections": sections_count,
        "size_bytes": size,
        "saved_to_computer": saved_local,
        "local_path": local_path,
        "download_path": f"/api/user/documents/{filename}",
        "message": message,
    }
    if local_error:
        result["computer_error"] = local_error

    # Se guarda en la sesión para que /api/user/chat lo devuelva aparte y la
    # interfaz muestre el botón de descarga sin depender de lo que escriba el modelo.
    registry = getattr(_session, "documents", None)
    if isinstance(registry, list):
        registry.append({
            "filename": filename,
            "title": title,
            "url": result["download_path"],
            "size_bytes": size,
            "saved_to_computer": saved_local,
            "local_path": local_path,
        })

    return result

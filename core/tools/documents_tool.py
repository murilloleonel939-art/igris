"""Herramienta para crear documentos directamente en el computador del usuario.

El backend no genera ni guarda el .docx. Solo envía el contenido estructurado al
agente Windows conectado; el ejecutable crea el archivo en la carpeta Documentos.
"""
from __future__ import annotations

import logging

from core import documents
from core.local_agent import hub, run_local_action
from core.tools._common import require_user, session_user_id

logger = logging.getLogger(__name__)


async def create_document(
    title: str,
    sections: list = None,
    format: str = "docx",
    subtitle: str = "",
    author: str = "",
    cover: bool = True,
    save_to_computer: bool = True,
    open_after: bool = False,
    _session=None,
) -> dict:
    """Pide al agente Windows crear localmente un archivo Office o de texto."""
    error = require_user(_session)
    if error:
        return error

    user_id = session_user_id(_session)
    if not isinstance(title, str):
        return {"error": "El título debe ser texto."}
    title = title.strip()
    if not isinstance(format, str):
        return {"error": "El formato debe ser texto: docx, xlsx, pptx, txt o csv."}
    format = (format or "docx").strip().lower()
    formats = {"docx", "xlsx", "pptx", "txt", "csv"}
    if format not in formats:
        return {"error": "Formato no admitido. Usa Word, Excel, PowerPoint, TXT o CSV."}
    if not title:
        return {"error": "Falta el título del documento."}
    if len(title) > documents.MAX_TITLE_CHARS:
        return {"error": "El título supera el límite permitido."}
    if not isinstance(subtitle, str) or not isinstance(author, str):
        return {"error": "Los datos de portada deben ser texto."}
    if len(subtitle) > 500 or len(author) > 500:
        return {"error": "Los datos de portada superan el tamaño permitido."}
    if not save_to_computer:
        return {"error": "La creación de documentos exige guardarlo en el computador."}
    if not hub.connected:
        return {
            "error": (
                "El computador del usuario no está conectado. No se creó ni se guardó "
                "ningún documento. Inicia el IGRIS Windows Agent y vuelve a intentarlo."
            )
        }
    if hub.owner_user_id is None:
        return {"error": "El agente conectado no está vinculado a un usuario. No se creó ningún documento."}
    if hub.owner_user_id != user_id:
        return {"error": "El agente conectado pertenece a otro usuario. No se creó ningún documento."}

    clean_sections = documents.normalize_sections(sections)
    if not clean_sections:
        return {"error": "Incluye al menos una sección o contenido para crear el archivo."}
    filename = documents.make_filename(title).rsplit(".", 1)[0] + "." + format
    try:
        result = await run_local_action(
            "create_document",
            format=format,
            title=title,
            subtitle=subtitle or "",
            author=author or "",
            cover=bool(cover),
            sections=clean_sections,
            filename=filename,
            open=bool(open_after),
        )
    except Exception as exc:
        logger.exception("Fallo creando el documento en el computador")
        return {"error": f"No se pudo crear el documento en el computador: {exc}"}

    if not result.get("ok"):
        return {
            "error": result.get("error") or "El computador rechazó la creación del documento.",
            "saved_to_computer": False,
        }

    saved_filename = result.get("filename") or filename
    local_path = result.get("path", "")
    try:
        size = int(result.get("size_bytes") or 0)
    except (TypeError, ValueError):
        size = 0
    try:
        sections_count = int(result.get("sections") or documents.section_count(clean_sections))
    except (TypeError, ValueError):
        sections_count = documents.section_count(clean_sections)
    message = (
        f"Documento creado y guardado en el computador: {local_path} "
        f"({sections_count} secciones, {max(1, round(size / 1024))} KB)."
    )
    if open_after:
        message += " Se abrió en pantalla."

    result = {
        "ok": True,
        "filename": saved_filename,
        "title": title,
        "sections": sections_count,
        "size_bytes": size,
        "saved_to_computer": True,
        "local_path": local_path,
        "message": message,
    }

    # El frontend muestra la confirmación, pero no ofrece una descarga del servidor:
    # el archivo ya está en el computador del usuario.
    registry = getattr(_session, "documents", None)
    if isinstance(registry, list):
        registry.append({
            "filename": saved_filename,
            "title": title,
            "size_bytes": size,
            "saved_to_computer": True,
            "local_path": local_path,
        })
    return result


__all__ = ["create_document"]

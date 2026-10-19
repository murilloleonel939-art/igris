"""Funciones pequeñas para normalizar metadatos de documentos Word.

El archivo se crea exclusivamente en el computador del usuario mediante el
agente Windows. Este módulo no genera ni guarda archivos.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from typing import Any, Optional

MAX_TITLE_CHARS = 160
MAX_BODY_CHARS = 6000
MAX_SECTIONS = 40


def _slug(text: str) -> str:
    """Nombre de archivo seguro: sin acentos raros, sin rutas, sin espacios."""
    normalized = unicodedata.normalize("NFKD", text or "")
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    cleaned = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text).strip("-").lower()
    return (cleaned or "documento")[:60]


def _clean(value: Any, limit: int = MAX_BODY_CHARS) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:limit]


def normalize_sections(raw: Any) -> list[dict[str, Any]]:
    """Normaliza y limita el texto antes de enviarlo al agente local."""
    if not isinstance(raw, list):
        return []
    sections: list[dict[str, Any]] = []
    total_chars = 0
    for item in raw:
        if len(sections) >= MAX_SECTIONS or total_chars >= MAX_BODY_CHARS * MAX_SECTIONS:
            break
        if isinstance(item, str):
            text = _clean(item, min(MAX_BODY_CHARS, MAX_BODY_CHARS * MAX_SECTIONS - total_chars))
            if text:
                sections.append({"heading": "", "body": [text], "bullets": False})
                total_chars += len(text)
            continue
        if not isinstance(item, dict):
            continue
        if not isinstance(item.get("heading", ""), str) or not isinstance(item.get("title", ""), str):
            continue
        remaining = MAX_BODY_CHARS * MAX_SECTIONS - total_chars
        heading = _clean(item.get("heading") or item.get("title"), min(MAX_TITLE_CHARS, remaining))
        body = item.get("body")
        if not isinstance(item.get("bullets", False), bool):
            continue
        if isinstance(body, str):
            raw_lines = body.splitlines()
        elif isinstance(body, list):
            raw_lines = body[:80]
        else:
            raw_lines = []
        lines = []
        for line in raw_lines:
            remaining = MAX_BODY_CHARS * MAX_SECTIONS - total_chars - len(heading)
            if remaining <= 0 or len(lines) >= 80:
                break
            text = _clean(line, min(MAX_BODY_CHARS, remaining))
            if text:
                lines.append(text)
                total_chars += len(text)
        total_chars += len(heading)
        if heading or lines:
            sections.append({"heading": heading, "body": lines, "bullets": bool(item.get("bullets"))})
    return sections


def make_filename(title: str) -> str:
    """Nombre visible y único: titulo-AAAAMMDD-HHMMSS.docx"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{_slug(title)}-{stamp}.docx"


def section_count(sections: Optional[list]) -> int:
    return len(normalize_sections(sections))

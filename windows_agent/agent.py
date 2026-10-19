"""Agente Windows de IGRIS. Ejecutar al iniciar sesión, sin permisos de administrador."""
from __future__ import annotations

import asyncio
import base64
import ctypes
import json
import os
import struct
import subprocess
import time
import webbrowser
import socket
import sys
import zlib
from pathlib import Path
from urllib.parse import quote, urlparse

import websockets


ALLOWED_HOSTS = {"www.google.com", "google.com", "www.youtube.com", "youtube.com", "open.spotify.com", "www.spotify.com", "store.steampowered.com", "www.bing.com", "quotex.com", "www.quotex.com"}

def enumerate_programs() -> list[dict[str, str]]:
    """Obtiene aplicaciones ejecutables desde accesos directos del menú Inicio."""
    roots = [
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
        Path(os.environ.get("APPDATA", "")) / "Microsoft/Windows/Start Menu/Programs",
    ]
    found: dict[str, dict[str, str]] = {}
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for shortcut in root.rglob("*"):
                if shortcut.suffix.lower() not in {".lnk", ".exe"} or not shortcut.is_file():
                    continue
                name = shortcut.stem.strip()
                if name and name.lower() not in found:
                    found[name.lower()] = {"name": name, "path": str(shortcut)}
        except (OSError, PermissionError):
            continue
    return sorted(found.values(), key=lambda item: item["name"].lower())[:500]


DYNAMIC_PROGRAMS: dict[str, str] = {}


class _BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", ctypes.c_uint32), ("biWidth", ctypes.c_int32), ("biHeight", ctypes.c_int32), ("biPlanes", ctypes.c_uint16), ("biBitCount", ctypes.c_uint16), ("biCompression", ctypes.c_uint32), ("biSizeImage", ctypes.c_uint32), ("biXPelsPerMeter", ctypes.c_int32), ("biYPelsPerMeter", ctypes.c_int32), ("biClrUsed", ctypes.c_uint32), ("biClrImportant", ctypes.c_uint32)]


class _BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", _BITMAPINFOHEADER), ("bmiColors", ctypes.c_uint32 * 3)]


def _png_chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)


def _capture_screen_png() -> str:
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    width, height = user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    if not (1 <= width <= 10000 and 1 <= height <= 10000):
        raise RuntimeError("Tamaño de pantalla no válido")
    desktop = user32.GetDC(0)
    source = gdi32.CreateCompatibleDC(desktop)
    bitmap = gdi32.CreateCompatibleBitmap(desktop, width, height)
    old = gdi32.SelectObject(source, bitmap)
    try:
        if not gdi32.BitBlt(source, 0, 0, width, height, desktop, 0, 0, 0x00CC0020):
            raise RuntimeError("No se pudo capturar la pantalla")
        info = _BITMAPINFO()
        info.bmiHeader.biSize = ctypes.sizeof(_BITMAPINFOHEADER)
        info.bmiHeader.biWidth = width
        info.bmiHeader.biHeight = -height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        pixels = (ctypes.c_ubyte * (width * height * 4))()
        if not gdi32.GetDIBits(source, bitmap, 0, height, pixels, ctypes.byref(info), 0):
            raise RuntimeError("No se pudo leer la pantalla")
        rows = bytearray()
        raw = bytes(pixels)
        for row in range(height):
            rows.append(0)
            for col in range(width):
                i = (row * width + col) * 4
                rows.extend((raw[i + 2], raw[i + 1], raw[i], 255))
        png = b"\\x89PNG\\r\\n\\x1a\\n"
        png += _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        png += _png_chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        png += _png_chunk(b"IEND", b"")
        return base64.b64encode(png).decode("ascii")
    finally:
        gdi32.SelectObject(source, old)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(source)
        user32.ReleaseDC(0, desktop)


def _window_text(hwnd: int) -> str:
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buffer = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buffer, length + 1)
    return buffer.value.strip()


def enumerate_windows() -> list[dict[str, str | int]]:
    windows: list[dict[str, str | int]] = []
    callback_type = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)

    def callback(hwnd, _lparam):
        if ctypes.windll.user32.IsWindowVisible(hwnd):
            title = _window_text(hwnd)
            if title:
                windows.append({"hwnd": int(hwnd), "title": title[:240]})
        return True

    ctypes.windll.user32.EnumWindows(callback_type(callback), 0)
    return windows[:100]


def _find_window(title: str = "", hwnd_value: int = 0):
    if hwnd_value:
        hwnd = ctypes.c_void_p(hwnd_value)
        if ctypes.windll.user32.IsWindow(hwnd):
            return hwnd
    wanted = title.strip().lower()
    if not wanted:
        return ctypes.windll.user32.GetForegroundWindow()
    for item in enumerate_windows():
        if wanted in str(item["title"]).lower():
            return ctypes.c_void_p(int(item["hwnd"]))
    return None


def _key_event(vk: int, flags: int = 0) -> None:
    ctypes.windll.user32.keybd_event(vk, 0, flags, 0)


PROGRAMS = {
    "chrome": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Google", "Chrome", "Application", "chrome.exe"), os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Google", "Chrome", "Application", "chrome.exe")],
    "edge": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe")],
    "microsoft edge": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft", "Edge", "Application", "msedge.exe")],
    "firefox": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Mozilla Firefox", "firefox.exe")],
    "powerpoint": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft Office", "root", "Office16", "POWERPNT.EXE")],
    "windows powershell": ["powershell.exe"],
    "telegram": [os.path.join(os.environ.get("APPDATA", ""), "Telegram Desktop", "Telegram.exe")],
    "whatsapp": [os.path.join(os.environ.get("LOCALAPPDATA", ""), "WhatsApp", "WhatsApp.exe")],
    "google drive": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Google", "Drive File Stream", "launch.bat")],
    "onedrive": [os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "OneDrive", "OneDrive.exe")],
    "spotify": [os.path.join(os.environ.get("APPDATA", ""), "Spotify", "Spotify.exe")],
    "steam": [os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Steam", "steam.exe")],
    "explorer": ["explorer.exe"],
    "word": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft Office", "root", "Office16", "WINWORD.EXE"), os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Microsoft Office", "root", "Office16", "WINWORD.EXE")],
    "excel": [os.path.join(os.environ.get("PROGRAMFILES", r"C:\\Program Files"), "Microsoft Office", "root", "Office16", "EXCEL.EXE"), os.path.join(os.environ.get("PROGRAMFILES(X86)", r"C:\\Program Files (x86)"), "Microsoft Office", "root", "Office16", "EXCEL.EXE")],
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
}


def execute(command: dict) -> dict:
    action = command.get("action")
    params = command.get("params") or {}
    if action == "capture_screen":
        try:
            image = _capture_screen_png()
            if len(image) > 12_000_000:
                return {"ok": False, "error": "La captura es demasiado grande"}
            return {"ok": True, "image": image, "media_type": "image/png", "message": "Captura actual de la pantalla"}
        except Exception as exc:
            return {"ok": False, "error": f"No pude capturar la pantalla: {exc}"}
    if action == "list_windows":
        return {"ok": True, "windows": enumerate_windows()}
    if action == "focus_window":
        hwnd = _find_window(str(params.get("title", "")), int(params.get("hwnd") or 0))
        if not hwnd:
            return {"ok": False, "error": "No encontré esa ventana"}
        ctypes.windll.user32.ShowWindow(hwnd, 9)
        ctypes.windll.user32.SetForegroundWindow(hwnd)
        return {"ok": True}
    if action == "click":
        try:
            x, y = int(params.get("x")), int(params.get("y"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "Coordenadas inválidas"}
        if not (0 <= x <= 10000 and 0 <= y <= 10000):
            return {"ok": False, "error": "Coordenadas fuera de rango"}
        ctypes.windll.user32.SetCursorPos(x, y)
        ctypes.windll.user32.mouse_event(2, 0, 0, 0, 0)
        ctypes.windll.user32.mouse_event(4, 0, 0, 0, 0)
        return {"ok": True, "x": x, "y": y}
    if action == "press_key":
        key = str(params.get("key", "")).strip().upper()
        keys = {"ENTER": 0x0D, "ESC": 0x1B, "TAB": 0x09, "SPACE": 0x20, "BACKSPACE": 0x08, "UP": 0x26, "DOWN": 0x28, "LEFT": 0x25, "RIGHT": 0x27, "CTRL": 0x11, "ALT": 0x12, "SHIFT": 0x10}
        if len(key) == 1 and key.isalnum():
            vk = ord(key)
        else:
            vk = keys.get(key)
        if vk is None:
            return {"ok": False, "error": "Tecla no permitida"}
        _key_event(vk)
        _key_event(vk, 2)
        return {"ok": True, "key": key}
    if action == "chrome_open_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            return {"ok": False, "error": "URL no permitida"}
        if urlparse(url).hostname not in ALLOWED_HOSTS:
            return {"ok": False, "error": "Sitio no autorizado"}
        chrome = next((candidate for candidate in PROGRAMS["chrome"] if os.path.isfile(candidate)), None)
        if chrome:
            subprocess.Popen([chrome, url], shell=False)
        else:
            webbrowser.get("windows-default").open(url)
        return {"ok": True}
    if action == "chrome_play_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://www.youtube.com/watch?"):
            return {"ok": False, "error": "Video de YouTube no permitido"}
        chrome = next((candidate for candidate in PROGRAMS["chrome"] if os.path.isfile(candidate)), None)
        if chrome:
            subprocess.Popen([chrome, url], shell=False)
        else:
            webbrowser.get("windows-default").open(url)
        # autoplay=1 inicia el video; no enviamos una tecla adicional que pudiera pausarlo.
        time.sleep(3)
        return {"ok": True, "url": url, "message": "Video abierto con reproducción solicitada."}
    if action == "edge_open_url":
        url = params.get("url", "")
        if not isinstance(url, str) or not url.startswith("https://"):
            return {"ok": False, "error": "URL no permitida"}
        edge = next((candidate for candidate in PROGRAMS["edge"] if os.path.isfile(candidate)), None)
        if edge:
            subprocess.Popen([edge, url], shell=False)
        else:
            return {"ok": False, "error": "Microsoft Edge no está instalado"}
        return {"ok": True, "url": url}
    if action == "spotify_search":
        query = str(params.get("query", "")).strip()
        if not query:
            return {"ok": False, "error": "Falta la búsqueda de Spotify"}
        spotify = DYNAMIC_PROGRAMS.get("spotify") or next(
            (path for name, path in DYNAMIC_PROGRAMS.items() if "spotify" in name),
            None,
        ) or next((candidate for candidate in PROGRAMS["spotify"] if os.path.isfile(candidate)), None)
        try:
            if spotify:
                if Path(spotify).suffix.lower() == ".lnk":
                    os.startfile(spotify)
                else:
                    subprocess.Popen([spotify], shell=False)
                time.sleep(2)
            # El protocolo spotify: abre la aplicación instalada, sin pasar por Chrome.
            os.startfile("spotify:search:" + quote(query))
            if params.get("play"):
                # Spotify Desktop enfoca la búsqueda; Enter abre el primer resultado.
                time.sleep(3)
                _key_event(0x0D)
                _key_event(0x0D, 2)
                time.sleep(1)
                # La barra espaciadora inicia o pausa la reproducción del resultado abierto.
                _key_event(0x20)
                _key_event(0x20, 2)
                return {"ok": True, "query": query, "application": "spotify", "playing": True}
            return {"ok": True, "query": query, "application": "spotify", "playing": False}
        except OSError:
            return {"ok": False, "error": "No se encontró la aplicación de Spotify instalada."}
    if action == "steam_search":
        query = params.get("query", "")
        url = "https://store.steampowered.com/search/?term=" + quote(str(query).strip())
        return execute({"action": "chrome_open_url", "params": {"url": url}})
    if action == "search_files":
        query = str(params.get("query", "")).strip().lower()
        folder = str(params.get("folder", "")).strip() or os.path.expanduser("~")
        if not query or not os.path.isdir(folder):
            return {"ok": False, "error": "Búsqueda o carpeta no válida"}
        matches = []
        try:
            for path in Path(folder).rglob("*"):
                if path.is_file() and query in path.name.lower():
                    matches.append(str(path))
                    if len(matches) >= 30:
                        break
        except (OSError, PermissionError) as exc:
            return {"ok": False, "error": f"No se pudo buscar: {exc}"}
        return {"ok": True, "matches": matches, "count": len(matches)}
    if action == "open_file":
        path = os.path.abspath(str(params.get("path", "")))
        if not os.path.isfile(path):
            return {"ok": False, "error": "El archivo no existe"}
        os.startfile(path)
        return {"ok": True, "path": path}
    if action == "create_document":
        # El backend envía solo estructura y texto. El .docx se construye aquí,
        # en el PC del usuario; nunca viaja un archivo terminado ni queda copia
        # temporal en IGRIS.
        file_format = str(params.get("format", "docx")).strip().lower()
        supported_formats = {"docx", "xlsx", "pptx", "txt", "csv"}
        if file_format not in supported_formats:
            return {"ok": False, "error": "Formato no admitido. Usa DOCX, XLSX, PPTX, TXT o CSV."}

        filename = str(params.get("filename", "")).strip()
        if (
            not filename
            or filename != os.path.basename(filename)
            or Path(filename).suffix.lower() != "." + file_format
            or any(ch in filename for ch in '<>:"/\\|?*')
            or filename.startswith(".")
        ):
            return {"ok": False, "error": "Nombre de archivo no permitido"}
        if len(filename) > 120 or filename.endswith((".", " ")):
            return {"ok": False, "error": "Nombre de archivo no permitido"}
        if file_format in {"docx", "xlsx"}:
            try:
                from docx import Document as WordDocument
            except ImportError:
                WordDocument = None
            try:
                from openpyxl import Workbook as ExcelWorkbook
            except ImportError:
                ExcelWorkbook = None
            if file_format == "docx" and WordDocument is None:
                return {"ok": False, "error": "El agente no tiene instalada la dependencia python-docx."}
            if file_format == "xlsx" and ExcelWorkbook is None:
                return {"ok": False, "error": "El agente no tiene instalada la dependencia openpyxl."}
        elif file_format == "pptx":
            try:
                from pptx import Presentation as PowerPointPresentation
            except ImportError:
                PowerPointPresentation = None
            if PowerPointPresentation is None:
                return {"ok": False, "error": "El agente no tiene instalada la dependencia python-pptx."}

        if not isinstance(params.get("title"), str):
            return {"ok": False, "error": "El título debe ser texto"}
        title = params["title"].strip()
        if not title:
            return {"ok": False, "error": "Falta el título del documento"}
        if len(title) > 160:
            return {"ok": False, "error": "El título supera el límite permitido"}
        sections = params.get("sections")
        if not isinstance(sections, list):
            return {"ok": False, "error": "Las secciones no son válidas"}
        if len(sections) > 40:
            return {"ok": False, "error": "El documento tiene demasiadas secciones"}
        total_chars = 0
        for raw in sections:
            if not isinstance(raw, dict):
                return {"ok": False, "error": "Las secciones no son válidas"}
            if not isinstance(raw.get("heading", ""), str) or not isinstance(raw.get("title", ""), str):
                return {"ok": False, "error": "Los encabezados deben ser texto"}
            if not isinstance(raw.get("bullets", False), bool):
                return {"ok": False, "error": "El formato de lista no es válido"}
            heading = raw.get("heading") or raw.get("title") or ""
            body = raw.get("body") or []
            if isinstance(body, str):
                body = [body]
            if not isinstance(body, list) or len(body) > 80 or len(heading) > 160:
                return {"ok": False, "error": "Una sección supera los límites permitidos"}
            for item in body:
                if not isinstance(item, str) or len(item) > 6000:
                    return {"ok": False, "error": "Un párrafo supera los límites permitidos"}
                total_chars += len(item)
            total_chars += len(heading)
        if total_chars > 240000:
            return {"ok": False, "error": "El documento supera el tamaño permitido"}
        has_content = False
        for item in sections:
            raw_body = item.get("body") or []
            if isinstance(raw_body, str):
                raw_body = [raw_body]
            if str(item.get("heading") or item.get("title") or "").strip() or any(
                isinstance(line, str) and line.strip() for line in raw_body
            ):
                has_content = True
                break
        if not has_content:
            return {"ok": False, "error": "Incluye contenido para crear el archivo."}
        for value_name in ("subtitle", "author"):
            value = params.get(value_name, "")
            if not isinstance(value, str):
                return {"ok": False, "error": "Los datos de portada deben ser texto"}
            if len(value) > 500:
                return {"ok": False, "error": "Los datos de portada superan el tamaño permitido"}

        subtitle = str(params.get("subtitle", "")).strip()[:500]
        author = str(params.get("author", "")).strip()[:500]
        if file_format == "docx":
            from docx import Document as WordDocument
            from docx.enum.text import WD_ALIGN_PARAGRAPH
            from docx.shared import Inches, Pt

            doc = WordDocument()
            section = doc.sections[0]
            section.top_margin = Inches(0.7)
            section.bottom_margin = Inches(0.7)
            section.left_margin = Inches(0.85)
            section.right_margin = Inches(0.85)
            normal = doc.styles["Normal"]
            normal.font.name = "Aptos"
            normal.font.size = Pt(10.5)
            if bool(params.get("cover", True)):
                p = doc.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                p.paragraph_format.space_before = Pt(150)
                run = p.add_run(title[:160])
                run.bold = True
                run.font.size = Pt(28)
                if subtitle:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.add_run(subtitle).italic = True
                if author:
                    p = doc.add_paragraph()
                    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                    p.add_run(author)
                doc.add_page_break()
            for raw in sections:
                heading = str(raw.get("heading") or raw.get("title") or "").strip()[:160]
                body = raw.get("body") or []
                if isinstance(body, str):
                    body = [body]
                if heading:
                    doc.add_heading(heading, level=1)
                for item in body[:80]:
                    text = str(item).strip()[:6000]
                    if text:
                        doc.add_paragraph(text, style="List Bullet" if raw.get("bullets") else None)
        elif file_format == "xlsx":
            from openpyxl import Workbook as ExcelWorkbook
            doc = ExcelWorkbook()
            sheet = doc.active
            sheet.title = (title[:31] or "Documento").replace("/", "-").replace("\\", "-")
            rows = [[title]]
            if subtitle:
                rows.append([subtitle])
            if author:
                rows.append(["Autor", author])
            for raw in sections:
                heading = str(raw.get("heading") or raw.get("title") or "").strip()
                if heading:
                    rows.append([heading])
                body = raw.get("body") or []
                if isinstance(body, str):
                    body = body.splitlines()
                for line in body[:80]:
                    text = str(line).strip()[:6000]
                    if text:
                        rows.append([text])
            for row in rows:
                sheet.append(row)
            sheet.column_dimensions["A"].width = 100
        elif file_format == "pptx":
            from pptx import Presentation as PowerPointPresentation

            doc = PowerPointPresentation()
            layout = doc.slide_layouts[0]
            slide = doc.slides.add_slide(layout)
            slide.shapes.title.text = title[:160]
            if len(slide.placeholders) > 1:
                slide.placeholders[1].text = "\n".join(value for value in (subtitle, author) if value)
            if not sections:
                slide = doc.slides.add_slide(doc.slide_layouts[5])
                slide.shapes.title.text = title[:160]
            for raw in sections:
                heading = str(raw.get("heading") or raw.get("title") or "").strip()[:160]
                body = raw.get("body") or []
                if isinstance(body, str):
                    body = body.splitlines()
                slide = doc.slides.add_slide(doc.slide_layouts[1])
                slide.shapes.title.text = heading or title[:160]
                frame = slide.placeholders[1].text_frame
                frame.clear()
                for index, line in enumerate(body[:80]):
                    text = str(line).strip()[:6000]
                    if text:
                        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                        paragraph.text = text
                        paragraph.level = 1 if raw.get("bullets") else 0
        else:
            rows = [title]
            if subtitle:
                rows.append(subtitle)
            if author:
                rows.append(author)
            for raw in sections:
                heading = str(raw.get("heading") or raw.get("title") or "").strip()
                if heading:
                    rows.extend(["", heading])
                body = raw.get("body") or []
                if isinstance(body, str):
                    body = body.splitlines()
                rows.extend(str(line).strip()[:6000] for line in body[:80] if str(line).strip())
            separator = "," if file_format == "csv" else "\n"
            if file_format == "csv":
                import csv
                import io

                buffer = io.StringIO(newline="")
                writer = csv.writer(buffer)
                writer.writerows([[line] for line in rows])
                text_content = buffer.getvalue()
            else:
                text_content = separator.join(rows) + "\n"

        # Windows puede redirigir Documentos a OneDrive u otra ubicación; usa
        # la ruta conocida del shell antes de recurrir a USERPROFILE\Documents.
        folder = None
        try:
            import ctypes
            from ctypes import wintypes

            class GUID(ctypes.Structure):
                _fields_ = [
                    ("Data1", wintypes.DWORD),
                    ("Data2", wintypes.WORD),
                    ("Data3", wintypes.WORD),
                    ("Data4", ctypes.c_ubyte * 8),
                ]

            folder_id = GUID(
                0xFDD39AD0, 0x238F, 0x46AF,
                (ctypes.c_ubyte * 8)(0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7),
            )
            known_folder = wintypes.LPWSTR()
            shell32 = ctypes.windll.shell32
            shell32.SHGetKnownFolderPath.argtypes = [
                ctypes.POINTER(GUID), wintypes.DWORD, wintypes.HANDLE,
                ctypes.POINTER(wintypes.LPWSTR),
            ]
            shell32.SHGetKnownFolderPath.restype = wintypes.HRESULT
            result = shell32.SHGetKnownFolderPath(
                ctypes.byref(folder_id), 0, None, ctypes.byref(known_folder)
            )
            if result == 0 and known_folder.value:
                folder = Path(known_folder.value)
            if known_folder.value:
                ole32 = ctypes.windll.ole32
                ole32.CoTaskMemFree.argtypes = [wintypes.LPVOID]
                ole32.CoTaskMemFree.restype = None
                ole32.CoTaskMemFree(ctypes.cast(known_folder, wintypes.LPVOID))
        except (AttributeError, OSError, TypeError):
            folder = None
        if folder is None:
            folder = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"

        try:
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / filename
            if target.exists():
                return {"ok": False, "error": "Ya existe un archivo con ese nombre; vuelve a intentarlo."}
            if file_format in {"txt", "csv"}:
                target.write_text(text_content, encoding="utf-8-sig" if file_format == "csv" else "utf-8")
            else:
                doc.save(str(target))
        except (OSError, PermissionError) as exc:
            return {"ok": False, "error": f"No se pudo guardar el documento: {exc}"}
        if params.get("open"):
            try:
                os.startfile(str(target))
            except OSError:
                pass
        return {
            "ok": True,
            "path": str(target),
            "filename": filename,
            "size_bytes": target.stat().st_size,
            "sections": len([x for x in sections if isinstance(x, dict)]),
        }
    if action == "type_text":
        text = str(params.get("text", ""))
        if not text:
            return {"ok": False, "error": "Texto vacío"}
        # Usa el portapapeles y Ctrl+V para conservar acentos y saltos de línea.
        import tkinter as tk
        root = tk.Tk(); root.withdraw(); root.clipboard_clear(); root.clipboard_append(text); root.update()
        ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)
        ctypes.windll.user32.keybd_event(0x56, 0, 2, 0)
        ctypes.windll.user32.keybd_event(0x11, 0, 2, 0)
        time.sleep(0.5)
        root.destroy()
        return {"ok": True, "characters": len(text)}
    if action == "system_power":
        power_action = params.get("action")
        wake_after = int(params.get("wake_after_seconds") or 0)
        if power_action == "wake":
            return {"ok": True, "message": "El equipo ya está activo para recibir esta orden."}
        if power_action == "sleep":
            if wake_after:
                # Programa el despertar mediante el Programador de tareas de Windows.
                task_name = "IGRIS-Wake"
                run_at = time.strftime("%H:%M", time.localtime(time.time() + wake_after))
                date_at = time.strftime("%m/%d/%Y", time.localtime(time.time() + wake_after))
                created = subprocess.run(["schtasks", "/Create", "/TN", task_name, "/TR", "cmd /c exit", "/SC", "ONCE", "/ST", run_at, "/SD", date_at, "/F", "/RU", "SYSTEM"], check=False, capture_output=True)
                if created.returncode != 0:
                    return {"ok": False, "error": "No se pudo programar el despertar de Windows."}
                # schtasks crea la tarea, y PowerShell activa la opción WakeToRun.
                subprocess.run(["powershell", "-NoProfile", "-Command", "$settings = New-ScheduledTaskSettingsSet -WakeToRun; Set-ScheduledTask -TaskName 'IGRIS-Wake' -Settings $settings"], check=False, capture_output=True)
                subprocess.run(["powercfg", "/SETACVALUEINDEX", "SCHEME_CURRENT", "SUB_NONE", "RTCWAKE", "1"], check=False, capture_output=True)
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
            return {"ok": True, "message": "El equipo entrará en suspensión."}
        return {"ok": False, "error": "Acción de energía no permitida"}
    if action.startswith("media_"):
        if action not in {"media_play_pause", "media_next", "media_previous"}:
            return {"ok": False, "error": "Acción no permitida"}
        vk = {"media_play_pause": 0xB3, "media_next": 0xB0, "media_previous": 0xB1}[action]
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True}
    if action.startswith("volume_"):
        if action not in {"volume_up", "volume_down", "volume_mute"}:
            return {"ok": False, "error": "Acción no permitida"}
        vk = {"volume_up": 0xAF, "volume_down": 0xAE, "volume_mute": 0xAD}[action]
        ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
        ctypes.windll.user32.keybd_event(vk, 0, 2, 0)
        return {"ok": True}
    if action == "launch_program":
        program = str(params.get("program", "")).strip().lower()
        dynamic_path = DYNAMIC_PROGRAMS.get(program)
        paths = PROGRAMS.get(program)
        builtin_paths = {"calculator": "calc.exe", "calculadora": "calc.exe", "notepad": "notepad.exe", "bloc de notas": "notepad.exe", "chrome": "chrome.exe"}
        if not dynamic_path and not paths and program in builtin_paths:
            paths = [builtin_paths[program]]
        if dynamic_path:
            if not os.path.isfile(dynamic_path) or Path(dynamic_path).suffix.lower() not in {".exe", ".lnk"}:
                return {"ok": False, "error": "La aplicación ya no está disponible"}
            if Path(dynamic_path).suffix.lower() == ".lnk":
                os.startfile(dynamic_path)
            else:
                subprocess.Popen([dynamic_path], shell=False)
            return {"ok": True, "program": program}
        if not paths:
            return {"ok": False, "error": "Programa no autorizado"}
        path = next((candidate for candidate in paths if os.path.isfile(candidate)), paths[0])
        if os.path.isfile(path) or path in {"explorer.exe", "notepad.exe", "calc.exe"}:
            subprocess.Popen([path], shell=False)
        elif program == "spotify":
            os.startfile("spotify:")
        elif program in {"word", "excel"}:
            # Office también puede estar registrado como aplicación de Windows.
            uri = "ms-word:" if program == "word" else "ms-excel:"
            try:
                os.startfile(uri)
            except OSError:
                return {"ok": False, "error": f"No se encontró {program} instalado"}
        else:
            return {"ok": False, "error": f"No se encontró {program} instalado"}
        return {"ok": True, "program": program}
    return {"ok": False, "error": "Acción desconocida"}


def load_node_token() -> str:
    token = os.environ.get("NODE_TOKEN", "").strip()
    if token:
        return token
    config = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "IGRIS" / "node_token.txt"
    if not config.is_file():
        config = Path(sys.executable if getattr(sys, "frozen", False) else __file__).with_name("node_token.txt")
    try:
        return config.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


async def main() -> None:
    url = "wss://igris.zottagroup.com/api/device/ws"
    token = load_node_token()
    if not token:
        raise RuntimeError("No se encontró NODE_TOKEN. Reinstala el agente y proporciona el token.")
    while True:
        try:
            async with websockets.connect(url, additional_headers={"Authorization": f"Bearer {token}"}, ping_interval=20, ping_timeout=20) as ws:
                await ws.send(json.dumps({
                    "type": "hello",
                    "agent_version": "2.0",
                    "machine_id": socket.gethostname(),
                    "hostname": socket.gethostname(),
                    "programs": enumerate_programs(),
                }))
                hello_result = json.loads(await ws.recv())
                if hello_result.get("type") != "hello_ack":
                    raise RuntimeError("El servidor no aceptó el agente")
                DYNAMIC_PROGRAMS.clear()
                DYNAMIC_PROGRAMS.update({item["name"].lower(): item["path"] for item in enumerate_programs()})
                # El ejecutable se compila sin consola; no usar print aquí.
                while True:
                    raw = await ws.recv()
                    command = json.loads(raw)
                    if command.get("action") == "sync_programs":
                        programs = enumerate_programs()
                        DYNAMIC_PROGRAMS.clear()
                        DYNAMIC_PROGRAMS.update({item["name"].lower(): item["path"] for item in programs})
                        await ws.send(json.dumps({"id": command.get("id"), "result": {"ok": True, "programs": programs}}))
                        continue
                    result = await asyncio.to_thread(execute, command)
                    await ws.send(json.dumps({"id": command.get("id"), "result": result}))
        except Exception as exc:
            # Reintenta en segundo plano sin abrir ni depender de una consola.
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())

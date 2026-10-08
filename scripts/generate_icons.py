#!/usr/bin/env python3
"""
Genera los iconos PNG de la PWA sin dependencias externas.

No hay Pillow en el entorno, así que el PNG se construye a mano: cada fila de
píxeles se codifica como RGBA y el conjunto se comprime con zlib. El formato PNG
exige que cada línea empiece con un byte de filtro (0 = sin filtro), y que los
bloques vayan con su CRC32.

Dibujo: fondo azul oscuro con degradado suave y una "I" de Igris en violeta,
con los bordes suavizados. Se genera una versión normal y otra "maskable",
que lleva el dibujo más pequeño y centrado porque Android recorta el icono en
círculo y se comería los bordes.
"""
import os
import struct
import zlib

BG_TOP = (11, 18, 38)      # #0b1226
BG_BOTTOM = (30, 41, 59)   # #1e293b
ACCENT = (139, 92, 246)    # #8b5cf6
ACCENT_2 = (96, 165, 250)  # #60a5fa


def chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_png(path: str, size: int, pixels) -> None:
    raw = bytearray()
    for y in range(size):
        raw.append(0)  # filtro 0 (None) al inicio de cada línea
        for x in range(size):
            raw.extend(pixels[y][x])

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    png += chunk(b"IEND", b"")

    with open(path, "wb") as fh:
        fh.write(png)


def lerp(a: int, b: int, t: float) -> int:
    return int(round(a + (b - a) * t))


def rounded_alpha(x: float, y: float, cx: float, cy: float, hw: float, hh: float, r: float) -> float:
    """Cobertura de un rectángulo redondeado (0..1), con borde suavizado."""
    dx = max(abs(x - cx) - (hw - r), 0.0)
    dy = max(abs(y - cy) - (hh - r), 0.0)
    dist = (dx * dx + dy * dy) ** 0.5 - r
    # 1 píxel de transición para que no se vean los dientes de sierra
    return max(0.0, min(1.0, 0.5 - dist))


def make_icon(size: int, maskable: bool = False):
    """Devuelve la matriz de píxeles RGBA del icono."""
    # En maskable el dibujo ocupa menos: Android recorta hasta un 20% por lado
    scale = 0.62 if maskable else 0.82
    bar_w = size * 0.115 * (1 if not maskable else 0.95)
    stem_h = size * scale * 0.5
    cap_h = size * 0.042
    gap = size * 0.028

    cx = size / 2.0
    cy = size / 2.0
    radius = bar_w / 2.0

    rows = []
    for y in range(size):
        row = []
        for x in range(size):
            px, py = x + 0.5, y + 0.5

            # Fondo con degradado vertical
            t = py / size
            r = lerp(BG_TOP[0], BG_BOTTOM[0], t)
            g = lerp(BG_TOP[1], BG_BOTTOM[1], t)
            b = lerp(BG_TOP[2], BG_BOTTOM[2], t)

            # La "I": barra superior, tallo y barra inferior
            a = 0.0
            a = max(a, rounded_alpha(px, py, cx, cy - stem_h / 2 - gap - cap_h / 2, bar_w * 1.55, cap_h, cap_h / 2))
            a = max(a, rounded_alpha(px, py, cx, cy + stem_h / 2 + gap + cap_h / 2, bar_w * 1.55, cap_h, cap_h / 2))
            a = max(a, rounded_alpha(px, py, cx, cy, bar_w / 2, stem_h / 2, radius))

            if a > 0:
                # Degradado diagonal en la letra (violeta -> azul)
                mix = max(0.0, min(1.0, ((px / size) + (py / size)) / 2))
                ar = lerp(ACCENT[0], ACCENT_2[0], mix)
                ag = lerp(ACCENT[1], ACCENT_2[1], mix)
                ab = lerp(ACCENT[2], ACCENT_2[2], mix)
                r = lerp(r, ar, a)
                g = lerp(g, ag, a)
                b = lerp(b, ab, a)

            row.append((int(r), int(g), int(b), 255))
        rows.append(row)
    return rows


def main() -> None:
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "web", "public", "icons")
    base = os.path.abspath(base)
    os.makedirs(base, exist_ok=True)

    targets = [
        ("icon-192.png", 192, False),
        ("icon-512.png", 512, False),
        ("icon-maskable-192.png", 192, True),
        ("icon-maskable-512.png", 512, True),
        ("apple-touch-icon.png", 180, False),
        ("favicon-32.png", 32, False),
        ("favicon-16.png", 16, False),
    ]

    for name, size, maskable in targets:
        write_png(os.path.join(base, name), size, make_icon(size, maskable))
        print(f"  {name}  ({size}x{size})")

    print(f"\n✅ {len(targets)} iconos en {base}")


if __name__ == "__main__":
    main()

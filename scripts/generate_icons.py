#!/usr/bin/env python3
"""
Genera los iconos PNG de la PWA a partir de la imagen de Igris
(web/src-assets/igris-icon-source.png) usando Pillow.

- icon-*.png: la imagen recortada a cuadrado y reescalada, a sangre completa.
- icon-maskable-*.png: la misma imagen pero más pequeña y centrada, dejando
  un margen (zona segura) alrededor. Android recorta el icono "maskable" en
  círculo (o en la forma que toque) y si el dibujo llega hasta el borde se
  come partes del personaje.
- apple-touch-icon.png / favicon-*.png: variantes a los tamaños que piden
  iOS y las pestañas del navegador.
"""
import os

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
SOURCE = os.path.join(HERE, "..", "web", "src-assets", "igris-icon-source.png")
OUT = os.path.abspath(os.path.join(HERE, "..", "web", "public", "icons"))


def load_square_source() -> Image.Image:
    """Carga la imagen y la recorta a cuadrado por el centro.

    El origen es más ancho que alto (202x177). Las franjas que sobran a los
    lados son solo fondo (comprobado a mano), así que un recorte centrado no
    corta ninguna parte del personaje.
    """
    im = Image.open(SOURCE).convert("RGB")
    w, h = im.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    return im.crop((left, top, left + side, top + side))


def make_icon(square: Image.Image, size: int) -> Image.Image:
    """Icono normal: a sangre completa, sin márgenes."""
    return square.resize((size, size), Image.LANCZOS)


def make_maskable(square: Image.Image, size: int, safe_ratio: float = 0.82) -> Image.Image:
    """Icono "maskable": el dibujo ocupa `safe_ratio` del lienzo y va centrado.

    El margen se rellena con el propio color de fondo de la imagen (el azul
    de las esquinas, que es uniforme), no con la imagen desenfocada: así el
    borde se ve como una continuación del fondo y no como un marco pegado.
    """
    inner = int(round(size * safe_ratio))
    fg = square.resize((inner, inner), Image.LANCZOS)

    w, h = square.size
    corners = [
        square.getpixel((2, 2)),
        square.getpixel((w - 3, 2)),
        square.getpixel((2, h - 3)),
        square.getpixel((w - 3, h - 3)),
    ]
    bg_color = tuple(sum(c[i] for c in corners) // len(corners) for i in range(3))

    canvas = Image.new("RGB", (size, size), bg_color)
    offset = (size - inner) // 2
    canvas.paste(fg, (offset, offset))
    return canvas


def main() -> None:
    os.makedirs(OUT, exist_ok=True)
    square = load_square_source()
    print(f"Fuente cuadrada: {square.size}")

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
        img = make_maskable(square, size) if maskable else make_icon(square, size)
        path = os.path.join(OUT, name)
        img.save(path, "PNG", optimize=True)
        print(f"  {name}  ({size}x{size}, {os.path.getsize(path)} bytes)")

    print(f"\n✅ {len(targets)} iconos generados en {OUT}")


if __name__ == "__main__":
    main()

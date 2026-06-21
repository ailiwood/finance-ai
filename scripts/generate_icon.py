"""Generate QuantSage application icon (.ico) — 256x256, tech-finance style.

Creates: installer/assets/quantsage.ico
Uses only stdlib: struct + zlib to produce a valid multi-resolution .ico file.
No Pillow dependency required.
"""

import struct
import zlib
from pathlib import Path

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "installer" / "assets"
OUTPUT = OUTPUT_DIR / "quantsage.ico"
OUTPUT_BMP = OUTPUT_DIR / "wizard.bmp"
OUTPUT_BMP_SMALL = OUTPUT_DIR / "wizard_small.bmp"


# ─── Color palette ───
DARK_BG = (8, 12, 34)
MID_BLUE = (20, 30, 60)
CYAN = (40, 200, 230)
GREEN = (70, 220, 140)
RED = (235, 85, 75)
GOLD = (245, 185, 55)
WHITE_DIM = (210, 215, 225)
CIRCUIT_CYAN = (55, 170, 210)


def _draw_rounded_rect(
    px: list, w: int, h: int,
    x0: int, y0: int, x1: int, y1: int,
    r: int, color: tuple,
) -> None:
    """Draw a filled rounded rectangle into pixel array."""
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0), min(w, x1)):
            # Corner distance checks
            in_corner = False
            if x < x0 + r and y < y0 + r:  # top-left
                in_corner = (x - (x0 + r))**2 + (y - (y0 + r))**2 > r*r
            elif x >= x1 - r and y < y0 + r:  # top-right
                in_corner = (x - (x1 - r - 1))**2 + (y - (y0 + r))**2 > r*r
            elif x < x0 + r and y >= y1 - r:  # bottom-left
                in_corner = (x - (x0 + r))**2 + (y - (y1 - r - 1))**2 > r*r
            elif x >= x1 - r and y >= y1 - r:  # bottom-right
                in_corner = (x - (x1 - r - 1))**2 + (y - (y1 - r - 1))**2 > r*r
            if not in_corner:
                px[y][x] = color


def _draw_line(px: list, w: int, h: int, x0: int, y0: int, x1: int, y1: int, thickness: int, color: tuple) -> None:
    """Bresenham-like thick line."""
    dx = abs(x1 - x0)
    dy = abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy

    cx, cy = x0, y0
    while True:
        for tx in range(-thickness, thickness + 1):
            for ty in range(-thickness, thickness + 1):
                px_x, py_y = cx + tx, cy + ty
                if 0 <= px_x < w and 0 <= py_y < h:
                    px[py_y][px_x] = color
        if cx == x1 and cy == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            cx += sx
        if e2 < dx:
            err += dx
            cy += sy


def _draw_filled_circle(px: list, w: int, h: int, cx: int, cy: int, radius: int, color: tuple) -> None:
    for y in range(max(0, cy - radius), min(h, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(w, cx + radius + 1)):
            if (x - cx)**2 + (y - cy)**2 <= radius**2:
                px[y][x] = color


def _draw_rect(px: list, w: int, h: int, x0: int, y0: int, x1: int, y1: int, color: tuple) -> None:
    for y in range(max(0, y0), min(h, y1)):
        for x in range(max(0, x0), min(w, x1)):
            px[y][x] = color


def _build_256_png() -> bytes:
    """Render 256x256 icon as RGBA pixels, encode to PNG."""
    S = 256

    # Initialize with transparent
    px = [[(0, 0, 0, 0) for _ in range(S)] for _ in range(S)]

    # 1. Rounded background rect (navy)
    margin = 16
    _draw_rounded_rect(px, S, S, margin, margin, S - margin, S - margin, 28, (*DARK_BG, 255))

    # 2. Inner panel (lighter navy)
    inner_m = 28
    _draw_rounded_rect(px, S, S, inner_m, inner_m, S - inner_m, S - inner_m, 20, (*MID_BLUE, 200))

    # 3. Central glowing orb (AI core)
    glow_cx, glow_cy = 120, 148
    for r in [48, 36, 26]:
        alpha = {48: 50, 36: 80, 26: 120}[r]
        _draw_filled_circle(px, S, S, glow_cx, glow_cy, r, (30, 180, 220, alpha))

    # 4. Candlestick #1 — Bullish (green) at right
    candle_x = 155
    wick_h = 130
    body_h = 60
    _draw_rect(px, S, S, candle_x - 5, 70, candle_x + 5, 70 + wick_h, (140, 160, 175, 255))  # wick
    _draw_rect(px, S, S, candle_x - 11, 95, candle_x + 11, 95 + body_h, (*GREEN, 255))      # body

    # 5. Candlestick #2 — Bearish (red) at left
    candle_x2 = 75
    wick_h2 = 100
    body_h2 = 45
    _draw_rect(px, S, S, candle_x2 - 5, 95, candle_x2 + 5, 95 + wick_h2, (140, 160, 175, 255))
    _draw_rect(px, S, S, candle_x2 - 11, 100, candle_x2 + 11, 100 + body_h2, (*RED, 255))

    # 6. Candlestick #3 — Small bullish (far right)
    candle_x3 = 195
    _draw_rect(px, S, S, candle_x3 - 3, 110, candle_x3 + 3, 170, (120, 140, 155, 255))
    _draw_rect(px, S, S, candle_x3 - 8, 118, candle_x3 + 8, 150, (*GREEN, 240))

    # 7. Candlestick #4 — Small bullish (between)
    candle_x4 = 115
    _draw_rect(px, S, S, candle_x4 - 3, 52, candle_x4 + 3, 120, (120, 140, 155, 255))
    _draw_rect(px, S, S, candle_x4 - 8, 58, candle_x4 + 8, 95, (*GREEN, 240))

    # 8. Circuit traces — horizontal cyan lines
    _draw_line(px, S, S, 50, 52, 185, 52, 2, (*CIRCUIT_CYAN, 200))
    _draw_line(px, S, S, 55, 72, 190, 72, 2, (*CIRCUIT_CYAN, 160))
    _draw_line(px, S, S, 48, 190, 200, 190, 2, (*CIRCUIT_CYAN, 180))

    # 9. Circuit nodes (small dots at line ends)
    for nx, ny in [(50, 52), (185, 52), (55, 72), (190, 72), (48, 190), (200, 190)]:
        _draw_filled_circle(px, S, S, nx, ny, 4, (*CYAN, 255))

    # 10. Upward trend arrow (growth indicator)
    arrow_x = 185
    _draw_line(px, S, S, arrow_x, 185, arrow_x, 95, 3, (*GOLD, 240))
    # Arrowhead
    _draw_line(px, S, S, arrow_x - 10, 108, arrow_x, 95, 3, (*GOLD, 240))
    _draw_line(px, S, S, arrow_x + 10, 108, arrow_x, 95, 3, (*GOLD, 240))

    # 11. Top text area: "QS" letter hint (simplified as geometric blocks)
    # Letter Q (left block)
    _draw_rect(px, S, S, 85, 210, 118, 225, (*CYAN, 230))
    _draw_rect(px, S, S, 85, 210, 100, 240, (*CYAN, 230))
    _draw_rect(px, S, S, 103, 210, 118, 240, (*CYAN, 230))
    _draw_rect(px, S, S, 85, 225, 118, 240, (*CYAN, 230))
    # Letter S (right block)
    _draw_rect(px, S, S, 128, 210, 150, 218, (*CYAN, 230))
    _draw_rect(px, S, S, 128, 210, 138, 225, (*CYAN, 230))
    _draw_rect(px, S, S, 128, 218, 150, 225, (*CYAN, 230))
    _draw_rect(px, S, S, 147, 218, 150, 232, (*CYAN, 230))
    _draw_rect(px, S, S, 128, 225, 150, 232, (*CYAN, 230))
    _draw_rect(px, S, S, 128, 225, 138, 240, (*CYAN, 230))
    _draw_rect(px, S, S, 128, 232, 150, 240, (*CYAN, 230))

    return _encode_png(px, S, S)


def _build_bmp_from_pixels(px: list, w: int, h: int) -> bytes:
    """Encode RGBA pixels as a Windows BMP (32-bit, BGRA)."""
    row_size = w * 4
    row_padded = (row_size + 3) & ~3
    pixel_data_size = row_padded * h
    file_size = 14 + 40 + pixel_data_size  # header + DIB + pixels

    # BMP header
    parts = [
        b"BM",
        struct.pack("<I", file_size),
        struct.pack("<HH", 0, 0),            # reserved
        struct.pack("<I", 14 + 40),           # pixel data offset
    ]
    header = b"".join(parts)

    # DIB header (BITMAPINFOHEADER)
    dib = struct.pack(
        "<IiiHHIIiiII",
        40,                                    # DIB size
        w, h,                                  # width, height (positive = bottom-up)
        1,                                     # planes
        32,                                    # bpp
        0,                                     # BI_RGB
        0,                                     # raw image size (can be 0 for BI_RGB)
        2835, 2835,                            # print resolution
        0,                                     # palette colors
        0,                                     # important colors
    )

    # Pixel data: bottom-up, BGRA
    pixel_data = b""
    for row in reversed(px):
        row_bytes = b""
        for r, g, b, a in row:
            row_bytes += struct.pack("BBBB", b, g, r, a)
        row_bytes += b"\x00" * (row_padded - row_size)
        pixel_data += row_bytes

    return header + dib + pixel_data


def _encode_png(px: list, w: int, h: int) -> bytes:
    """Encode RGBA pixels to PNG bytes."""
    def chunk(ctype: bytes, data: bytes) -> bytes:
        c = ctype + data
        crc_val = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc_val

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))

    raw = b""
    for row in px:
        raw += b"\x00"
        for r, g, b, a in row:
            raw += struct.pack("BBBB", r, g, b, a)

    idat = chunk(b"IDAT", zlib.compress(raw, 9))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


def _png_to_ico(png_data: bytes) -> bytes:
    """Wrap a 256x256 PNG into a .ico file."""
    header = struct.pack("<HHH", 0, 1, 1)       # reserved, type=ICO, 1 image

    # Directory entry for 256x256
    entry = struct.pack(
        "<BBBBHHII",
        0,      # width (0=256 in ICO)
        0,      # height (0=256 in ICO)
        0,      # colors (0=no palette)
        0,      # reserved
        0,      # planes (0 for PNG)
        32,     # bpp
        len(png_data),  # image size
        22,     # offset (6 header + 16 entry)
    )
    return header + entry + png_data


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 256x256 icon
    print("Rendering 256x256 icon...")
    png_256 = _build_256_png()
    ico = _png_to_ico(png_256)
    OUTPUT.write_bytes(ico)
    print(f"  -> {OUTPUT}  ({len(ico):,} bytes)")

    # Wizard BMP (164x314) — simplified gradient version of icon
    print("Rendering wizard banner (164x314)...")
    px_bmp = [[(15, 15, 40, 255) for _ in range(164)] for _ in range(314)]
    # Add centered glow
    for y in range(314):
        for x in range(164):
            cx, cy = 82, 157
            dist = ((x - cx)**2 + (y - cy)**2) ** 0.5 / 200
            glow = max(0, min(1, 1 - dist))
            px_bmp[y][x] = (
                min(255, int(15 + 30 * glow)),
                min(255, int(15 + 70 * glow)),
                min(255, int(40 + 80 * glow)),
                255,
            )
    bmp_data = _build_bmp_from_pixels(px_bmp, 164, 314)
    OUTPUT_BMP.write_bytes(bmp_data)
    print(f"  -> {OUTPUT_BMP}  ({len(bmp_data):,} bytes)")

    # Wizard small BMP (55x55)
    print("Rendering wizard small (55x55)...")
    px_small = [[(15, 15, 40, 255) for _ in range(55)] for _ in range(55)]
    for y in range(55):
        for x in range(55):
            cx, cy = 27, 27
            d = ((x - cx)**2 + (y - cy)**2) ** 0.5 / 35
            g = max(0, min(1, 1 - d))
            px_small[y][x] = (
                min(255, int(15 + 40 * g)),
                min(255, int(15 + 90 * g)),
                min(255, int(40 + 100 * g)),
                255,
            )
    bmp_small_data = _build_bmp_from_pixels(px_small, 55, 55)
    OUTPUT_BMP_SMALL.write_bytes(bmp_small_data)
    print(f"  -> {OUTPUT_BMP_SMALL}  ({len(bmp_small_data):,} bytes)")

    print("\nAll icon assets generated successfully.")


if __name__ == "__main__":
    main()

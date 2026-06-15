"""
Generate professional macOS app icon for MacSystemMonitorAI.
1024x1024 PNG with squircle mask, CPU + network waveform design.
"""

import math
import os
import struct
import zlib
from PIL import Image, ImageDraw, ImageFilter

OUTPUT_DIR = os.path.dirname(os.path.abspath(__file__))
PNG_PATH = os.path.join(OUTPUT_DIR, "app_icon_1024.png")
SIZE = 1024


# ── Color palette ──────────────────────────────────────────────
C_BG_DARK    = (10, 22, 55)
C_BG_MID     = (18, 48, 110)
C_BG_LIGHT   = (28, 70, 150)
C_CHIP_DARK  = (20, 38, 90)
C_CHIP_BODY  = (32, 68, 165)
C_CHIP_TOP   = (55, 110, 210)
C_GRID       = (80, 150, 240)
C_PIN        = (170, 210, 245)
C_TRACE      = (90, 160, 240)
C_CYAN       = (0, 210, 255)
C_CYAN_LIGHT = (120, 235, 255)
C_WHITE_SOFT = (220, 238, 255)
C_GLOW       = (40, 130, 230)
C_HIGHLIGHT  = (130, 190, 245)
C_SHADOW     = (0, 0, 0)


def make_squircle_mask():
    """Create squircle mask as an alpha image.
    Superellipse: |x/a|^5 + |y/b|^5 <= 1
    """
    print("  Computing squircle mask...")
    mask = Image.new("L", (SIZE, SIZE), 0)
    n = 5.0
    a = SIZE / 2.0

    # Process in blocks for better cache locality
    for y in range(SIZE):
        ny = abs((y - a) / a)
        ny_n = ny ** n
        for x in range(SIZE):
            nx = abs((x - a) / a)
            if nx ** n + ny_n <= 1.0:
                mask.putpixel((x, y), 255)

    # Smooth edge slightly
    mask = mask.filter(ImageFilter.GaussianBlur(1.2))
    return mask


def draw_all(mask):
    """Draw everything on a single image and apply mask at the end."""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = SIZE / 2
    cy = SIZE / 2

    # ═══════════════════════════════════════════════════════════
    # 1. BACKGROUND GRADIENT (radial: brighter center)
    # ═══════════════════════════════════════════════════════════
    print("  [1] Background gradient...")
    for y in range(SIZE):
        for x in range(SIZE):
            dx = (x - cx) / cx
            dy = (y - cy) / cy
            dist = math.sqrt(dx * dx + dy * dy)
            vf = y / SIZE  # slight top-to-bottom darkening

            r = int(10 + 22 * (1 - dist) - 6 * vf)
            g = int(22 + 55 * (1 - dist) - 10 * vf)
            b = int(55 + 105 * (1 - dist) - 15 * vf)
            r = max(0, min(255, r))
            g = max(0, min(255, g))
            b = max(0, min(255, b))
            img.putpixel((x, y), (r, g, b, 255))

    # ═══════════════════════════════════════════════════════════
    # 2. SUBTLE BACKGROUND TECH GRID
    # ═══════════════════════════════════════════════════════════
    print("  [2] Background tech grid...")
    # Concentric circles
    for i, r in enumerate([SIZE * 0.24, SIZE * 0.32, SIZE * 0.40]):
        alpha = 30 - i * 8
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(50, 110, 190, alpha),
            width=max(1, SIZE // 400),
        )

    # Subtle diagonal lines
    spacing = int(SIZE * 0.11)
    for i in range(-10, 25):
        offset = i * spacing
        d.line(
            [offset, -10, offset + SIZE + 10, SIZE + 10],
            fill=(25, 55, 120, 25),
            width=1,
        )

    # Corner tech dots
    margin = int(SIZE * 0.10)
    dot_r = max(3, SIZE // 150)
    corners = [
        (margin, margin), (SIZE - margin, margin),
        (margin, SIZE - margin), (SIZE - margin, SIZE - margin),
    ]
    for cpx, cpy in corners:
        for j in range(5):
            alpha = 120 - j * 22
            d.ellipse(
                [cpx - dot_r + j * 8, cpy - dot_r,
                 cpx + dot_r + j * 8, cpy + dot_r],
                fill=(100, 170, 235, alpha),
            )
            d.ellipse(
                [cpx - dot_r, cpy - dot_r + j * 8,
                 cpx + dot_r, cpy + dot_r + j * 8],
                fill=(100, 170, 235, alpha),
            )

    # ═══════════════════════════════════════════════════════════
    # 3. CENTRAL GLOW (behind the CPU)
    # ═══════════════════════════════════════════════════════════
    print("  [3] Central glow...")
    for i in range(25):
        t = i / 25
        r = SIZE * 0.40 * (0.2 + 0.8 * t)
        alpha = int(35 * (1 - t))
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            fill=(40, 120, 220, alpha),
        )

    # ═══════════════════════════════════════════════════════════
    # 4. CPU CHIP
    # ═══════════════════════════════════════════════════════════
    print("  [4] CPU chip...")
    chip_w = SIZE * 0.34
    chip_h = SIZE * 0.36
    hw = chip_w / 2
    hh = chip_h / 2
    corner_r = int(chip_w * 0.09)

    # Shadow under chip
    d.rounded_rectangle(
        [cx - hw - 6, cy - hh - 2, cx + hw + 6, cy + hh + 12],
        radius=corner_r + 2,
        fill=(0, 0, 0, 100),
    )

    # Base body
    d.rounded_rectangle(
        [cx - hw, cy - hh, cx + hw, cy + hh],
        radius=corner_r,
        fill=C_CHIP_DARK,
    )

    # Beveled top face
    bevel = int(chip_w * 0.04)
    d.rounded_rectangle(
        [cx - hw + bevel, cy - hh + bevel, cx + hw - bevel, cy + hh - bevel],
        radius=max(1, corner_r - bevel),
        fill=C_CHIP_BODY,
    )

    # Inner die (dark core)
    inner_margin = int(chip_w * 0.13)
    die_rect = [
        cx - hw + inner_margin,
        cy - hh + inner_margin,
        cx + hw - inner_margin,
        cy + hh - inner_margin,
    ]
    die_r = int(chip_w * 0.05)
    d.rounded_rectangle(die_rect, radius=die_r, fill=(12, 26, 65))

    # Grid contact pads
    grid_n = 4
    cell_w = (chip_w - 2 * inner_margin) / grid_n
    cell_h = (chip_h - 2 * inner_margin) / grid_n
    gx0 = cx - hw + inner_margin
    gy0 = cy - hh + inner_margin
    pad_r = min(cell_w, cell_h) * 0.24

    for row in range(grid_n):
        for col in range(grid_n):
            px = gx0 + (col + 0.5) * cell_w
            py = gy0 + (row + 0.5) * cell_h
            pr = pad_r
            d.rounded_rectangle(
                [px - pr, py - pr, px + pr, py + pr],
                radius=max(2, int(pr * 0.4)),
                fill=C_GRID,
            )

    # Circuit trace lines
    for i in range(3):
        ty = cy - hh * 0.38 + i * (hh * 0.38)
        tx1 = cx - hw + inner_margin + 8
        tx2 = cx + hw - inner_margin - 8
        d.line([tx1, ty, tx2, ty], fill=C_TRACE, width=max(3, int(chip_w * 0.013)))

    # Vertical center line
    d.line(
        [cx, cy - hh * 0.48, cx, cy + hh * 0.48],
        fill=(70, 130, 220),
        width=max(2, int(chip_w * 0.008)),
    )

    # Top glossy highlight
    d.rounded_rectangle(
        [cx - hw * 0.55, cy - hh * 0.72, cx + hw * 0.55, cy - hh * 0.32],
        radius=int(chip_w * 0.04),
        fill=(100, 160, 230, 70),
    )

    # Edge pins (left/right)
    pin_count = 8
    pin_len = int(chip_w * 0.09)
    pin_w = max(2, int(chip_w * 0.015))
    for side in [-1, 1]:
        for i in range(pin_count):
            py = cy - hh * 0.76 + i * (1.52 * hh / (pin_count - 1))
            d.line(
                [cx + side * (hw + 1), py, cx + side * (hw + pin_len), py],
                fill=C_PIN,
                width=pin_w,
            )

    # Edge pins (top/bottom)
    for side in [-1, 1]:
        for i in range(pin_count):
            px = cx - hw * 0.76 + i * (1.52 * hw / (pin_count - 1))
            d.line(
                [px, cy + side * (hh + 1), px, cy + side * (hh + pin_len)],
                fill=C_PIN,
                width=pin_w,
            )

    # ═══════════════════════════════════════════════════════════
    # 5. NETWORK WAVEFORM ELEMENTS
    # ═══════════════════════════════════════════════════════════
    print("  [5] Network waveforms...")

    # ── Wi-Fi arcs above chip ──
    arc_base_y = cy - hh - SIZE * 0.03
    for i, arc_r in enumerate([SIZE * 0.14, SIZE * 0.20, SIZE * 0.26]):
        arc_rect = [
            cx - arc_r, arc_base_y - arc_r * 0.58,
            cx + arc_r, arc_base_y + arc_r * 0.58,
        ]
        c = (C_CYAN[0], C_CYAN[1] - i * 10, C_CYAN[2])
        d.arc(arc_rect, start=210, end=330, fill=c, width=max(5, int(SIZE * 0.019)))

    # ── Signal bars (left) ──
    bar_bottom = cy + hh + SIZE * 0.09
    bar_base_x = cx - hw * 0.6
    bar_w = int(SIZE * 0.026)
    bar_heights = [SIZE * 0.035, SIZE * 0.065, SIZE * 0.10, SIZE * 0.065, SIZE * 0.035]
    bar_spacing = SIZE * 0.075

    for i, bh in enumerate(bar_heights):
        bx = bar_base_x + i * bar_spacing
        t_center = abs(i - 2) / 2.0
        r = int(10 + 30 * (1 - t_center))
        g = int(140 + 90 * (1 - t_center))
        b = int(230 + 25 * (1 - t_center))
        d.rounded_rectangle(
            [bx, bar_bottom - bh, bx + bar_w, bar_bottom],
            radius=max(3, int(bar_w * 0.5)),
            fill=(r, g, b),
        )

    # ── Sine wave (right side) ──
    wave_cx = cx + hw * 0.35
    wave_cy = bar_bottom - SIZE * 0.02
    wave_amp = SIZE * 0.05
    wave_len = hw * 1.5
    freq = 3

    # Glow layer
    pts_glow = []
    for i in range(81):
        t = i / 80
        px = wave_cx - wave_len / 2 + t * wave_len
        env = math.sin(t * math.pi)
        py = wave_cy - env * wave_amp * math.sin(t * freq * 2 * math.pi)
        pts_glow.append((px, py))
    for i in range(len(pts_glow) - 1):
        d.line(pts_glow[i : i + 2], fill=(0, 170, 255, 90), width=max(8, int(SIZE * 0.028)))

    # Core wave
    for i in range(len(pts_glow) - 1):
        d.line(pts_glow[i : i + 2], fill=C_CYAN, width=max(3, int(SIZE * 0.01)))

    # Data dots on wave
    for frac in [0.14, 0.34, 0.5, 0.66, 0.86]:
        t = frac
        px = wave_cx - wave_len / 2 + t * wave_len
        env = math.sin(t * math.pi)
        py = wave_cy - env * wave_amp * math.sin(t * freq * 2 * math.pi)
        # Glow ring
        dr = SIZE * 0.022
        d.ellipse([px - dr, py - dr, px + dr, py + dr], fill=(0, 190, 255, 70))
        # Core
        dr2 = SIZE * 0.013
        d.ellipse([px - dr2, py - dr2, px + dr2, py + dr2], fill=C_CYAN_LIGHT)

    # ═══════════════════════════════════════════════════════════
    # 6. EDGE VIGNETTE (inner shadow on squircle)
    # ═══════════════════════════════════════════════════════════
    print("  [6] Edge vignette...")
    for i in range(20):
        alpha = int(10 * (1 - i / 20))
        inset = i * (SIZE / 180)
        r = SIZE / 2 - inset
        d.ellipse(
            [cx - r, cy - r, cx + r, cy + r],
            outline=(0, 0, 0, alpha),
            width=max(1, SIZE // 120),
        )

    # ═══════════════════════════════════════════════════════════
    # 7. APPLY SQUIRCLE MASK
    # ═══════════════════════════════════════════════════════════
    print("  [7] Applying squircle mask...")
    img.putalpha(mask)

    return img


def main():
    print(f"MacSystemMonitorAI Icon Generator")
    print(f"  Size: {SIZE}×{SIZE}px")
    print(f"  Style: Blue-tech CPU + Network Waveform")
    print("=" * 56)

    mask = make_squircle_mask()
    img = draw_all(mask)

    print(f"\n  Saving → {PNG_PATH}")
    img.save(PNG_PATH, "PNG", optimize=True)
    file_size = os.path.getsize(PNG_PATH)
    print(f"  Done! {SIZE}×{SIZE}px | {file_size / 1024:.0f} KB")
    print("=" * 56)


if __name__ == "__main__":
    main()

"""
texture generator.
Run with: py -3.11 generate_textures.py
Outputs 5 textures to static/textures/
"""
import os, math, random
import numpy as np
from PIL import Image, ImageFilter, ImageDraw

OUT = os.path.join(os.path.dirname(__file__), "static", "textures")
os.makedirs(OUT, exist_ok=True)
rng = random.Random(42)
np.random.seed(42)

def save(img, name, quality=85):
    path = os.path.join(OUT, name)
    img.convert("RGB").save(path, "JPEG", quality=quality)
    kb = os.path.getsize(path) // 1024
    w, h = img.size
    print(f"  {name}: {w}x{h}px  {kb} KB  -> {path}")
    return path


# stone_bg.jpg  1920×1080  Dark dungeon stone wall
def make_stone_bg():
    W, H = 1920, 1080
    arr = np.zeros((H, W, 3), dtype=np.uint8)

    # Base warm dark fill
    arr[:, :] = [18, 14, 10]

    # Stone block grid
    bx, by = 120, 80          # nominal block size
    x = 0
    while x < W:
        bw = bx + rng.randint(-15, 15)
        y = 0
        while y < H:
            bh = by + rng.randint(-15, 15)
            # random block tone
            r = rng.randint(20, 35)
            g = rng.randint(15, 28)
            b = rng.randint(10, 20)
            x1, y1 = min(x + 1, W - 1), min(y + 1, H - 1)
            x2, y2 = min(x + bw - 1, W), min(y + bh - 1, H)
            if x2 > x1 and y2 > y1:
                arr[y1:y2, x1:x2] = [r, g, b]
            # block border lines
            bw2 = rng.randint(2, 3)
            arr[y:min(y + bw2, H), x:min(x + bw, W)] = [8, 6, 4]
            arr[y:min(y + bh, H), x:min(x + bw2, W)] = [8, 6, 4]
            y += bh
        x += bw

    # Thin crack lines across random blocks
    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img)
    for _ in range(60):
        cx = rng.randint(0, W)
        cy = rng.randint(0, H)
        length = rng.randint(40, 180)
        angle = rng.uniform(-0.3, 0.3)
        ex = int(cx + length * math.cos(angle))
        ey = int(cy + length * math.sin(angle) + rng.randint(-20, 20))
        draw.line([(cx, cy), (ex, ey)], fill=(10, 8, 6), width=1)
    arr = np.array(img)

    # Vignette — darken edges
    for y in range(H):
        for pass_ in range(1):  # vectorised below
            pass
    ys = np.linspace(-1, 1, H)
    xs = np.linspace(-1, 1, W)
    xg, yg = np.meshgrid(xs, ys)
    dist = np.sqrt(xg ** 2 + yg ** 2)
    vignette = np.clip(1.0 - dist * 0.55, 0.55, 1.0)
    for c in range(3):
        arr[:, :, c] = np.clip(arr[:, :, c] * vignette, 0, 255).astype(np.uint8)

    # Moss patches in corners
    for corner in [(0, 0), (W - 200, 0), (0, H - 200), (W - 200, H - 200)]:
        cx, cy = corner
        for _ in range(300):
            px = cx + rng.randint(0, 200)
            py = cy + rng.randint(0, 200)
            if 0 <= px < W and 0 <= py < H:
                fade = 1.0 - math.sqrt((px - cx - 100) ** 2 + (py - cy - 100) ** 2) / 141
                if fade > 0 and rng.random() < fade * 0.6:
                    arr[py, px] = [12, 20, 12]

    img = Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(radius=0.8))
    save(img, "stone_bg.jpg", quality=85)


# parchment_panel.jpg  800×600  Aged parchment
def make_parchment():
    W, H = 800, 600
    arr = np.full((H, W, 3), [244, 228, 193], dtype=np.uint8)

    # Fine grain noise
    noise = np.random.randint(-12, 13, (H, W, 3))
    arr = np.clip(arr.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Aging blobs
    img = Image.fromarray(arr, "RGB")
    for _ in range(18):
        bx = rng.randint(0, W)
        by = rng.randint(0, H)
        br = rng.randint(30, 120)
        patch = Image.new("RGBA", (br * 2, br * 2), (0, 0, 0, 0))
        pd = ImageDraw.Draw(patch)
        alpha = rng.randint(40, 110)
        pd.ellipse([0, 0, br * 2, br * 2], fill=(200, 175, 130, alpha))
        patch = patch.filter(ImageFilter.GaussianBlur(radius=br // 3))
        img.paste(Image.new("RGB", (br * 2, br * 2), (200, 175, 130)),
                  (bx - br, by - br),
                  mask=patch.split()[3])
    arr = np.array(img)

    # Water stains soft ellipses
    for _ in range(4):
        sx = rng.randint(80, W - 80)
        sy = rng.randint(80, H - 80)
        sw = rng.randint(60, 160)
        sh = rng.randint(30, 80)
        for dy in range(-sh, sh):
            for dx in range(-sw, sw):
                if (dx / sw) ** 2 + (dy / sh) ** 2 <= 1:
                    px, py = sx + dx, sy + dy
                    if 0 <= px < W and 0 <= py < H:
                        fade = 1.0 - math.sqrt((dx / sw) ** 2 + (dy / sh) ** 2)
                        arr[py, px] = np.clip(
                            arr[py, px].astype(np.int16) + int(fade * (-24)),
                            0, 255).astype(np.uint8)

    # Edge darkening
    edge = 80
    for y in range(H):
        for x in range(W):
            ey = min(y, H - 1 - y)
            ex = min(x, W - 1 - x)
            ef = max(0.0, 1.0 - min(ey, ex) / edge)
            if ef > 0:
                target = np.array([180, 145, 100])
                arr[y, x] = np.clip(
                    arr[y, x] * (1 - ef) + target * ef, 0, 255).astype(np.uint8)

    # Laid paper horizontal lines every 4px
    for y in range(0, H, 4):
        arr[y] = np.clip(arr[y].astype(np.int16) - 6, 0, 255).astype(np.uint8)

    # Warm yellow tint 15%
    tint = np.array([255, 220, 150])
    arr = np.clip(arr * 0.85 + tint * 0.15, 0, 255).astype(np.uint8)

    img = Image.fromarray(arr, "RGB")
    save(img, "parchment_panel.jpg", quality=90)


# dark_wood.jpg  400×60  Tileable dark wood grain
def make_dark_wood():
    W, H = 400, 60
    arr = np.full((H, W, 3), [30, 20, 12], dtype=np.uint8)

    # Wood grain lines
    y = 0.0
    while y < H:
        gy = int(y)
        r = rng.randint(35, 55)
        g = rng.randint(22, 38)
        b = rng.randint(12, 22)
        for x in range(W):
            wave = int(math.sin(x * 0.04 + rng.uniform(-0.3, 0.3)) * 1.5)
            py = gy + wave
            if 0 <= py < H:
                arr[py, x] = [r, g, b]
        y += rng.uniform(2, 4)

    # Knot ovals
    for _ in range(2):
        kx = rng.randint(60, W - 60)
        ky = rng.randint(10, H - 10)
        for ring in range(5):
            ra, rb = 12 - ring * 2, 6 - ring
            if ra <= 0 or rb <= 0:
                break
            for angle in range(360):
                px = int(kx + ra * math.cos(math.radians(angle)))
                py = int(ky + rb * math.sin(math.radians(angle)))
                if 0 <= px < W and 0 <= py < H:
                    arr[py, px] = [15, 10, 6]

    # Top highlight
    arr[0, :] = [60, 45, 30]

    img = Image.fromarray(arr, "RGB")
    save(img, "dark_wood.jpg", quality=85)


# leather_panel.jpg  400×800  Dark leather
def make_leather():
    W, H = 400, 800
    arr = np.full((H, W, 3), [25, 18, 12], dtype=np.uint8)

    # Pore texture — tiny dots
    coords = np.random.randint(0, H, 8000), np.random.randint(0, W, 8000)
    arr[coords[0], coords[1]] = [18, 12, 8]

    # Grain  diagonal streaks at 15°
    tan15 = math.tan(math.radians(15))
    for start_x in range(-H, W, 6):
        for dy in range(H):
            dx = int(dy * tan15) + start_x
            if 0 <= dx < W:
                r = rng.randint(22, 30)
                g = rng.randint(15, 22)
                b = rng.randint(10, 16)
                arr[dy, dx] = [r, g, b]

    # Worn areas lighter patches
    img = Image.fromarray(arr, "RGB")
    for _ in range(4):
        wx = rng.randint(40, W - 40)
        wy = rng.randint(80, H - 80)
        wr = rng.randint(40, 100)
        patch = Image.new("RGBA", (wr * 2, wr * 2), (0, 0, 0, 0))
        pd = ImageDraw.Draw(patch)
        pd.ellipse([0, 0, wr * 2, wr * 2], fill=(40, 28, 18, 80))
        patch = patch.filter(ImageFilter.GaussianBlur(radius=wr // 2))
        img.paste(Image.new("RGB", (wr * 2, wr * 2), (40, 28, 18)),
                  (wx - wr, wy - wr), mask=patch.split()[3])
    arr = np.array(img)

    # Diagonal sheen highlight
    for y in range(H):
        x = int(y * 0.4) % W
        for dx in range(-3, 4):
            px = x + dx
            if 0 <= px < W:
                fade = 1.0 - abs(dx) / 4.0
                arr[y, px] = np.clip(
                    arr[y, px].astype(np.int16) + int(fade * 18), 0, 255).astype(np.uint8)

    img = Image.fromarray(arr, "RGB").filter(ImageFilter.GaussianBlur(radius=0.5))
    save(img, "leather_panel.jpg", quality=85)


# 5. map_bg.jpg  450×450  Stone floor from above
def make_map_bg():
    W, H = 450, 450
    arr = np.full((H, W, 3), [15, 12, 8], dtype=np.uint8)

    # Build flagstone grid
    nominal = 60
    stones = []
    y = 0
    while y < H:
        x = 0
        while x < W:
            sw = nominal + rng.randint(-8, 8)
            sh = nominal + rng.randint(-8, 8)
            # Jitter corners
            corners = []
            for cx, cy in [(x, y), (x + sw, y), (x + sw, y + sh), (x, y + sh)]:
                jx = cx + rng.randint(-8, 8)
                jy = cy + rng.randint(-8, 8)
                corners.append((jx, jy))
            stones.append(corners)
            x += sw
        y += sh

    img = Image.fromarray(arr, "RGB")
    draw = ImageDraw.Draw(img)

    # Fill each stone
    for i, corners in enumerate(stones):
        r = rng.randint(22, 32)
        g = rng.randint(18, 26)
        b = rng.randint(12, 18)
        flat = [c for pt in corners for c in pt]
        try:
            draw.polygon(flat, fill=(r, g, b))
        except Exception:
            pass

    # Draw gaps (border lines between stones)
    for corners in stones:
        pts = corners + [corners[0]]
        for j in range(len(pts) - 1):
            draw.line([pts[j], pts[j + 1]], fill=(8, 6, 4), width=rng.randint(1, 2))

    arr = np.array(img)

    # Dirt smudges in stone corners
    for corners in stones:
        for cx, cy in corners:
            if rng.random() < 0.35:
                for dy in range(-4, 5):
                    for dx in range(-4, 5):
                        px, py = cx + dx, cy + dy
                        if 0 <= px < W and 0 <= py < H:
                            fade = 1.0 - math.sqrt(dx ** 2 + dy ** 2) / 5.0
                            if fade > 0:
                                arr[py, px] = np.clip(
                                    arr[py, px].astype(np.int16) - int(fade * 5),
                                    0, 255).astype(np.uint8)

    # Hairline cracks on 1 in 8 stones
    img = Image.fromarray(arr, "RGB")
    draw2 = ImageDraw.Draw(img)
    for corners in stones:
        if rng.random() < 0.125:
            xs = [c[0] for c in corners]
            ys = [c[1] for c in corners]
            cx = sum(xs) // 4
            cy = sum(ys) // 4
            length = rng.randint(20, 50)
            angle = rng.uniform(0, math.pi)
            ex = int(cx + length * math.cos(angle))
            ey = int(cy + length * math.sin(angle))
            draw2.line([(cx, cy), (ex, ey)], fill=(10, 8, 5), width=1)

    save(img, "map_bg.jpg", quality=85)


print("Generating textures...")
make_stone_bg()
make_parchment()
make_dark_wood()
make_leather()
make_map_bg()
print("Done.")

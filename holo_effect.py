"""
holo_effect.py
--------------
ساخت GIF هولوگرافی از تصویر کارت Pokemon
سه لایه: Rainbow Shimmer + Rotating Holo Band + Silver Stars
دانلود تصویر با aiohttp (سازگار با Railway)
"""

import asyncio
import io
import math

import aiohttp
import numpy as np
from PIL import Image


# ── دانلود async با aiohttp ─────────────────────────────────────────────────

async def download_image_async(url: str) -> Image.Image | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0 Safari/537.36"
        ),
        "Accept": "image/png,image/webp,image/*,*/*",
        "Referer": "https://www.tcgdex.net/",
    }
    try:
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    return None
                data = await resp.read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


# ── ساخت GIF ────────────────────────────────────────────────────────────────

def _build_gif(card_img: Image.Image, frames: int = 24, fps: int = 16, max_width: int = 380) -> bytes:
    w, h = card_img.size
    if w > max_width:
        ratio = max_width / w
        card_img = card_img.resize((max_width, int(h * ratio)), Image.LANCZOS)
    w, h = card_img.size

    card_arr = np.array(card_img.convert("RGBA"), dtype=np.float32)

    rng = np.random.default_rng(42)
    n_stars = 140
    sx = rng.integers(0, w, n_stars)
    sy = rng.integers(0, h, n_stars)
    ss = rng.uniform(0.6, 2.8, n_stars)

    xs = np.linspace(0, 1, w, dtype=np.float32)
    ys = np.linspace(0, 1, h, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)

    result_frames: list[Image.Image] = []
    pi2 = 2 * math.pi

    for f in range(frames):
        t = f / frames

        # ── 1. Rainbow Shimmer ────────────────────────────────────────────
        phase = (xg * 0.6 + yg * 0.4 + t) % 1.0
        r_ch = np.sin(phase * pi2 + 0.0)   * 0.5 + 0.5
        g_ch = np.sin(phase * pi2 + 2.094) * 0.5 + 0.5
        b_ch = np.sin(phase * pi2 + 4.189) * 0.5 + 0.5
        rainbow = np.stack([r_ch, g_ch, b_ch], axis=2) * 255.0

        # ── 2. Rotating Holo Band ─────────────────────────────────────────
        tilt_x = math.cos(t * pi2)
        band = np.clip((xg - 0.5) * 3.0 * tilt_x + 0.5, 0, 1)
        band = np.exp(-((band - 0.5) ** 2) / 0.035).astype(np.float32)
        tilt_hl = np.stack([band] * 3, axis=2) * 255.0

        # ── 3. Silver Sparkle Stars ───────────────────────────────────────
        star_layer = np.zeros((h, w, 3), dtype=np.float32)
        for i in range(n_stars):
            star_phase = (t + i / n_stars) % 1.0
            brightness = max(0.0, math.sin(star_phase * pi2 * 2)) ** 3
            if brightness < 0.01:
                continue
            bx, by = int(sx[i]), int(sy[i])
            radius = max(1, int(ss[i]))
            for dy in range(-radius, radius + 1):
                for dx in range(-radius, radius + 1):
                    nx_, ny_ = bx + dx, by + dy
                    if 0 <= nx_ < w and 0 <= ny_ < h:
                        falloff = math.exp(-(dx*dx + dy*dy) / (0.6 + ss[i]))
                        v = brightness * falloff * 255.0
                        star_layer[ny_, nx_, 0] += v
                        star_layer[ny_, nx_, 1] += v
                        star_layer[ny_, nx_, 2] += v * 0.85
        np.clip(star_layer, 0, 255, out=star_layer)

        # ── Composite ─────────────────────────────────────────────────────
        base_rgb  = card_arr[:, :, :3]
        alpha_mask = card_arr[:, :, 3:4] / 255.0

        comp = 1.0 - (1.0 - base_rgb / 255.0) * (1.0 - rainbow / 255.0 * 0.42)
        comp = np.clip(comp * 255.0 + tilt_hl * 0.32 + star_layer * 0.88, 0, 255)
        comp = comp * alpha_mask + 255.0 * (1.0 - alpha_mask)

        result_frames.append(Image.fromarray(comp.astype(np.uint8), "RGB"))

    buf = io.BytesIO()
    result_frames[0].save(
        buf, format="GIF", save_all=True,
        append_images=result_frames[1:],
        duration=int(1000 / fps), loop=0, optimize=False,
    )
    return buf.getvalue()


# ── تابع اصلی (async) ───────────────────────────────────────────────────────

async def create_holo_gif(image_url: str) -> bytes | None:
    """URL تصویر کارت → بایت‌های GIF هولوگرافی (یا None در صورت خطا)"""
    img = await download_image_async(image_url)
    if img is None:
        return None
    loop = asyncio.get_event_loop()
    # محاسبات سنگین numpy را در thread pool اجرا می‌کنیم
    return await loop.run_in_executor(None, _build_gif, img)

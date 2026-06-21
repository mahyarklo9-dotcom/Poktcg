"""
holo_effect.py
--------------
تبدیل تصویر کارت Pokemon به GIF انیمیشن هولوگرافی با سه لایه:
  1. Rainbow Shimmer  – گرادیان رنگین‌کمانی چرخشی
  2. Rotating Holo    – نوار درخشان چرخنده
  3. Silver Stars     – ستاره‌های نقره‌ای چشمک‌زن
"""

import io
import math
import urllib.request

import numpy as np
from PIL import Image


# ── دانلود تصویر کارت ───────────────────────────────────────────────────────

def download_image(url: str) -> Image.Image | None:
    """تصویر را از URL دانلود کرده و به صورت RGBA برمی‌گرداند."""
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "PokemonTCGBot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        return Image.open(io.BytesIO(data)).convert("RGBA")
    except Exception:
        return None


# ── ساخت GIF هولوگرافی ──────────────────────────────────────────────────────

def make_holo_gif(
    card_img: Image.Image,
    frames: int = 24,
    fps: int = 16,
    max_width: int = 400,
) -> bytes | None:
    """
    کارت RGBA را می‌گیرد و بایت‌های GIF انیمیشن هولوگرافی را برمی‌گرداند.

    پارامترها:
        card_img  : تصویر کارت (PIL RGBA)
        frames    : تعداد فریم (بیشتر = نرم‌تر، سنگین‌تر)
        fps       : سرعت پخش
        max_width : عرض حداکثر برای کوچک‌سازی (برای حجم GIF)
    """
    # کوچک‌سازی اختیاری برای کاهش حجم
    w, h = card_img.size
    if w > max_width:
        ratio = max_width / w
        card_img = card_img.resize(
            (max_width, int(h * ratio)), Image.LANCZOS
        )
    w, h = card_img.size

    card_arr = np.array(card_img.convert("RGBA"), dtype=np.float32)

    # موقعیت ستاره‌های ثابت
    rng = np.random.default_rng(42)
    n_stars = 140
    sx = rng.integers(0, w, n_stars)
    sy = rng.integers(0, h, n_stars)
    ss = rng.uniform(0.6, 2.8, n_stars)

    result_frames: list[Image.Image] = []

    xs = np.linspace(0, 1, w, dtype=np.float32)
    ys = np.linspace(0, 1, h, dtype=np.float32)
    xg, yg = np.meshgrid(xs, ys)

    for f in range(frames):
        t = f / frames  # 0.0 → 1.0

        # ── 1. Rainbow Shimmer ────────────────────────────────────────────
        phase = (xg * 0.6 + yg * 0.4 + t) % 1.0
        pi2 = 2 * math.pi
        r_ch = np.sin(phase * pi2 + 0.0) * 0.5 + 0.5
        g_ch = np.sin(phase * pi2 + 2.094) * 0.5 + 0.5
        b_ch = np.sin(phase * pi2 + 4.189) * 0.5 + 0.5
        rainbow = np.stack([r_ch, g_ch, b_ch], axis=2) * 255.0

        # ── 2. Rotating Holo band ─────────────────────────────────────────
        angle = t * pi2
        tilt_x = math.cos(angle)
        band = np.clip((xg - 0.5) * 3.0 * tilt_x + 0.5, 0, 1)
        band = np.exp(-((band - 0.5) ** 2) / 0.035).astype(np.float32)
        tilt_highlight = np.stack([band] * 3, axis=2) * 255.0

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
                        d2 = dx * dx + dy * dy
                        falloff = math.exp(-d2 / (0.6 + ss[i]))
                        v = brightness * falloff * 255.0
                        star_layer[ny_, nx_, 0] += v
                        star_layer[ny_, nx_, 1] += v
                        star_layer[ny_, nx_, 2] += v * 0.85  # کمی آبی
        np.clip(star_layer, 0, 255, out=star_layer)

        # ── ترکیب لایه‌ها روی کارت ────────────────────────────────────────
        base_rgb = card_arr[:, :, :3]
        alpha_mask = card_arr[:, :, 3:4] / 255.0

        # Screen blend برای رنگین‌کمان
        comp = 1.0 - (1.0 - base_rgb / 255.0) * (1.0 - rainbow / 255.0 * 0.42)
        comp *= 255.0

        # نوار هولو (additive)
        comp = np.clip(comp + tilt_highlight * 0.32, 0, 255)

        # ستاره‌ها (additive)
        comp = np.clip(comp + star_layer * 0.88, 0, 255)

        # اعمال alpha – خارج از کارت سفید می‌شه (GIF شفافیت کامل ندارد)
        comp = comp * alpha_mask + 255.0 * (1.0 - alpha_mask)
        frame_arr = np.clip(comp, 0, 255).astype(np.uint8)

        result_frames.append(Image.fromarray(frame_arr, "RGB"))

    # ذخیره در حافظه
    buf = io.BytesIO()
    result_frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=result_frames[1:],
        duration=int(1000 / fps),
        loop=0,
        optimize=False,
    )
    return buf.getvalue()


# ── تابع اصلی برای استفاده در بات ──────────────────────────────────────────

def create_holo_gif(image_url: str) -> bytes | None:
    """
    URL تصویر کارت را می‌گیرد و بایت‌های GIF هولوگرافی را برمی‌گرداند.
    در صورت خطا None برمی‌گرداند.
    """
    img = download_image(image_url)
    if img is None:
        return None
    return make_holo_gif(img)

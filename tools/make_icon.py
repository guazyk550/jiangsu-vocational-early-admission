"""生成应用图标 ``assets/icon.ico``（多尺寸）与预览图。

用 Pillow 绘制一个简洁的院校导航标识：圆角蓝底 + 白色定位针 + 书页轮廓。
纯代码生成，避免引入二进制素材，也便于随时调整配色。

用法::

    py tools/make_icon.py
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = PROJECT_ROOT / "assets"
ICO_PATH = OUT_DIR / "icon.ico"
PNG_PATH = OUT_DIR / "icon.png"

#: 与界面主题色保持一致
PRIMARY = (37, 99, 235, 255)
PRIMARY_DARK = (29, 78, 216, 255)
WHITE = (255, 255, 255, 255)

#: ico 需要包含的尺寸
ICO_SIZES = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)]


def draw_icon(size: int) -> Image.Image:
    """绘制指定尺寸的图标。"""
    scale = size / 256
    image = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)

    margin = int(12 * scale)
    radius = int(52 * scale)
    draw.rounded_rectangle(
        [margin, margin, size - margin, size - margin],
        radius=radius,
        fill=PRIMARY,
    )
    # 顶部高光，让图标有一点层次
    draw.rounded_rectangle(
        [margin, margin, size - margin, int(size * 0.52)],
        radius=radius,
        fill=PRIMARY_DARK,
    )

    # 定位针（水滴形：圆 + 三角）
    cx = size / 2
    circle_r = size * 0.19
    circle_cy = size * 0.40
    draw.ellipse(
        [cx - circle_r, circle_cy - circle_r, cx + circle_r, circle_cy + circle_r],
        fill=WHITE,
    )
    draw.polygon(
        [
            (cx - circle_r * 0.78, circle_cy + circle_r * 0.62),
            (cx + circle_r * 0.78, circle_cy + circle_r * 0.62),
            (cx, circle_cy + circle_r * 2.6),
        ],
        fill=WHITE,
    )
    # 针心
    hole_r = circle_r * 0.42
    draw.ellipse(
        [cx - hole_r, circle_cy - hole_r, cx + hole_r, circle_cy + hole_r],
        fill=PRIMARY,
    )

    # 底部书本轮廓
    book_top = size * 0.72
    book_bottom = size * 0.845
    draw.rounded_rectangle(
        [size * 0.26, book_top, size * 0.74, book_bottom],
        radius=int(8 * scale),
        fill=WHITE,
    )
    draw.line(
        [(cx, book_top + size * 0.012), (cx, book_bottom - size * 0.012)],
        fill=PRIMARY_DARK,
        width=max(1, int(6 * scale)),
    )
    return image


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    images = [draw_icon(width) for width, _ in ICO_SIZES]
    images[0].save(
        ICO_PATH,
        format="ICO",
        sizes=[(w, h) for w, h in ICO_SIZES],
        append_images=images[1:],
    )
    images[0].save(PNG_PATH, format="PNG")
    print(f"[完成] 写入 {ICO_PATH}")
    print(f"[完成] 写入 {PNG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

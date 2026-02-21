"""
make_icon.py — generates static/logo.ico for the Windows EXE.
Run once: venv\Scripts\python.exe make_icon.py
"""
import os
from PIL import Image, ImageDraw, ImageFont

SIZE = 256

def draw_logo(size):
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded rectangle background (dark navy)
    radius = max(1, size // 5)
    draw.rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=(7, 9, 26, 255))

    # Corner stripe: top-right triangle (orange)
    cut = size * 14 // 40
    draw.polygon([(size - cut, 0), (size, 0), (size, cut)], fill=(232, 74, 10, 255))

    # Corner stripe: bottom-left triangle (gold)
    draw.polygon([(0, size - cut), (cut, size), (0, size)], fill=(247, 184, 1, 255))

    # "AC" text — try bold system font, fall back to default
    font_size = size * 17 // 40
    font = None
    for fname in ('arialbd.ttf', 'Arial_Bold.ttf', 'Arial.ttf', 'impact.ttf'):
        try:
            font = ImageFont.truetype(fname, font_size)
            break
        except Exception:
            pass
    if font is None:
        font = ImageFont.load_default(size=font_size)

    text = 'AC'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    tx = (size - tw) // 2 - bbox[0]
    ty = (size - th) // 2 - bbox[1] - size // 20
    draw.text((tx, ty), text, fill=(255, 255, 255, 255), font=font)

    # Gold underline
    ul_y = ty + th + size // 20
    ul_x1 = size * 8 // 40
    ul_x2 = size * 32 // 40
    lw = max(1, size // 20)
    draw.line([(ul_x1, ul_y), (ul_x2, ul_y)], fill=(247, 184, 1, 255), width=lw)

    return img

def main():
    out = os.path.join(os.path.dirname(__file__), 'static', 'logo.ico')
    sizes = [256, 128, 64, 48, 32, 16]
    images = [draw_logo(s) for s in sizes]
    images[0].save(
        out,
        format='ICO',
        append_images=images[1:],
        sizes=[(s, s) for s in sizes],
    )
    print(f'Written: {out}')

if __name__ == '__main__':
    main()

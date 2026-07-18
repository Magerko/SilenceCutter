"""Regenerates resources/icon.ico and resources/icon.png.

Run with `python tools/make_icon.py` after changing the palette below.
Requires Pillow, which is a build-time dependency only.
"""
import os

from PIL import Image, ImageDraw

BG_TOP = (48, 43, 99)
BG_BOTTOM = (36, 36, 62)
WAVE = (78, 205, 196)
CUT = (255, 107, 107)

SS = 4                      # supersampling factor, downscaled at the end
SIZE = 256 * SS
ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 128, 256]

# Left and right halves of a speech-like waveform. The middle is deliberately
# empty: that gap is the silence the app cuts out.
BARS_LEFT = [0.38, 0.70, 1.00, 0.55]
BARS_RIGHT = [0.62, 1.00, 0.72, 0.34]


def rounded_background() -> Image.Image:
    gradient = Image.new('RGB', (1, SIZE))
    for y in range(SIZE):
        t = y / (SIZE - 1)
        gradient.putpixel((0, y), tuple(
            round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)))
    gradient = gradient.resize((SIZE, SIZE))

    mask = Image.new('L', (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (0, 0, SIZE - 1, SIZE - 1), radius=int(SIZE * 0.22), fill=255)

    canvas = Image.new('RGBA', (SIZE, SIZE), (0, 0, 0, 0))
    canvas.paste(gradient, (0, 0), mask)
    return canvas


def draw_waveform(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)
    centre_y = SIZE / 2
    bar_w = SIZE * 0.052
    gap = SIZE * 0.030
    group_w = len(BARS_LEFT) * bar_w + (len(BARS_LEFT) - 1) * gap
    cut_w = SIZE * 0.19

    left_x = SIZE / 2 - cut_w / 2 - group_w
    right_x = SIZE / 2 + cut_w / 2

    for bars, origin in ((BARS_LEFT, left_x), (BARS_RIGHT, right_x)):
        for i, amplitude in enumerate(bars):
            x = origin + i * (bar_w + gap)
            half = SIZE * 0.34 * amplitude
            draw.rounded_rectangle(
                (x, centre_y - half, x + bar_w, centre_y + half),
                radius=bar_w / 2, fill=WAVE)

    # The cut itself: a coral seam where the silence was removed.
    seam_w = SIZE * 0.022
    draw.rounded_rectangle(
        (SIZE / 2 - seam_w / 2, centre_y - SIZE * 0.30,
         SIZE / 2 + seam_w / 2, centre_y + SIZE * 0.30),
        radius=seam_w / 2, fill=CUT)


def main() -> None:
    canvas = rounded_background()
    draw_waveform(canvas)

    resources = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources')
    os.makedirs(resources, exist_ok=True)

    master = canvas.resize((256, 256), Image.LANCZOS)
    master.save(os.path.join(resources, 'icon.png'))
    master.save(os.path.join(resources, 'icon.ico'),
                sizes=[(s, s) for s in ICO_SIZES])
    print('wrote icon.png and icon.ico to %s' % resources)


if __name__ == '__main__':
    main()
